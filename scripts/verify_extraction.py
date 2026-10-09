"""Cross-check extracted PDF blocks against the original PDF.

A block is promoted to ``extraction_status=verified`` only when every gate
passes; anything with room for misreading stays ``needs_review``:

1. The local PDF matches the document's ``source_sha256``.
2. PDFium (an extractor independent of pdfplumber, which produced the blocks)
   yields exactly the same text for the block's page region.
3. The block is plain running text: no table, figure, footnote, page-spanning
   block, column-warning page, low-coverage page, scanned page, formula
   symbol, sub/superscript, neighbouring text on the same lines, or drawn
   graphics over the region.
4. The block is a complete unit: it does not look like a fragment of, or a
   merge with, an adjacent block.
5. OCR of the rendered page region (tesseract) agrees with the text, so a
   broken text layer cannot pass on the strength of two parsers reading it
   the same way.

Usage:
    python scripts/verify_extraction.py --pdf-dir DIR [--apply] [--calibrate] [KEY ...]
"""

import argparse
import ctypes
import difflib
import hashlib
import html
import json
import re
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_TAG = "pdfium+ocr"
TEXT_KINDS = {"paragraph", "heading", "list_item", "note"}
LIST_ITEM = re.compile(r"^(?:[•●▪]\s+|(\d+)\.\s+)")
TOC_ENTRY = re.compile(r"^.+ — (?:\d{1,3}|[ivxlc]{1,6}|[A-Z]-\d{1,2})$")
TAG = re.compile(r"<[^>]+>")
TERMINAL = re.compile(r"[.:;?!][\"'”’)\]]*$")
STARTS_OK = re.compile(r"^(?:[▪•●■]\s+)?[\"'“‘(\[]?[A-Z0-9]")
# Formula operators and letters whose extraction order/position is unreliable.
MATH = re.compile(r"[=^≡≤≥±×÷∑∏√∈∉⊕⊗≠≈∞∀∃∧∨¬→←↔⇒∥∙·Ͱ-Ͽ∀-⋿⟀-⟯]")


def _normal(text):
    return " ".join(text.replace("­", "").replace("ﬁ", "fi")
                   .replace("ﬂ", "fl").split())


def _leaders(text):
    """Table-of-contents dot leaders, whatever the spacing around them."""
    return re.sub(r"\s*\.{3,}\s*", " … ", text)


def _block_text(block):
    source = re.sub(r"<br\s*/?>", " ", block["html"])
    return _leaders(_normal(html.unescape(TAG.sub("", source))))


def _pdfium_text(raw, kind, toc):
    """Normalize PDFium's bounded text the way the parser normalizes lines."""
    text = raw.replace("\x02", "-").replace("￾", "-")
    lines = [_normal(line) for line in re.split(r"[\r\n]+", text)]
    lines = [line for line in lines if line]
    joined = ""
    for line in lines:
        if not joined:
            joined = line
        else:
            percent = joined.endswith("%") and re.match(r"^[0-9A-Fa-f]{2}", line)
            joined += ("" if joined.endswith("-") or percent else " ") + line
    if toc:
        match = re.fullmatch(r"(.*?)\.{3,}\s*(\S{1,6})\s*", joined)
        if match:
            joined = match.group(1).rstrip(" .") + " — " + match.group(2)
    if kind == "list_item":
        joined = LIST_ITEM.sub("", joined, count=1)
        # A bullet drawn with an unmapped symbol glyph, or a small "o" bullet.
        joined = re.sub(r"^(?:[\x00-\x1f\x80-\x9f\uf000-\uf8ff]|o(?= [A-Z]))\s*", "", joined, count=1)
    return _leaders(joined)


class PageData:
    """Characters and drawn objects of one PDF page in pdfplumber coordinates."""

    def __init__(self, page, pdfium_c):
        self.page = page
        self.width, self.height = page.get_size()
        self.rotation = page.get_rotation()
        box = page.get_mediabox()
        self.x_offset, self.y_top = box[0], box[3]
        self.textpage = page.get_textpage()
        self.chars = []
        left, right, bottom, top = (ctypes.c_double() for _ in range(4))
        origin_x, origin_y = ctypes.c_double(), ctypes.c_double()
        matrix = pdfium_c.FS_MATRIX()
        handle = self.textpage.raw
        name_buffer = ctypes.create_string_buffer(256)
        flags = ctypes.c_int()
        for index in range(self.textpage.count_chars()):
            code = pdfium_c.FPDFText_GetUnicode(handle, index)
            if pdfium_c.FPDFText_IsGenerated(handle, index) == 1:
                continue
            char = chr(code) if code else ""
            if not char or char.isspace():
                continue
            if not pdfium_c.FPDFText_GetCharBox(handle, index, left, right, bottom, top):
                continue
            pdfium_c.FPDFText_GetCharOrigin(handle, index, origin_x, origin_y)
            pdfium_c.FPDFText_GetFontInfo(handle, index, name_buffer, 256, flags)
            # The nominal font size is 1.0 when the text matrix does the
            # scaling, so combine both into the size actually painted.
            pdfium_c.FPDFText_GetMatrix(handle, index, matrix)
            self.chars.append({
                "text": char,
                "x0": left.value - self.x_offset, "x1": right.value - self.x_offset,
                "top": self.y_top - top.value, "bottom": self.y_top - bottom.value,
                "baseline": self.y_top - origin_y.value,
                "size": pdfium_c.FPDFText_GetFontSize(handle, index) *
                        (matrix.b ** 2 + matrix.d ** 2) ** 0.5,
                "font": name_buffer.value.decode("utf-8", "replace"),
                "upright": abs(pdfium_c.FPDFText_GetCharAngle(handle, index)) < 0.01,
            })
        self.graphics = []
        self.scanned = False
        page_area = self.width * self.height
        for obj in page.get_objects(max_depth=3):
            try:
                x0, y0, x1, y1 = obj.get_bounds()
            except Exception:
                continue
            width, height = x1 - x0, y1 - y0
            kind = obj.type
            if kind == 1:  # text
                continue
            if kind == 3 and width * height >= page_area * 0.5:
                self.scanned = True
            if width * height >= page_area * 0.8:
                continue  # page background
            self.graphics.append({
                "x0": x0 - self.x_offset, "x1": x1 - self.x_offset,
                "top": self.y_top - y1, "bottom": self.y_top - y0,
                "width": width, "height": height, "image": kind == 3,
            })

    def bounded_text(self, bbox, pad=1.0):
        x0, top, x1, bottom = bbox
        return self.textpage.get_text_bounded(
            left=x0 + self.x_offset - pad, bottom=self.y_top - bottom - pad,
            right=x1 + self.x_offset + pad, top=self.y_top - top + pad)


def _lines(chars):
    """Cluster characters into baselines."""
    lines = []
    for char in sorted(chars, key=lambda item: item["baseline"]):
        if lines and char["baseline"] - lines[-1][-1]["baseline"] <= 0.6:
            lines[-1].append(char)
        else:
            lines.append([char])
    return lines


def _layout_reasons(block, page, text):
    """Reasons a single block's region is not plain, self-contained text."""
    reasons = []
    x0, top, x1, bottom = block["source_refs"][0]["bbox"]
    inside, beside = [], []
    for char in page.chars:
        center_x = (char["x0"] + char["x1"]) / 2
        center_y = (char["top"] + char["bottom"]) / 2
        if not top - 1 <= center_y <= bottom + 1:
            continue
        if x0 - 1 <= center_x <= x1 + 1:
            inside.append(char)
        elif char["upright"]:
            beside.append(char)
    if not inside:
        return ["no_chars"], None
    if beside:
        reasons.append("neighbour_text")
    if any(not char["upright"] for char in inside):
        reasons.append("rotated_text")
    if block["kind"] == "footnote":
        # The raised reference number that opens a footnote is not a formula.
        body = statistics.median(char["size"] for char in inside)
        first = min(char["top"] for char in inside)
        start = min(char["x0"] for char in inside)
        marker = [char for char in inside
                  if char["text"].isdigit() and char["size"] < body - 0.6 and
                  char["top"] - first < body and char["x0"] - start < 14]
        inside = [char for char in inside if not any(char is other for other in marker)] or inside
    if block["kind"] == "list_item":
        # The bullet glyph is often set in another size and on another baseline.
        first = min(inside, key=lambda char: (round(char["top"] / 4), char["x0"]))
        if not first["text"].isalnum() and len(inside) > 1:
            inside = [char for char in inside if char is not first]
    sizes = [char["size"] for char in inside]
    size = statistics.median(sizes)
    if any(abs(value - size) > 0.6 for value in sizes):
        reasons.append("mixed_size")
    lines = _lines(inside)
    baselines = [statistics.median(char["baseline"] for char in line) for line in lines]
    steps = [b - a for a, b in zip(baselines, baselines[1:])]
    if any(step < 0.8 * size for step in steps):
        reasons.append("raised_or_lowered_text")
    elif steps and max(steps) > 1.2 * min(steps):
        reasons.append("uneven_line_spacing")
    for graphic in page.graphics:
        if (graphic["x1"] < x0 - 2 or graphic["x0"] > x1 + 2 or
                graphic["bottom"] < top - 2 or graphic["top"] > bottom + 2):
            # Vertical rules beside the block still indicate a table or box.
            # Rules far out in the margin are page furniture instead.
            if (graphic["width"] < 3 and graphic["height"] > 8 and
                    graphic["bottom"] > top and graphic["top"] < bottom and
                    x0 - 12 <= graphic["x0"] <= x1 + 12):
                reasons.append("vertical_rule")
                break
            continue
        if graphic["height"] < 3 and not graphic["image"]:
            continue  # link underline or horizontal rule
        reasons.append("graphics_overlap")
        break
    if MATH.search(text):
        reasons.append("math_symbol")
    if any(unicodedata.category(char) in {"Co", "Cc", "Cn", "Cs"} or char == "�"
           for char in text):
        reasons.append("bad_character")
    font = Counter((char["font"], round(char["size"], 1)) for char in inside).most_common(1)[0][0]
    return reasons, {"size": size, "font": font}


def _evaluate(document, pdf, held_pages, pdfium_c):
    """Return {block id: [reasons]} for every block; an empty list passes."""
    # Running headers and footers are not part of the reading flow.
    blocks = [block for block in document["contents"]
              if not block.get("duplicate_artifact_of") and not block.get("page_furniture")]
    by_page = {}
    for block in blocks:
        by_page.setdefault(block["source_page"], []).append(block)
    toc_pages = {page for page, items in by_page.items()
                 if sum(bool(TOC_ENTRY.match(_block_text(item))) for item in items) >= 4}
    results, info, texts = {}, {}, {}
    pages = {}
    for block in blocks:
        reasons = []
        text = texts[block["id"]] = _block_text(block)
        number = block["source_page"]
        if block["kind"] not in TEXT_KINDS and block["kind"] != "footnote":
            reasons.append("kind_" + block["kind"])
        if len(block["source_refs"]) != 1:
            reasons.append("page_spanning")
        if number in held_pages:
            reasons.append("page_" + held_pages[number])
        if not text:
            reasons.append("empty")
        if not reasons:
            if number not in pages:
                pages[number] = PageData(pdf[number - 1], pdfium_c)
            page = pages[number]
            if page.rotation:
                reasons.append("page_rotated")
            if page.scanned:
                reasons.append("page_scanned")
            raw = page.bounded_text(block["source_refs"][0]["bbox"])
            # A hyphen at a line end may be a compound or a word split by
            # hyphenation; the two cannot be told apart from the text alone.
            # PDFium rejoins such a word itself and marks the spot with U+0002.
            if ("\x02" in raw or "\ufffe" in raw or
                    re.search(r"[-\u2010\u2011][ \t]*[\r\n]+\s*\S", raw)):
                reasons.append("line_end_hyphen")
            other = _pdfium_text(raw, block["kind"], number in toc_pages)
            if other != text:
                reasons.append("text_mismatch")
            layout, details = _layout_reasons(block, page, text)
            reasons.extend(layout)
            if details:
                info[block["id"]] = details
        results[block["id"]] = reasons

    def gap(first, second):
        return second["source_refs"][0]["bbox"][1] - first["source_refs"][0]["bbox"][3]

    def overlaps(first, second):
        a, b = first["source_refs"][0]["bbox"], second["source_refs"][0]["bbox"]
        return min(a[3], b[3]) - max(a[1], b[1]) > 2

    for page_blocks in by_page.values():
        for first in page_blocks:
            if any(first is not second and overlaps(first, second) for second in page_blocks):
                results[first["id"]].append("side_by_side_block")

    flow = [block for block in blocks if block["kind"] != "footnote"]
    for index, block in enumerate(flow):
        if block["kind"] not in TEXT_KINDS:
            continue
        reasons = results[block["id"]]
        text = texts[block["id"]]
        size = info.get(block["id"], {}).get("size", 11)
        previous = flow[index - 1] if index else None
        following = flow[index + 1] if index + 1 < len(flow) else None
        same_page_prev = previous is not None and previous["source_page"] == block["source_page"]
        same_page_next = following is not None and following["source_page"] == block["source_page"]
        toc = block["source_page"] in toc_pages and bool(TOC_ENTRY.match(text))
        terminal = bool(TERMINAL.search(text))
        if block["kind"] != "list_item" and not STARTS_OK.match(text):
            reasons.append("starts_mid_sentence")
        if block["kind"] in {"paragraph", "note"} and not toc and not terminal:
            reasons.append("no_terminal_punctuation")
        if following is not None and following["kind"] in TEXT_KINDS:
            next_text = texts[following["id"]]
            if next_text[:1].islower() and following["kind"] != "list_item":
                reasons.append("next_continues")
        if block["kind"] == "list_item" and not terminal:
            if not same_page_next:
                reasons.append("list_item_open_at_page_end")
            elif following["kind"] != "list_item":
                reasons.append("list_item_open")
        if block["kind"] == "heading":
            if len(text) > 200:
                reasons.append("long_heading")
            if re.search(r"[.,;]$", text):
                reasons.append("heading_ends_like_sentence")
            if (same_page_next and following["kind"] in TEXT_KINDS and
                    gap(block, following) < 1.0 * size and
                    info.get(following["id"], {}).get("font") == info.get(block["id"], {}).get("font")):
                reasons.append("heading_split")
        if previous is not None and previous["kind"] in TEXT_KINDS:
            previous_text = texts[previous["id"]]
            previous_toc = (previous["source_page"] in toc_pages and
                            bool(TOC_ENTRY.match(previous_text)))
            previous_open = not previous_toc and not TERMINAL.search(previous_text)
            if previous["kind"] == "heading":
                if (same_page_prev and gap(previous, block) < 1.0 * size and
                        info.get(previous["id"], {}).get("font") == info.get(block["id"], {}).get("font")):
                    reasons.append("continues_heading")
            elif previous_open and (not same_page_prev or gap(previous, block) < 0.6 * size):
                # A heading in its own font at the top of a page starts a new unit.
                new_page_heading = (
                    not same_page_prev and block["kind"] == "heading" and
                    block["id"] in info and previous["id"] in info and
                    info[block["id"]]["font"] != info[previous["id"]]["font"])
                if not (previous["kind"] == "list_item" and block["kind"] == "list_item"
                        ) and not new_page_heading:
                    reasons.append("continues_previous")
    # A paragraph without closing punctuation is a complete unit (a label, a
    # title line, a list row) when the block after it starts afresh: a line
    # cut out of a running paragraph leaves its continuation right below it.
    for index, block in enumerate(flow):
        reasons = results[block["id"]]
        open_reasons = {"no_terminal_punctuation", "list_item_open"} & set(reasons)
        if not open_reasons:
            continue
        following = flow[index + 1] if index + 1 < len(flow) else None
        if following is None or (following["kind"] in TEXT_KINDS and not (
                {"continues_previous", "continues_heading", "starts_mid_sentence"} &
                set(results[following["id"]]))):
            for reason in open_reasons:
                reasons.remove(reason)
    return results, pages


def _ocr_words(page, cache_path):
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    scale = 200 / 72
    with tempfile.TemporaryDirectory() as folder:
        image = Path(folder) / "page.png"
        page.page.render(scale=scale, grayscale=True).to_pil().save(image)
        # Leptonica rewrites absolute /tmp paths, so pass a relative file name.
        output = subprocess.run(["tesseract", image.name, "stdout", "--psm", "3", "tsv"],
                                capture_output=True, check=True, cwd=folder
                                ).stdout.decode("utf-8", "replace")
    words = []
    for row in output.splitlines()[1:]:
        cells = row.split("\t")
        if len(cells) < 12 or cells[0] != "5" or not cells[11].strip():
            continue
        left, top, width, height = (int(cells[i]) / scale for i in (6, 7, 8, 9))
        words.append([left, top, left + width, top + height, cells[11]])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(words))
    return words


def _alnum(text):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).lower())


def _ocr_agrees(block, text, words):
    x0, top, x1, bottom = block["source_refs"][0]["bbox"]
    found = [word for word in words
             if x0 - 2 <= (word[0] + word[2]) / 2 <= x1 + 2 and
             top - 2 <= (word[1] + word[3]) / 2 <= bottom + 2]
    # Group the words into printed lines by their vertical centres, then read
    # each line left to right. Bucketing the centres on a fixed grid would
    # scatter the words of a line whose baseline jitters across a grid edge.
    found.sort(key=lambda word: (word[1] + word[3]) / 2)
    rows = []
    for word in found:
        centre = (word[1] + word[3]) / 2
        if rows and centre - rows[-1][0] <= 0.5 * max(word[3] - word[1], rows[-1][1]):
            rows[-1][2].append(word)
        else:
            rows.append([centre, word[3] - word[1], [word]])
    found = [word for row in rows for word in sorted(row[2], key=lambda item: item[0])]
    expected = text
    if block["kind"] == "list_item":
        seen = "".join(word[4] for word in found)
        seen = re.sub(r"^(?:[^A-Za-z0-9]{1,2}|\d+\.)", "", seen)
    else:
        seen = "".join(word[4] for word in found)
    expected, seen = _alnum(expected), _alnum(seen)
    if not expected:
        return False
    if block["kind"] == "list_item" and block.get("ordinal") is not None:
        prefix = str(block["ordinal"])
        if seen.startswith(prefix) and not expected.startswith(prefix):
            seen = seen[len(prefix):]
    entry = TOC_ENTRY.match(text)
    if entry:
        # OCR reads the dot leaders as junk: compare the title and the page label.
        title, _, label = text.rpartition(" — ")
        title, label = _alnum(title), _alnum(label)
        head = difflib.SequenceMatcher(None, title, seen[:len(title)], autojunk=False).ratio()
        return bool(title) and head >= 0.93 and seen.endswith(label)
    ratio = difflib.SequenceMatcher(None, expected, seen, autojunk=False).ratio()
    return ratio >= (0.93 if len(expected) >= 20 else 0.8)


def process(key, pdf_dir, cache_dir, apply, calibrate, held, keep=False):
    import pypdfium2
    import pypdfium2.raw as pdfium_c

    path = ROOT / "data" / (key + "-trans.json")
    document = json.loads(path.read_text())
    summary = {"key": key, "reasons": Counter(), "promoted": 0, "calibration": Counter()}
    if document.get("source_format") != "pdf":
        return summary
    # Re-running re-evaluates earlier automatic promotions under the current rules.
    reset = 0
    for block in document["contents"]:
        if block.get("extraction_check") == CHECK_TAG and not keep:
            del block["extraction_check"]
            block["extraction_status"] = "needs_review"
            reset += 1
    pending = [block for block in document["contents"]
               if block.get("extraction_status") == "needs_review"]
    if not pending and not calibrate:
        return summary
    pdf_path = Path(pdf_dir) / (key + ".pdf")
    if (not pdf_path.exists() or
            hashlib.sha256(pdf_path.read_bytes()).hexdigest() != document.get("source_sha256")):
        summary["reasons"]["pdf_missing_or_sha_mismatch"] = len(pending)
        return summary
    held_pages = dict(held)
    for warning in document.get("extraction_warnings", []):
        match = re.match(r"PDF p\.(\d+): (二段組|抽出できる文字が少ない)", warning)
        if match:
            held_pages.setdefault(int(match.group(1)),
                                  "column_warning" if match.group(2) == "二段組" else "low_text")
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    if len(pdf) != document.get("pdf_page_count"):
        summary["reasons"]["page_count_mismatch"] = len(pending)
        return summary
    results, pages = _evaluate(document, pdf, held_pages, pdfium_c)
    changed = False
    for block in document["contents"]:
        reasons = results.get(block["id"])
        if reasons is None:
            continue
        current = block.get("extraction_status")
        if current != "needs_review" and not calibrate:
            continue
        if not reasons:
            words = _ocr_words(pages[block["source_page"]],
                               Path(cache_dir) / key / ("p%04d.json" % block["source_page"]))
            if not _ocr_agrees(block, _block_text(block), words):
                reasons = ["ocr_disagrees"]
        if calibrate:
            summary["calibration"][(current, "pass" if not reasons else "hold")] += 1
            if current == "needs_review" and not reasons:
                summary.setdefault("examples", []).append(
                    (block["id"], block["kind"], _block_text(block)[:110]))
        if current != "needs_review":
            continue
        if reasons:
            summary["reasons"].update(set(reasons))
            continue
        summary["promoted"] += 1
        if apply:
            block["extraction_status"] = "verified"
            block["extraction_check"] = CHECK_TAG
            changed = True
    if apply and reset and not changed:
        changed = True  # every earlier promotion was withdrawn
    if apply:
        # A translation review does not stand on a source that is unverified again.
        for block in document["contents"]:
            if (block.get("extraction_status") == "needs_review" and
                    block.get("translation_check")):
                if block.get("status") == "reviewed":
                    block["status"] = "draft"
                del block["translation_check"]
                block.pop("translation_fix_rounds", None)
                summary["reasons"]["translation_review_withdrawn"] += 1
                changed = True
    if changed:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return summary


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("keys", nargs="*", help="document keys such as sp800-89 (default: all)")
    cli.add_argument("--pdf-dir", type=Path, default=ROOT / "data")
    cli.add_argument("--cache-dir", type=Path, default=Path(tempfile.gettempdir()) / "nist-ocr-cache")
    cli.add_argument("--apply", action="store_true", help="write verified status to the JSON files")
    cli.add_argument("--calibrate", action="store_true",
                     help="also evaluate blocks that already have a status and report agreement")
    cli.add_argument("--keep", action="store_true",
                     help="leave earlier automatic promotions as they are instead of re-evaluating them")
    args = cli.parse_args()
    keys = args.keys or sorted(path.name[:-len("-trans.json")]
                               for path in (ROOT / "data").glob("*-trans.json"))
    held = {}
    candidates = ROOT / "reports" / "page-coverage-candidates.json"
    if candidates.exists():
        for item in json.loads(candidates.read_text()):
            held.setdefault(item["document_key"], {})[item["page"]] = "low_coverage"
    total, promoted, calibration = Counter(), 0, Counter()
    for key in keys:
        summary = process(key, args.pdf_dir, args.cache_dir, args.apply,
                          args.calibrate, held.get(key, {}), args.keep)
        total.update(summary["reasons"])
        promoted += summary["promoted"]
        calibration.update(summary["calibration"])
        if summary["promoted"] or summary["reasons"] or summary["calibration"]:
            print("%-22s promoted=%-5d %s" % (summary["key"], summary["promoted"],
                                              dict(summary["calibration"]) or ""), flush=True)
        for example in summary.get("examples", []):
            print("   PASS-BUT-HELD", *example)
    print("promoted:", promoted, "(applied)" if args.apply else "(dry run)")
    if calibration:
        print("calibration:", dict(calibration))
    for reason, count in total.most_common():
        print("  %-28s %d" % (reason, count))


if __name__ == "__main__":
    sys.exit(main())
