"""Reviewed, PDF-hash-bound font maps and diagram regions.

Never infer missing letters from U+FFFD itself. These mappings are specific
to the embedded fonts in the exact PDFs compared with their rendered pages.
The PDF bytes on disk are never modified.
"""

import re
from copy import deepcopy


PROFILES = {
    "fc63bcd61715d0181dd8e85998b1e6201ae3515fc6626102101cab1841e11ec6": {
        "figures": {
            36: ([60, 260, 524, 634], "Figure 1: Control Structure"),
        },
    },
    "3ba5248bab614da212440a1bcfe814f0068ef95ebc2d73025742bc78a89c865a": {
        "fonts": {"ECEAGV+Calibri": {"019F": "ti"}},
        "figures": {
            19: ([76, 98, 766, 359], "Figure 2: Phases of Information Exchange Management"),
            20: ([193, 101, 423, 387], "Figure 3: Information Exchange Planning Phase"),
            31: ([246, 139, 367, 422], "Figure 4: Information Exchange Establish Phase"),
            34: ([166, 308, 447, 586], "Figure 5: Information Exchange Maintain Phase"),
            38: ([244, 146, 367, 424], "Figure 6: Information Exchange Discontinue Phase"),
        },
    },
    "16943833039802353339cc03a99421f1771f33777a82a3c046c76c00125e802a": {
        "fonts": {"RZYPZP+TimesNewRomanPSMT": {"0E60": "Th"}},
    },
    "b6e9816c0637290d376a979086c70010473d738c894ed374283160ec4459a16b": {
        "fonts": {"RJJSJG+TimesNewRomanPSMT": {"0E60": "Th"}},
    },
    "75665570048b969ad465a4f4f1db425ce505c374951c2c64e462949c6b21be47": {
        "fonts": {"STXQJN+Calibri": {"014C": "ft", "019F": "ti", "01AB": "tti"},
                  "QACJHR+Calibri-Bold": {"019F": "ti"}},
    },
}


def repair_font_maps(pdf, source_sha256):
    """Correct only known bad ToUnicode entries before text extraction starts."""
    from pdfminer.pdftypes import resolve1

    fonts = PROFILES.get(source_sha256, {}).get("fonts", {})
    if not fonts:
        return []
    seen, repaired = set(), []
    for page in pdf.pages:
        for ref in resolve1(page.page_obj.resources.get("Font", {})).values():
            font = resolve1(ref)
            name = getattr(font.get("BaseFont"), "name", "")
            stream = resolve1(font.get("ToUnicode"))
            if name not in fonts or stream is None or id(stream) in seen:
                continue
            seen.add(id(stream))
            data = stream.get_data()
            for code, text in fonts[name].items():
                pattern = re.compile(rb"<" + code.encode() + rb">\s*<FFFD>", re.I)
                replacement = ("<%s> <%s>" % (code, text.encode("utf-16-be").hex())).encode()
                data, count = pattern.subn(lambda _: replacement, data)
                if count:
                    repaired.append({"font": name, "code": code, "replacement": text})
            # PDFStream caches decoded data; editing this cache leaves the
            # source file, compression and embedded glyph outlines intact.
            stream.data = data
    return repaired


def figure_region(source_sha256, page_number):
    return PROFILES.get(source_sha256, {}).get("figures", {}).get(page_number)


def preserve_source_repairs(previous, current):
    """Retain recorded block/page repairs on reparse of the identical PDF.

    Corrected contents remain canonical. Original records live only in the
    archive. A different PDF must be reviewed instead of inheriting repairs.
    """
    repair = previous.get("source_repairs")
    if not repair:
        return current
    if current.get("source_sha256") != repair["source_sha256"]:
        raise ValueError("PDF changed; source repairs require a new original comparison")
    pages = set(repair.get("pages", []))
    pinned_ids = set(repair.get("block_ids", []))
    retained = [deepcopy(b) for b in previous["contents"]
                if b["source_page"] in pages or b["id"] in pinned_ids]
    if not retained:
        return current
    # Block-level repairs also replace a raw block that drifted to another ID
    # but still occupies the same source region on a reparse.
    spans = {(r["page"], tuple(r["bbox"])) for b in retained
             for r in b.get("source_refs", [])}
    ordinary = [b for b in current["contents"] if b["source_page"] not in pages
                and b["id"] not in pinned_ids
                and not any((r["page"], tuple(r["bbox"])) in spans
                            for r in b.get("source_refs", []))]
    current["contents"] = sorted(ordinary + retained,
                                 key=lambda b: (b["source_page"], b["source_refs"][0]["bbox"][1],
                                                b["source_refs"][0]["bbox"][0]))
    current["source_repairs"] = deepcopy(repair)
    # A continuation reference does not mean the whole following page was
    # extracted. Only whole pinned pages add coverage. Otherwise math carry
    # can try to reconstruct unrelated formulae on an unrequested next page.
    current["included_pages"] = sorted(set(current.get("included_pages", [])) | pages)
    if current.get("pdf_page_count"):
        current["extraction_partial"] = len(current["included_pages"]) != current["pdf_page_count"]
    from .source_quality import encoding_issues
    current["encoding_issues"] = encoding_issues(current)
    current["extraction_warnings"] = [w for w in current.get("extraction_warnings", [])
                                      if "置換文字" not in w]
    for issue in current["encoding_issues"]:
        current["extraction_warnings"].append(
            "PDF p.%s: %sに置換文字が%d箇所。原本照合と文字変換の修復が必要" %
            (issue["page"], issue["id"], issue["count"]))
    return current
