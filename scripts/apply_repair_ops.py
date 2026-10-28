"""Apply a reviewed list of source repairs (from an original-PDF comparison) to a document.

    python scripts/apply_repair_ops.py OPS_JSON [--dry-run]

OPS_JSON: {"document": "sp800-130", "pdf_sha256": "...", "evidence_directory": "...",
           "reason": "...", "ops": [...]}. Each op names the blocks it touches:

- {"op": "verify", "id", "note", optional "html", "kind", "level", "ordered", "ordinal",
   "depth", "source_page"}: the block matches the original (after the given corrections).
- {"op": "retire", "id", "note"}: a duplicate, fragment or false record; removed from contents.
- {"op": "merge", "into", "from": [ids], "html", "note"}: "into" gets the whole text,
   the "from" blocks are retired.
- {"op": "split", "id", "parts": [{"kind", "html", ...}], "note"}: the first part keeps the id.
- {"op": "insert", "after", "kind", "html", "source_page", "note", ...}: text missing from the
   document; a new block after "after".
- {"op": "furniture", "id", "note"}: running header/footer or page number; kept but hidden.
- {"op": "order", "ids": [...]}: put these blocks consecutively in this order.
- {"op": "figure", "id", "alt_en", "alt_ja", "note", optional "crop_png", "bbox"}.
- {"op": "table", "id", "html", "note"}: a table restored as HTML from the original.

Every touched block is archived in source_repairs.original_blocks first, and the pages it
spans are pinned so a reparse of the same PDF keeps the repair. A changed English text gets
a new source_hash; its earlier translation is kept (status draft, for review) when the text
changed only slightly, otherwise cleared (status untranslated). Source references are
recomputed from the PDF text layer when the text can be located. Extraction is marked
verified; translation approval is never added here.
"""

import argparse
import copy
import difflib
import hashlib
import html as htmllib
import json
import re
import shutil
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
ATTRS = ("kind", "level", "ordered", "ordinal", "depth", "source_page")


def plain(value):
    return re.sub(r"\s+", "", htmllib.unescape(re.sub(r"<[^>]+>", "", value)))


def rehash(block):
    block["source_hash"] = hashlib.sha256(
        (block["kind"] + "\n" + block["html"] + "\n").encode()).hexdigest()[:16]


class Locator:
    def __init__(self, pdf_path):
        self.pdf = pdfplumber.open(pdf_path)
        self.pages = {}

    def words(self, page):
        if page not in self.pages:
            words = self.pdf.pages[page - 1].extract_words(use_text_flow=True)
            self.pages[page] = [w for w in words if w["x0"] > 40]
        return self.pages[page]

    def find(self, text, pages):
        """Union bbox of the words covering ``text`` (whitespace ignored), per page."""
        target = plain(text)
        if not target:
            return None
        refs, rest = [], target
        for page in pages:
            words = self.words(page)
            stream, owner = "", []
            for index, word in enumerate(words):
                piece = plain(word["text"])
                stream += piece
                owner += [index] * len(piece)
            # longest prefix of the remaining text found on this page
            for size in range(len(rest), 7, -1):
                at = stream.find(rest[:size])
                if at >= 0:
                    used = [words[i] for i in sorted(set(owner[at:at + size]))]
                    refs.append({"page": page, "bbox": [round(min(w["x0"] for w in used), 1),
                                                        round(min(w["top"] for w in used), 1),
                                                        round(max(w["x1"] for w in used), 1),
                                                        round(max(w["bottom"] for w in used), 1)]})
                    rest = rest[size:]
                    break
            if not rest:
                return refs
        return None


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("ops", type=Path)
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    spec = json.loads(args.ops.read_text())
    path = ROOT / "data" / (spec["document"] + "-trans.json")
    document = json.loads(path.read_text())
    if document["source_sha256"] != spec["pdf_sha256"]:
        raise SystemExit("PDF hash differs from the comparison; not applied")
    pdf_path = ROOT / "data" / (spec["document"] + ".pdf")
    if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != spec["pdf_sha256"]:
        raise SystemExit("local PDF differs from the comparison; not applied")
    locator = Locator(pdf_path)
    contents = document["contents"]
    blocks = {b["id"]: b for b in contents}
    archive, retired, touched, warnings = {}, [], {}, []
    stamp = "原本画像と文字層で照合（%s）。" % spec.get("checked_by", "Claude Opus")

    def take(key):
        if key not in blocks:
            raise SystemExit("unknown block " + key)
        archive.setdefault(key, copy.deepcopy(blocks[key]))
        touched[key] = blocks[key]
        return blocks[key]

    def set_text(block, value, note):
        old = block["html"]
        block["html"] = value
        rehash(block)
        if block.get("html_ja"):
            ratio = difflib.SequenceMatcher(None, plain(old), plain(value)).ratio()
            if ratio >= 0.97 and block["kind"] != "table":
                block["status"] = "draft"
            else:
                block["html_ja"] = ""
                block["status"] = "untranslated"
            block.pop("translation_check", None)
            block.pop("translation_fix_rounds", None)

    def mark(block, note):
        block["extraction_status"] = "verified"
        block["extraction_check"] = "visual-page"
        block.pop("page_furniture", None)
        if isinstance(block.get("column_reflow"), dict):
            block["column_reflow"]["page_proof"] = "matches_original"
            block["column_reflow"].pop("proof_note", None)
        block["extraction_note"] = stamp + (note or "")

    def new_block(template, key, part):
        block = {k: v for k, v in template.items()
                 if k in ("source_page", "source_refs", "column")}
        block.update({"id": key, "status": "untranslated", "html_ja": ""})
        block.update({k: part[k] for k in ("kind", "html", "level", "ordered", "ordinal", "depth",
                                            "source_page") if k in part})
        rehash(block)
        blocks[key] = block
        touched[key] = block
        return block

    def fresh_id(base):
        index = 1
        while "%s-s%d" % (base, index) in blocks:
            index += 1
        return "%s-s%d" % (base, index)

    for op in spec["ops"]:
        kind, note = op["op"], op.get("note", "")
        if kind == "verify":
            block = take(op["id"])
            for key in ATTRS:
                if key in op:
                    block[key] = op[key]
            if "html" in op and op["html"] != block["html"]:
                set_text(block, op["html"], note)
            elif any(key in op for key in ("kind", "level")):
                rehash(block)
            mark(block, note)
        elif kind == "retire":
            block = take(op["id"])
            block["retired_note"] = note
            retired.append(block)
        elif kind == "merge":
            block = take(op["into"])
            for key in op["from"]:
                retired.append(take(key))
                block["source_refs"] = block.get("source_refs", []) + blocks[key].get("source_refs", [])
            set_text(block, op["html"], note)
            if op.get("html_ja"):
                block["html_ja"], block["status"] = op["html_ja"], "draft"
            mark(block, note)
        elif kind == "split":
            block = take(op["id"])
            at = contents.index(block)
            parts = op["parts"]
            for key in ATTRS:
                if key in parts[0]:
                    block[key] = parts[0][key]
            set_text(block, parts[0]["html"], note)
            if block["status"] == "draft":
                block["html_ja"], block["status"] = "", "untranslated"
            mark(block, note)
            for offset, part in enumerate(parts[1:], 1):
                piece = new_block(block, fresh_id(op["id"]), part)
                piece["split_from"] = op["id"]
                mark(piece, note)
                contents.insert(at + offset, piece)
        elif kind == "insert":
            anchor = take(op["after"]) if op["after"] in blocks else None
            piece = new_block(anchor or {}, op.get("new_id") or fresh_id(op["after"]), op)
            piece["source_refs"] = [{"page": op["source_page"], "bbox": [0, 0, 0, 0]}]
            mark(piece, note)
            contents.insert(contents.index(anchor) + 1, piece)
        elif kind == "furniture":
            block = take(op["id"])
            block["page_furniture"] = True
            block["extraction_status"] = "verified"
            block["extraction_note"] = stamp + note
        elif kind == "order":
            moving = [take(key) for key in op["ids"]]
            at = min(contents.index(b) for b in moving)
            for b in moving:
                contents.remove(b)
            contents[at:at] = moving
        elif kind == "figure":
            block = take(op["id"])
            src = re.search(r'src="([^"]+)"', block["html"]).group(1)
            if op.get("crop_png"):
                target = ROOT / "html" / src
                if not args.dry_run:
                    shutil.copyfile(op["crop_png"], target)
                block["source_image_hash"] = hashlib.sha256(Path(op["crop_png"]).read_bytes()).hexdigest()
            if op.get("bbox"):
                block["source_refs"] = [{"page": block["source_page"], "bbox": op["bbox"]}]
            esc = lambda s: htmllib.escape(s, quote=True)
            block["html"] = '<img src="%s" alt="%s">' % (src, esc(op["alt_en"]))
            block["html_ja"] = '<img src="%s" alt="%s">' % (src, esc(op["alt_ja"]))
            rehash(block)
            block["status"] = "draft"
            block.pop("translation_check", None)
            mark(block, note)
        elif kind == "table":
            block = take(op["id"])
            set_text(block, op["html"], note)
            block["html_ja"], block["status"] = "", "untranslated"
            for key in ("source_image",):
                block.pop(key, None)
            mark(block, note)
        else:
            raise SystemExit("unknown op " + kind)

    for block in retired:
        touched.pop(block["id"], None)
        if block in contents:
            contents.remove(block)
    # Exact source references from the text layer where the text is found.
    for block in touched.values():
        if block["kind"] in ("figure", "table") or block.get("page_furniture"):
            continue
        pages = sorted({r["page"] for r in block.get("source_refs", [])} | {block["source_page"]})
        pages = [p for p in range(min(pages), max(pages) + 2) if p <= len(locator.pdf.pages)]
        refs = locator.find(block["html"], pages)
        if refs:
            block["source_refs"] = refs
            block["source_page"] = refs[0]["page"]
        else:
            warnings.append("text not located: " + block["id"])
    pinned = set()
    for block in list(touched.values()) + retired:
        pinned |= {r["page"] for r in block.get("source_refs", [])} | {block["source_page"]}
    repair = document.setdefault("source_repairs", {"source_sha256": spec["pdf_sha256"], "pages": [],
                                                    "original_blocks": [], "history": []})
    if repair.get("source_sha256") != spec["pdf_sha256"]:
        raise SystemExit("existing source_repairs belong to another PDF")
    repair.setdefault("history", []).append({k: copy.deepcopy(v) for k, v in repair.items()
                                             if k not in ("original_blocks", "history")})
    repair["pages"] = sorted(set(repair.get("pages", [])) | pinned)
    repair["original_blocks"] = repair.get("original_blocks", []) + list(archive.values())
    repair["retired_block_ids"] = repair.get("retired_block_ids", []) + [b["id"] for b in retired]
    repair["evidence_directory"] = spec["evidence_directory"]
    repair["reason"] = spec["reason"]
    sys.path.insert(0, str(ROOT / "src"))
    from nist_translater.translation import audit_translations
    audit_translations(document)
    print(json.dumps({"touched": len(touched), "retired": len(retired), "archived": len(archive),
                      "pinned_pages": len(pinned), "warnings": warnings}, ensure_ascii=False))
    if not args.dry_run:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
