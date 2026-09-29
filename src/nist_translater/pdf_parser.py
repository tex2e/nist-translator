"""Turn a NIST PDF into source blocks with page-level provenance.

PDF layout is not a reliable semantic tree. Every extracted block starts with
``extraction_status=needs_review``; visual review against the official PDF is
required before its English text is considered verified.
"""

import hashlib
import html
import re
from collections import defaultdict
from pathlib import Path


HEADING = re.compile(r"^(?:(\d{1,3}(?:\.\d+)*\.?)\s+|Appendix\s+[A-Z](?::|\s))", re.I)
LIST_ITEM = re.compile(r"^(?:[•●▪]\s+|(\d+)\.\s+)")
FOOTNOTE = re.compile(r"^\d{1,2}\s+\S")
FRONT_HEADINGS = {"Abstract", "Keywords", "Acknowledgments", "Table of Contents",
                  "Reports on Computer Systems Technology"}


def _normal(text):
    return " ".join(text.replace("\u00ad", "").replace("\ufb01", "fi")
                   .replace("\ufb02", "fl").split())


def _join_lines(left, right):
    # Keep a printed hyphen: it may be part of an identifier or compound word.
    return left + ("" if left.endswith("-") else " ") + right


def _bbox(item):
    return [round(float(item[key]), 1) for key in ("x0", "top", "x1", "bottom")]


def _bounded_bbox(box, page):
    """Clamp a detected box to its page; PDF table rules can overshoot the crop box."""
    x0, top, x1, bottom = box
    bounded = (max(0, x0), max(0, top), min(page.width, x1), min(page.height, bottom))
    if bounded[0] >= bounded[2] or bounded[1] >= bounded[3]:
        raise ValueError("Detected PDF region does not intersect the page")
    return bounded


def _size(line):
    sizes = sorted(char["size"] for char in line.get("chars", []) if char.get("upright", True))
    return sizes[len(sizes) // 2] if sizes else 0


def _bold_ratio(line):
    chars = [char for char in line.get("chars", []) if char.get("upright", True)]
    return (sum("bold" in char.get("fontname", "").lower() for char in chars) / len(chars)
            if chars else 0)


def _split_horizontal_fragments(line, page):
    """Split unrelated text boxes that pdfplumber joins across a wide gap."""
    chars = sorted(line.get("chars", []), key=lambda char: char["x0"])
    if len(chars) < 2:
        return [line]
    groups = [[chars[0]]]
    for char in chars[1:]:
        if char["x0"] - groups[-1][-1]["x1"] > max(40, page.width * 0.06):
            groups.append([])
        groups[-1].append(char)
    if len(groups) == 1:
        return [line]
    fragments = []
    for group in groups:
        text = _chars_text(group)
        if not text:
            continue
        fragment = {
            **line,
            "x0": min(char["x0"] for char in group),
            "x1": max(char["x1"] for char in group),
            "top": min(char["top"] for char in group),
            "bottom": max(char["bottom"] for char in group),
            "chars": group,
            "text": text,
        }
        fragments.append({**fragment, "size": _size(fragment),
                          "bold_ratio": _bold_ratio(fragment)})
    return fragments


def _chars_text(chars):
    """Rebuild a line from positioned characters, restoring omitted word spaces."""
    parts = []
    previous = None
    seen = set()
    for char in chars:
        position = (round(char["x0"], 2), round(char["top"], 2), char["text"])
        if position in seen:
            continue  # Some PDFs paint the same footer glyph twice at identical coordinates.
        seen.add(position)
        # Some NIST PDFs use unusually tight word spacing. A size-relative
        # threshold of 0.17 drops genuine spaces in 10–12 pt body text.
        if (previous and char["x0"] - previous["x1"] > 1.6):
            parts.append(" ")
        parts.append(char["text"])
        previous = char
    return _normal("".join(parts))


def _text_lines(page, running_headers=None):
    raw_lines = page.extract_text_lines(layout=False)
    result = []
    for raw_line in raw_lines:
        chars = raw_line.get("chars", [])
        if chars and sum(not char.get("upright", True) for char in chars) > len(chars) / 2:
            continue  # Vertical running text is page furniture, not body text.
        for line in _split_horizontal_fragments(raw_line, page):
            if line["top"] < 0 or line["bottom"] > page.height:
                continue
            text = _chars_text(line.get("chars", [])) or _normal(line["text"])
            page_label = re.sub(r"(.)\1+", r"\1", text, flags=re.I)
            if (not text or re.fullmatch(r"[-–—_=\s]{3,}", text) or
                    re.fullmatch(r"PAGE\s+\d+", page_label, re.I)):
                continue
            repeated_header = line["top"] < 66 and text in (running_headers or set())
            page_number = (line["top"] > page.height * 0.9 and
                           re.fullmatch(r"(?:\d{1,3}|[ivxlcdm]{1,8})", text, re.I))
            if repeated_header or page_number:
                continue  # Repeated running headers and printed page labels are page furniture.
            result.append({**line, "text": text, "size": _size(line),
                           "bold_ratio": _bold_ratio(line)})
    table_of = next((line for line in result if line["text"].lower() == "table of"), None)
    contents = next((line for line in result if line["text"].lower() == "contents"), None)
    if table_of and contents:
        title = {
            **table_of,
            "text": "Table of Contents",
            "x0": min(table_of["x0"], contents["x0"]),
            "x1": max(table_of["x1"], contents["x1"]),
            "top": min(table_of["top"], contents["top"]),
            "bottom": max(table_of["bottom"], contents["bottom"]),
            "chars": table_of.get("chars", []) + contents.get("chars", []),
        }
        title["size"] = _size(title)
        title["bold_ratio"] = _bold_ratio(title)
        result = [line for line in result if line not in (table_of, contents)] + [title]

        paired_numbers = set()
        for number in list(result):
            if not re.fullmatch(r"\d{2}", number["text"]):
                continue
            candidates = [line for line in result
                          if line is not number and line["text"] != title["text"]
                          and line["x0"] < page.width / 2 < number["x0"]
                          and max(line["top"], number["top"]) <
                              min(line["bottom"], number["bottom"])
                          and id(line) not in paired_numbers]
            if not candidates:
                continue
            label = min(candidates, key=lambda line: abs(line["top"] - number["top"]))
            label["text"] += " " + number["text"]
            label["top"] = min(label["top"], number["top"])
            label["bottom"] = max(label["bottom"], number["bottom"])
            label["x1"] = max(label["x1"], number["x1"])
            label["chars"] = label.get("chars", []) + number.get("chars", [])
            paired_numbers.add(id(label))
            result.remove(number)
        ordered = sorted(result, key=lambda line: (line["top"], line["x0"]))
        for index, line in enumerate(ordered[:-1]):
            continuation = ordered[index + 1]
            match = re.fullmatch(r"(.+?)\s+(\d{1,2})", line["text"])
            gap = continuation["top"] - line["bottom"]
            if (match and 0 <= gap <= 8 and
                    continuation["text"] != title["text"] and
                    not continuation["text"].startswith("-") and
                    not re.fullmatch(r"\d{1,2}", continuation["text"])):
                label, page_number = match.groups()
                separator = "" if label.endswith("-") else " "
                line["text"] = label + separator + continuation["text"] + " " + page_number
                line["bottom"] = max(line["bottom"], continuation["bottom"])
                line["x1"] = max(line["x1"], continuation["x1"])
                line["chars"] = line.get("chars", []) + continuation.get("chars", [])
                result.remove(continuation)
    return sorted(result, key=lambda line: (line["top"], line["x0"]))


def _inside(line, box):
    x = (line["x0"] + line["x1"]) / 2
    y = (line["top"] + line["bottom"]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def _is_page_sized_artifact(box, page):
    """Ignore full-page rule detections caused by decorative page artwork."""
    x0, top, x1, bottom = box
    return (x0 <= 1 and top <= 1 and x1 >= page.width - 1 and
            bottom >= page.height - 1)


def _is_layout_artifact_table(box, page):
    """Reject large shallow boxes that are page banners, not data tables."""
    x0, top, x1, bottom = box
    width = x1 - x0
    height = bottom - top
    return (_is_page_sized_artifact(box, page) or
            (width >= page.width * 0.9 and height <= page.height * 0.12))


def _has_parallel_columns(page, running_headers=None):
    midpoint = page.width / 2
    tables = [table.bbox for table in page.find_tables()
              if not _is_layout_artifact_table(table.bbox, page)]
    lines = [line for line in _text_lines(page, running_headers)
             if line["top"] < page.height * 0.76 and
             not any(_inside(line, box) for box in tables)]
    left = [line for line in lines if line["x1"] < midpoint - 5]
    right = [line for line in lines if line["x0"] > midpoint + 5]
    return (len(left) >= 5 and len(right) >= 5 and
            max(left[0]["top"], right[0]["top"]) <
            min(left[-1]["bottom"], right[-1]["bottom"]))


def _table_html(table):
    """Collapse narrow, empty PDF grid cells to the text-bearing columns."""
    extracted = table.extract()
    candidates = []
    for row, values in zip(table.rows, extracted):
        cells = [(box, _normal(value)) for box, value in zip(row.cells, values) if box and value and value.strip()]
        if len(cells) >= 2:
            coverage = sum(box[2] - box[0] for box, _ in cells) / (table.bbox[2] - table.bbox[0])
            candidates.append((coverage, cells))
    if not candidates:
        return "", False
    coverage, anchors = max(candidates, key=lambda item: item[0])
    columns = sorted((box[0], box[2]) for box, _ in anchors)
    if coverage < 0.7 or any(columns[i][1] > columns[i + 1][0] + 2
                             for i in range(len(columns) - 1)):
        return "", False
    rows = []
    ambiguous = False
    for row, values in zip(table.rows, extracted):
        cells = ["" for _ in columns]
        for box, value in zip(row.cells, values):
            if not box or not value or not value.strip():
                continue
            center = (box[0] + box[2]) / 2
            target = min(range(len(columns)),
                         key=lambda index: abs(center - (columns[index][0] + columns[index][1]) / 2))
            if cells[target]:
                ambiguous = True
                cells[target] += " / " + _normal(value)
            else:
                cells[target] = _normal(value)
        if any(cells):
            rows.append(cells)
    if not rows:
        return "", False
    parts = ["<table>"]
    for cells in rows:
        parts.append("<tr>")
        for value in cells:
            parts.append("<td>%s</td>" % html.escape(value))
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts), not ambiguous


def _save_crop(page, box, asset_dir, asset_prefix, name, table=False):
    if asset_dir is None:
        return None, None
    asset_dir = Path(asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    path = asset_dir / name
    # A table caption may touch the top edge of a detected table. Its text is
    # retained as a separate block, so keep it out of the source table image.
    top = box[1] + 2 if table else box[1] - 3
    padded = _bounded_bbox((box[0] - 3, top, box[2] + 3, box[3] + 3), page)
    page.crop(padded).to_image(resolution=144).save(str(path))
    return "%s/%s" % (asset_prefix.rstrip("/"), name), hashlib.sha256(path.read_bytes()).hexdigest()


def _kind(line, footnote_top):
    text = line["text"]
    if footnote_top is not None and line["top"] >= footnote_top:
        return "footnote"
    if re.fullmatch(r"\([A-Za-z0-9.-]{1,16}\)[.,;:]?", text):
        return "paragraph"  # Short parenthetical acronyms often wrap a list-item line.
    if (HEADING.match(text) and len(text) < 150 and
            (line["bold_ratio"] >= 0.5 or
             (line["size"] >= 13 and not LIST_ITEM.match(text)))):
        return "heading"
    if text in FRONT_HEADINGS and line["size"] >= 11:
        return "heading"
    if text.isupper() and len(text) < 150 and line["size"] >= 11:
        return "heading"
    if (text.lower().startswith("major accomplishments in fy ") or
            text.lower().startswith("fy 2024 event topics included:")):
        return "heading"
    if len(text) < 150 and line["size"] >= 20:
        return "heading"
    if LIST_ITEM.match(text):
        return "list_item"
    if text.startswith("Note:") and line["x0"] >= 100:
        return "note"
    return "paragraph"


def _page_items(page, page_number, asset_dir, asset_prefix, running_headers=None):
    lines = _text_lines(page, running_headers)
    toc_page = (any(line["text"] == "Table of Contents" for line in lines) or
                sum(bool(re.fullmatch(r".+?\s*\.{3,}\s*\d{1,3}\s*", line["text"]))
                    for line in lines) >= 6)
    tables = ([] if toc_page else sorted(
        (table for table in page.find_tables()
         if not _is_layout_artifact_table(table.bbox, page)),
        key=lambda table: table.bbox[1]))
    footnote_top = next((line["top"] for line in lines
                         if line["top"] > page.height * 0.66 and line["size"] <= 10.5
                         and FOOTNOTE.match(line["text"])), None)
    entries = []
    for index, table in enumerate(tables, 1):
        source_html, structured = _table_html(table)
        if not source_html:
            source_html = html.escape(_normal(
                page.crop(_bounded_bbox(table.bbox, page)).extract_text() or "[Table]"))
        box = {"x0": table.bbox[0], "top": table.bbox[1],
               "x1": table.bbox[2], "bottom": table.bbox[3]}
        image, image_hash = _save_crop(page, table.bbox, asset_dir, asset_prefix,
                                       "p%04d-table-%02d.png" % (page_number, index), table=True)
        entries.append({"kind": "table", "text": source_html, "top": box["top"],
                        "bbox": _bbox(box), "source_image": image,
                        "source_image_hash": image_hash,
                        "extraction_note": "表の行列構造を要確認" if not structured else "表と原本画像を照合してください"})
    images = sorted(page.images,
                    key=lambda image: (image["x0"], image["top"], image["x1"], image["bottom"]))
    for index, image in enumerate(images, 1):
        box = (image["x0"], image["top"], image["x1"], image["bottom"])
        if (box[0] >= page.width or box[2] <= 0 or
                box[1] >= page.height or box[3] <= 0):
            continue  # Embedded images outside the PDF page cannot be shown or cropped.
        if ((box[0] < 65 and box[2] - box[0] < page.width * 0.7) or
                box[1] < 68 or box[3] > page.height - 58 or
                (box[2] - box[0]) * (box[3] - box[1]) < 2500 or
                ((box[2] - box[0]) >= page.width * 0.6 and
                 (box[3] - box[1]) <= 15) or
                (box[0] > page.width * 0.8 and box[1] > page.height * 0.8)):
            continue  # Shallow, page-wide raster strips are separator/leader lines.
        area = (box[2] - box[0]) * (box[3] - box[1])
        if any(
                other is not image and
                other["x0"] <= box[0] and other["top"] <= box[1] and
                other["x1"] >= box[2] and other["bottom"] >= box[3] and
                (other["x1"] - other["x0"]) * (other["bottom"] - other["top"]) >= area * 1.2
                for other in images):
            continue  # Prefer a complete enclosing figure over its nested image layer.
        large_text_overlay = any(
            line["size"] >= 20 and line["bold_ratio"] >= 0.5 and
            max(0, min(line["x1"], box[2]) - max(line["x0"], box[0])) *
            max(0, min(line["bottom"], box[3]) - max(line["top"], box[1])) >= area * 0.2
            for line in lines)
        overlapping_text = []
        for line in lines:
            overlap = (max(0, min(line["x1"], box[2]) - max(line["x0"], box[0])) *
                       max(0, min(line["bottom"], box[3]) - max(line["top"], box[1])))
            if overlap >= area * 0.05:
                overlapping_text.append(overlap)
        if (large_text_overlay or
                (len(overlapping_text) >= 2 and sum(overlapping_text) >= area * 0.25)):
            continue  # The graphic is mostly text already extracted into separate blocks.
        url, image_hash = _save_crop(page, box, asset_dir, asset_prefix,
                                      "p%04d-figure-%02d.png" % (page_number, index))
        source_html = ('<img src="%s" alt="PDF原本のp.%dにある図">' %
                       (html.escape(url, quote=True), page_number)) if url else "[Figure]"
        entries.append({"kind": "figure", "text": source_html, "top": box[1],
                        "bbox": _bbox(image), "source_image_hash": image_hash,
                        "extraction_note": "図中の文字とキャプションを要確認"})
    for line in lines:
        if any(_inside(line, table.bbox) for table in tables):
            continue
        if toc_page:
            match = re.fullmatch(r"(.*?)\.{3,}\s*(\d{1,3})\s*", line["text"])
            if match:
                line["text"] = match.group(1).rstrip(" .") + " — " + match.group(2)
        kind = ("paragraph" if toc_page and line["text"] != "Table of Contents"
                else _kind(line, footnote_top))
        entries.append({"kind": kind, "text": line["text"],
                        "top": line["top"], "bbox": _bbox(line), "size": line["size"]})
    entries.sort(key=lambda item: (
        0 if toc_page and item.get("text") == "Table of Contents" else 1,
        0 if item.get("text", "").strip().upper() == "FOREWORD" else 1,
        item["top"], item["bbox"][0]))
    grouped = []
    for item in entries:
        if item["kind"] in {"table", "figure"} or toc_page:
            grouped.append(item)
            continue
        previous = grouped[-1] if grouped else None
        gap = item["bbox"][1] - previous["bbox"][3] if previous else 999
        same_column = (previous and
                       (abs(previous["bbox"][0] - item["bbox"][0]) <= 25 or
                        abs((previous["bbox"][0] + previous["bbox"][2]) / 2 -
                            (item["bbox"][0] + item["bbox"][2]) / 2) <= 30))
        wrapped_heading = (previous and previous["kind"] == item["kind"] == "heading"
                           and previous.get("size", 0) >= 20 and item.get("size", 0) >= 20
                           and same_column
                           and gap <= 16)
        heading_suffix = (previous and previous["kind"] == "heading" and
                          item["kind"] in {"heading", "paragraph"} and
                          same_column and gap <= 8 and
                          re.fullmatch(r"\([A-Z0-9.-]{1,20}\)\)?", item["text"]))
        same_kind = (previous and previous["kind"] == item["kind"] and
                     item["kind"] not in {"heading", "list_item"} and same_column)
        continuation = (previous and previous["kind"] in {"list_item", "note"}
                        and item["kind"] == "paragraph" and gap <= 7
                        and item["bbox"][0] >= previous["bbox"][0])
        starts_new_footnote = item["kind"] == "footnote" and FOOTNOTE.match(item["text"])
        merge_lines = (wrapped_heading or heading_suffix or (same_kind and gap <= 8) or
                       (continuation and gap <= 7))
        if merge_lines and not starts_new_footnote:
            previous["text"] = _join_lines(previous["text"], item["text"])
            previous["bbox"][2] = max(previous["bbox"][2], item["bbox"][2])
            previous["bbox"][3] = max(previous["bbox"][3], item["bbox"][3])
        else:
            grouped.append(item)
    return grouped


def parse_pdf_document(path, number, source_url, pages=None, asset_dir=None,
                       asset_prefix="assets"):
    """Extract ordered PDF blocks; ``pages`` is an optional 1-based page list."""
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError("PDF support requires pdfplumber; install requirements.txt") from error

    path = Path(path)
    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        selected = list(range(1, page_count + 1)) if pages is None else sorted(set(pages))
        if not selected or any(page < 1 or page > page_count for page in selected):
            raise ValueError("PDF pages must be within 1..%d" % page_count)
        blocks = []
        warnings = []
        text_characters = 0
        header_pages = defaultdict(set)
        lines_by_page = {physical_page: _text_lines(page)
                         for physical_page, page in enumerate(pdf.pages, start=1)}
        for physical_page, page_lines in lines_by_page.items():
            for line in page_lines:
                if line["top"] < 66:
                    header_pages[line["text"]].add(physical_page)
        running_headers = {text for text, header_pages_seen in header_pages.items()
                           if len(header_pages_seen) >= 2}
        for page_number in selected:
            page = pdf.pages[page_number - 1]
            readable = sum(char.get("upright", True) for char in page.chars)
            text_characters += readable
            if readable < 20:
                warnings.append("PDF p.%d: 抽出できる文字が少ないため OCR または画像の照合が必要" % page_number)
            if _has_parallel_columns(page, running_headers):
                warnings.append("PDF p.%d: 二段組の可能性があるため読み順を原本と照合してください" % page_number)
            items = _page_items(page, page_number, asset_dir, asset_prefix, running_headers)
            for index, item in enumerate(items, 1):
                kind = item["kind"]
                source_text = LIST_ITEM.sub("", item["text"], count=1) if kind == "list_item" else item["text"]
                source_html = source_text if kind in {"table", "figure"} else html.escape(source_text)
                image_hash = item.get("source_image_hash") or ""
                block = {
                    "id": "pdf-p%04d-b%04d" % (page_number, index),
                    "kind": kind,
                    "html": source_html,
                    "source_hash": hashlib.sha256((kind + "\n" + source_html + "\n" + image_hash)
                                                  .encode("utf-8")).hexdigest()[:16],
                    "html_ja": "",
                    "status": "untranslated",
                    "extraction_status": "needs_review",
                    "source_page": page_number,
                    "source_refs": [{"page": page_number, "bbox": item["bbox"]}],
                }
                if kind == "heading":
                    match = HEADING.match(item["text"])
                    block["level"] = min(match.group(1).count(".") + 1, 3) if match and match.group(1) else 1
                if kind == "list_item":
                    marker = LIST_ITEM.match(item["text"])
                    block["ordered"] = bool(marker.group(1))
                    block["ordinal"] = int(marker.group(1)) if marker.group(1) else None
                    block["depth"] = 0
                if item.get("source_image"):
                    block["source_image"] = item["source_image"]
                if image_hash:
                    block["source_image_hash"] = image_hash
                if item.get("extraction_note"):
                    block["extraction_note"] = item["extraction_note"]
                blocks.append(block)
        if not blocks or text_characters < 20:
            raise ValueError("PDF has no extractable body text; OCR and visual review are required")
        # A line may continue across a physical page break. Keep the first ID
        # and provenance for both pages so existing translations can be carried.
        for index in range(len(blocks) - 1, 0, -1):
            current = blocks[index]
            if current["kind"] != "paragraph" or current["source_page"] <= 1:
                continue
            previous = next((block for block in reversed(blocks[:index])
                             if block["source_page"] == current["source_page"] - 1
                             and block["kind"] != "footnote"), None)
            if (previous and previous["kind"] == "paragraph" and
                    (previous["html"].endswith("-") or
                     (current["html"] and current["html"][0].islower())) and
                    not any(block["source_page"] == current["source_page"] and
                            block["kind"] != "footnote" for block in blocks[:index]
                            if block is not previous)):
                previous["html"] = _join_lines(previous["html"], current["html"])
                previous["source_refs"].extend(current["source_refs"])
                previous["source_hash"] = hashlib.sha256(
                    ("paragraph\n" + previous["html"]).encode("utf-8")).hexdigest()[:16]
                del blocks[index]
        return {
            "title": {"text": "NIST " + number, "html_ja": ""},
            "number": number,
            "created_at": "",
            "updated_by": "",
            "source_format": "pdf",
            "source_url": source_url,
            "source_fetched_at": "",
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "pdf_page_count": page_count,
            "included_pages": selected,
            "extraction_partial": len(selected) != page_count,
            "extraction_warnings": warnings,
            "contents": blocks,
        }
