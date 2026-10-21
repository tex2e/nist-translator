"""Recover SP 800-22 mathematics as KaTeX and retain original figure images.

This is a document-specific repair: the reviewed graphic boxes apply only to
the pinned NIST PDF. Original extraction records are archived in the JSON so
neither their translations nor their provenance are silently discarded.
"""

import hashlib
import html
import re
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

SOURCE_SHA256 = "38aba1b34a7fa52c440790d6e0cabf498e4b525177b3b6cebb399ab8ccf031d2"
REPAIR_VERSION = 15
# PDF coordinates, measured on the original pages, including axes/captions.
# Embedded-image boxes are unreliable here: clipping masks make some boxes
# overlap unrelated body text, and the spectral charts have no text objects.
GRAPHICS = {
    42: [([130, 588, 536, 668], "figure", "初期化区間と検定区間")],
    57: [([180, 110, 435, 249], "figure", "ランダムウォークの例")],
    61: [([180, 246, 435, 398], "figure", "ランダムウォークの例")],
    70: [([110, 70, 561, 655], "figure", "周波数成分の有無を示すスペクトル図")],
    90: [([70, 271, 270, 455], "figure", "図4-1：P値のプロット")],
    91: [([60, 121, 280, 322], "figure", "図4-2：P値のヒストグラム")],
    102: [([62, 79, 558, 357], "figure", "図5-1：最終分析レポート")],
    127: [
        ([68, 64, 560, 718], "code", "非周期的テンプレート生成のソースコード（前半）")
    ],
    128: [
        ([68, 64, 560, 385], "code", "非周期的テンプレート生成のソースコード（後半）")
    ],
    129: [
        ([66, 133, 562, 618], "code", "無理数の二進展開を生成するMathematicaプログラム")
    ],
}


def _overlap(left, right):
    width = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0, min(left[3], right[3]) - max(left[1], right[1]))
    area = max(0.01, (left[2] - left[0]) * (left[3] - left[1]))
    return width * height / area


def _chars_in_box(page, box):
    graphic_boxes = [region[0] for region in GRAPHICS.get(page.page_number, [])]
    return [
        char
        for char in page.chars
        if char["x0"] >= 60
        and box[1] - 1 <= (char["top"] + char["bottom"]) / 2 <= box[3] + 1
        and not any(
            region[0] <= (char["x0"] + char["x1"]) / 2 <= region[2]
            and region[1] <= (char["top"] + char["bottom"]) / 2 <= region[3]
            for region in graphic_boxes
        )
        and char["text"].strip()
    ]


def _math_risk(block, pages):
    text = html.unescape(re.sub(r"<[^>]+>", " ", block["html"]))
    if re.search(r"[\ue000-\uf8ff∑∫√∇€]", text):
        return True
    chars = [
        char
        for ref in block["source_refs"]
        for char in _chars_in_box(pages[ref["page"] - 1], ref["bbox"])
    ]
    if any("Symbol" in char["fontname"] for char in chars):
        return True
    # Small Times/Symbol glyphs are superscripts, subscripts and limits, not
    # separate paragraphs. Small Arial text also occurs inside real diagrams.
    small_math = any(
        char["size"] < 8.5
        and ("Times" in char["fontname"] or "Symbol" in char["fontname"])
        for char in chars
    )
    if small_math and (
        len(text.strip()) < 30 or any(char["size"] > 10 for char in chars)
    ):
        return True
    return False


def restore_extraction(document):
    """Recover raw records and translations before reapplying a repair."""
    result = deepcopy(document)
    archive = document.get("math_preservation", {})
    if not archive:
        return result
    # Records that a page rebuild replaced are raw records too; the rebuilt
    # blocks themselves are not, so they are left out.
    blocks = {
        block["id"]: deepcopy(block)
        for block in archive["original_blocks"] + archive.get("rebuilt_blocks", [])
        if not block.get("replaces")
    }
    blocks.update(
        {
            block["id"]: deepcopy(block)
            for block in document["contents"]
            if not block.get("replaces") and block["kind"] != "source_excerpt"
            and not block.get("column_reflow", {}).get("rebuilt")
        }
    )
    result["contents"] = sorted(blocks.values(), key=lambda block: block["id"])
    result.pop("math_preservation", None)
    return result


def preserve_sp800_22_math(
    document, pdf_path, asset_dir, asset_prefix, previous_document=None
):
    """Recover fragmented math; apply source-bound LaTeX and original figures.

    Ambiguous structural LaTeX candidates are marked needs_review.
    Raw extraction records and translations remain available for reparsing.
    """
    import pdfplumber
    import pypdfium2
    from .pdf_equations import (
        recover_region,
        inline_katex_html,
        pending_math_translation,
    )

    pdf_path, asset_dir = Path(pdf_path), Path(asset_dir)
    source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if source_hash != SOURCE_SHA256:
        raise ValueError(
            "SP 800-22 PDF changed; review math/figure regions before applying the repair"
        )
    existing = document.get("math_preservation", {})
    if (
        existing.get("version") == REPAIR_VERSION
        and existing.get("source_sha256") == source_hash
    ):
        return deepcopy(document)
    repaired = deepcopy(document)
    original = restore_extraction(document)["contents"]
    prior_math = {
        block["id"]: block
        for block in (previous_document or document)["contents"]
        if block.get("math_mode")
    }
    parents = list(range(len(original)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        parents[find(right)] = find(left)

    regions = []
    region_members = []
    graphic_indices = set()
    for page_number, graphics in GRAPHICS.items():
        for box, kind, label in graphics:
            members = [
                index
                for index, block in enumerate(original)
                if any(
                    ref["page"] == page_number and _overlap(ref["bbox"], box) > 0.45
                    for ref in block["source_refs"]
                )
            ]
            # The existing graph crop is oversized and overlaps body text.
            members += [
                index
                for index, block in enumerate(original)
                if block["kind"] == "figure" and block["source_page"] == page_number
            ]
            members = sorted(set(members))
            if graphic_indices.intersection(members):
                raise ValueError("Reviewed graphic regions overlap")
            graphic_indices.update(members)
            regions.append(
                {"page": page_number, "bbox": box, "type": kind, "label": label}
            )
            region_members.append(members)

    with pdfplumber.open(str(pdf_path)) as pdf:
        by_page = defaultdict(list)
        for index, block in enumerate(original):
            if index in graphic_indices or block["kind"] == "figure":
                continue
            for ref in block["source_refs"]:
                by_page[ref["page"]].append((index, ref["bbox"]))
        # Join rows before classifying math so a detached "0" in H_0 also
        # brings along the sentence it belongs to. Real section headings
        # remain boundaries even when a tall mathematical glyph touches them.
        for entries in by_page.values():
            for position, (left_index, left) in enumerate(entries):
                for right_index, right in entries[position + 1 :]:
                    if min(left[3], right[3]) + 8 < max(left[1], right[1]):
                        continue
                    left_block, right_block = (
                        original[left_index],
                        original[right_index],
                    )
                    if any(
                        block["kind"] == "heading"
                        and re.match(
                            r"^(?:\d+(?:\.\d+)*\s+[A-Za-z]|Appendix\s+[A-Z])",
                            block["html"],
                        )
                        for block in (left_block, right_block)
                    ):
                        continue
                    union(left_index, right_index)
        risks = {
            index
            for index, block in enumerate(original)
            if index not in graphic_indices and _math_risk(block, pdf.pages)
        }
        # Adjacent display lines can be the two halves of one long equation.
        # Join them across a small gap, but keep section headings as barriers.
        for entries in by_page.values():
            ordered = sorted(entries, key=lambda item: item[1][1])
            for (left_index, left), (right_index, right) in zip(ordered, ordered[1:]):
                if (
                    left_index in risks
                    and right_index in risks
                    and original[left_index]["kind"] != "heading"
                    and original[right_index]["kind"] != "heading"
                    and 0 <= right[1] - left[3] <= 18
                ):
                    union(left_index, right_index)
        components = defaultdict(list)
        for index in range(len(original)):
            if index not in graphic_indices:
                components[find(index)].append(index)
        for members in components.values():
            if not risks.intersection(members):
                continue
            boxes = defaultdict(list)
            for index in members:
                for ref in original[index]["source_refs"]:
                    boxes[ref["page"]].append(ref["bbox"])
            kind = (
                "table"
                if any(original[index]["kind"] == "table" for index in members)
                else "math"
            )
            for page_number, page_boxes in sorted(boxes.items()):
                box = [
                    min(value[0] for value in page_boxes),
                    min(value[1] for value in page_boxes),
                    max(value[2] for value in page_boxes),
                    max(value[3] for value in page_boxes),
                ]
                # The old parser retained the x0 of the first (often raised)
                # glyph, omitting the left half of later lines. Recover all
                # characters on the same rows directly from the PDF.
                row_chars = _chars_in_box(pdf.pages[page_number - 1], box)
                if row_chars:
                    box[0] = min(box[0], min(char["x0"] for char in row_chars))
                    box[2] = max(box[2], max(char["x1"] for char in row_chars))
                regions.append(
                    {
                        "page": page_number,
                        "bbox": box,
                        "type": kind,
                        "label": (
                            "数式を含む表" if kind == "table" else "数式と周辺の説明"
                        ),
                    }
                )
                region_members.append(members)

        asset_dir.mkdir(parents=True, exist_ok=True)
        rendered_pdf = pypdfium2.PdfDocument(str(pdf_path))
        page_images = {}
        replacements = defaultdict(list)
        covered = set()
        crop_records = []
        empty_artifacts = []
        equation_records = []
        for region_index, (region, members) in enumerate(
            zip(regions, region_members), 1
        ):
            page_number, box = region["page"], region["bbox"]
            page = pdf.pages[page_number - 1]
            # Padding retains antialiased glyph edges, fraction rules and
            # bracket strokes extending slightly outside character boxes.
            top, bottom = box[1] - 2, box[3] + 2
            if region["type"] in {"math", "table"}:
                # Do not include a clipped sliver of an adjacent prose line.
                adjacent = [
                    ref["bbox"]
                    for index, item in enumerate(original)
                    if index not in members and index not in graphic_indices
                    for ref in item["source_refs"]
                    if ref["page"] == page_number
                ]
                above = [other[3] for other in adjacent if other[3] <= box[1]]
                below = [other[1] for other in adjacent if other[1] >= box[3]]
                if above:
                    top = max(top, (max(above) + box[1]) / 2)
                if below:
                    bottom = min(bottom, (min(below) + box[3]) / 2)
            box = [
                max(0, box[0] - 4),
                max(0, top),
                min(page.width, box[2] + 4),
                min(page.height, bottom),
            ]
            if region["type"] in {"math", "table"}:
                identifier = "pdf-p%04d-math-%03d" % (page_number, region_index)
                source_html, equations = recover_region(
                    page, box, [g[0] for g in GRAPHICS.get(page_number, [])]
                )
                correction = prior_math.get(identifier)
                if correction:
                    expected = correction.get("math_source_hashes")
                    actual = {
                        original[index]["id"]: original[index]["source_hash"]
                        for index in members
                    }
                    if expected is not None and expected != actual:
                        raise ValueError("Math source changed: " + identifier)
                    source_html = correction["html"]
                source_html = inline_katex_html(source_html)
                if not source_html:
                    covered.update(members)
                    empty_artifacts.extend(original[index]["id"] for index in members)
                    continue
                ja = (
                    inline_katex_html(correction.get("html_ja", ""))
                    if correction
                    else ""
                )
                mode = correction.get("math_mode", "latex") if correction else "latex"
                pending = (
                    correction.get("status") == "untranslated" if correction else True
                )
                if not ja:
                    ja = pending_math_translation(source_html)
                block = {
                    "id": identifier,
                    "kind": "math",
                    "html": source_html,
                    "html_ja": ja,
                    "status": (correction["status"] if correction else "untranslated"),
                    "extraction_status": (
                        correction.get("extraction_status", "needs_review")
                        if correction
                        else "needs_review"
                    ),
                    "source_page": page_number,
                    "source_refs": [{"page": page_number, "bbox": box}],
                    "source_hash": hashlib.sha256(
                        ("math\n" + source_html).encode()
                    ).hexdigest()[:16],
                    "math_mode": mode,
                    "math_translation_pending": pending,
                    "math_source_hashes": {
                        original[index]["id"]: original[index]["source_hash"]
                        for index in members
                    },
                    "replaces": [original[index]["id"] for index in members],
                }
                if correction:
                    for field in (
                        "math_reconstruction",
                        "math_review_notes",
                        "math_duplicate_of",
                    ):
                        if field in correction:
                            block[field] = deepcopy(correction[field])
                if members:
                    replacements[min(members)].append(block)
                covered.update(members)
                equation_records.append(
                    {
                        "id": identifier,
                        "page": page_number,
                        "bbox": box,
                        "mode": block["math_mode"],
                        "equations": equations,
                        "replaces": block["replaces"],
                    }
                )
                continue
            if region["type"] == "code":
                code = "\n".join(
                    line.rstrip()
                    for line in page.crop(tuple(box))
                    .extract_text(layout=True)
                    .splitlines()
                ).strip()
                source_html = "<pre><code>" + html.escape(code) + "</code></pre>"
                identifier = "pdf-p%04d-code-%03d" % (page_number, region_index)
                block = {
                    "id": identifier,
                    "kind": "code",
                    "html": source_html,
                    "html_ja": "",
                    "status": "source_only",
                    "extraction_status": "needs_review",
                    "source_page": page_number,
                    "source_refs": [{"page": page_number, "bbox": box}],
                    "source_hash": hashlib.sha256(
                        ("code\n" + source_html).encode()
                    ).hexdigest()[:16],
                    "replaces": [original[index]["id"] for index in members],
                }
                if members:
                    replacements[min(members)].append(block)
                covered.update(members)
                continue
            if page_number not in page_images:
                page_images.clear()
                page_images[page_number] = (
                    rendered_pdf[page_number - 1].render(scale=3).to_pil()
                )
            image = page_images[page_number]
            crop = image.crop(
                (
                    int(box[0] * 3),
                    int(box[1] * 3),
                    int(box[2] * 3 + 0.999),
                    int(box[3] * 3 + 0.999),
                )
            )
            if crop.convert("L").getextrema()[0] > 230:
                # MathType's invisible Symbol-font spacer sometimes extracts
                # as a euro sign. A blank crop must not become a visible row.
                covered.update(members)
                empty_artifacts.extend(original[index]["id"] for index in members)
                continue
            name = "p%04d-preserved-%03d.png" % (page_number, region_index)
            path = asset_dir / name
            crop.save(path, optimize=True)
            url = "%s/%s" % (asset_prefix.rstrip("/"), name)
            image_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            alt = "PDF p.%d：%s（原本画像）" % (page_number, region["label"])
            source_html = (
                '<img src="%s" alt="%s" width="%d" height="%d" loading="lazy">'
                % (
                    html.escape(url, quote=True),
                    html.escape(alt, quote=True),
                    round(crop.width * 1.4 / 3),
                    round(crop.height * 1.4 / 3),
                )
            )
            first = min(members) if members else None
            # A multi-page original block can yield one crop for each page.
            identifier = "pdf-p%04d-preserved-%03d" % (page_number, region_index)
            block = {
                "id": identifier,
                "kind": "source_excerpt",
                "html": source_html,
                "html_ja": "",
                "status": "source_only",
                "extraction_status": "verified",
                "source_page": page_number,
                "source_refs": [{"page": page_number, "bbox": box}],
                "source_hash": hashlib.sha256(
                    ("source_excerpt\n" + source_html + "\n" + image_hash).encode()
                ).hexdigest()[:16],
                "source_image_hash": image_hash,
                "source_excerpt_type": region["type"],
                "source_label": region["label"],
                "source_image": url,
                "replaces": [original[index]["id"] for index in members],
            }
            if first is not None:
                replacements[first].append(block)
            else:
                # Raster-only charts have no extraction records. Insert by
                # physical page rather than dropping them for lack of text.
                following = next(
                    (
                        index
                        for index, item in enumerate(original)
                        if item["source_page"] > page_number
                    ),
                    len(original),
                )
                replacements[following].append(block)
            covered.update(members)
            crop_records.append(
                {
                    "id": identifier,
                    **region,
                    "bbox": box,
                    "asset": url,
                    "replaces": block["replaces"],
                }
            )
        rendered_pdf.close()

    repaired["contents"] = []
    for index, block in enumerate(original):
        repaired["contents"].extend(replacements.get(index, []))
        if index not in covered:
            repaired["contents"].append(block)
    repaired["contents"].extend(replacements.get(len(original), []))
    repaired["math_preservation"] = {
        "version": REPAIR_VERSION,
        "source_sha256": source_hash,
        "storage_format": "semantic_inline_katex",
        "coordinate_layout_region_count": 0,
        "mode": "katex_with_original_figures",
        "resolution_dpi": 216,
        "crop_count": len(crop_records),
        "equation_region_count": len(equation_records),
        "replaced_block_count": len(covered),
        "original_record_count": len(original),
        "regions": crop_records,
        "equation_regions": equation_records,
        "empty_artifact_ids": empty_artifacts,
        "original_blocks": [original[index] for index in sorted(covered)],
    }
    return repaired
