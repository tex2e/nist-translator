"""Re-extract multi-column PDFs column by column.

The general parser reads a page top to bottom, so on a page set in columns it
interleaves the lines of neighbouring columns and joins lines that share a
baseline. This script reads such documents again: it finds the gutters of each
page, splits lines at them, orders the text band by band and column by column,
and groups lines into paragraphs. Figures and tables keep their existing
blocks. Every new block starts as ``needs_review`` and untranslated.

Usage:
    python scripts/reflow_columns.py KEY [--pages 12,40-42] [--apply]
"""

import argparse
import hashlib
import html
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.pdf_parser import (  # noqa: E402
    LIST_ITEM, _bold_ratio, _kind, _normal, _size, _text_lines)

WORDS = set()
for _path in ("/usr/share/dict/words",):
    if Path(_path).exists():
        WORDS = {word.strip().lower() for word in Path(_path).read_text().split()}
BULLET = re.compile(r"^[•●▪■◆»\x80-\x9f\uf000-\uf8ff]\s*")
MARKER = re.compile(r"(?:\d{1,2}[.)]|[a-z][.)]|[•●▪■◆»\x80-\x9f\uf000-\uf8ff])")
LEADER = re.compile(r"\.{4,}\s*[0-9ivxlc]{1,4}$")
TERMINAL = re.compile(r"[.:;?!][\"'”’)\]]*$")


LIGATURE = "\x00"


def _stems(word):
    word = word.lower()
    return {word, re.sub(r"(?:s|es|ed|ing|ly|d|er|ers)$", "", word), re.sub(r"ies$", "y", word),
            re.sub(r"ied$", "y", word), re.sub(r"ing$", "e", word), re.sub(r"ed$", "e", word),
            re.sub(r"^(?:un|re|non|pre|mis|over|under)", "", word)}


def _known(word):
    return bool(WORDS & _stems(word))


def _text(chars, narrow=None):
    """Text of one line; a too-wide ``f`` is a ligature the font maps to plain f."""
    parts, previous, seen = [], None, set()
    # Letters sit at a usual gap: zero, a tracking value, or an overlap where
    # the recorded widths are too large (the same font name can carry both).
    # A space is clearly wider than the letter gaps around it, so each gap is
    # judged against the median of its neighbours.
    gaps = [b["x0"] - a["x1"] for a, b in zip(chars, chars[1:])]
    limits = []
    for index in range(len(gaps)):
        near = sorted(gaps[max(0, index - 4):index + 5])
        base = near[len(near) // 2]
        if len(near) < 5:
            whole = sorted(gaps)
            base = min(base, whole[len(whole) // 2])
        limits.append(1.8 * base if base > 1.0 else base + 1.0)
    whole = sorted(gaps)
    if len(gaps) >= 20 and all(gap <= limit for gap, limit in zip(gaps, limits)):
        base = whole[len(whole) // 2]
        if whole[-1] - base > 0.25:  # a line squeezed to fit: its widest gaps are the spaces
            limits = [base + 0.5 * (whole[-1] - base)] * len(gaps)
    overlapping = [gap < -1.0 for gap in gaps]
    for index, char in enumerate(chars):
        position = (round(char["x0"], 2), round(char["top"], 2), char["text"])
        if position in seen:
            continue
        seen.add(position)
        if previous and index and gaps[index - 1] > limits[index - 1]:
            parts.append(" ")
        width = char["x1"] - char["x0"]
        ratio = width / (char["size"] or 10)
        base = (narrow or {}).get((char.get("fontname"), round(char["size"], 1)))
        inflated = any(overlapping[max(0, index - 2):index + 2])  # widths here are not real
        if char["text"] == "f" and ratio > 0.45 and base and width > 1.45 * base and not inflated:
            parts.append(LIGATURE + ("3" if ratio > 0.75 else "2" if ratio > 0.6 else "1"))
        else:
            parts.append(char["text"])
        previous = char
    return _normal("".join(parts))


CLASSES = {"1": ("fi", "fl"), "2": ("ff",), "3": ("ffi", "ffl")}


def _resolve(text):
    """Replace ligature placeholders, choosing the spelling that makes a word."""
    guesses = []

    def word(match):
        token = match.group(0)
        slots = re.findall(LIGATURE + r"([123])", token)
        options = [[]]
        for slot in slots:
            options = [head + [tail] for head in options for tail in CLASSES[slot]]
        best = None
        for index, option in enumerate(options):
            candidate = token
            for piece in option:
                candidate = re.sub(LIGATURE + r"[123]", piece, candidate, count=1)
            if index == 0:
                first = candidate
            if all(_known(part) for part in re.findall(r"[A-Za-z]+", candidate) if len(part) > 2):
                best = candidate
                break
        if best is None:
            best = first
            if len(options) > 1:
                guesses.append(best)
        return best

    pattern = r"[A-Za-z%s123]*%s[123][A-Za-z%s123]*" % (LIGATURE, LIGATURE, LIGATURE)
    return re.sub(pattern, word, text), guesses


def _fragment(line, chars):
    box = {"x0": min(c["x0"] for c in chars), "x1": max(c["x1"] for c in chars),
           "top": min(c["top"] for c in chars), "bottom": max(c["bottom"] for c in chars)}
    item = {**line, **box, "chars": chars, "text": _text(chars, line.get("narrow", {}))}
    item["size"], item["bold_ratio"] = _size(item), _bold_ratio(item)
    item["italic_ratio"] = (sum("italic" in c.get("fontname", "").lower() or
                                "oblique" in c.get("fontname", "").lower() for c in chars) / len(chars))
    item["font"] = max(set(c.get("fontname", "") for c in chars),
                       key=[c.get("fontname", "") for c in chars].count)
    return item


def _gutters(lines, width):
    """x positions of column gutters: bands that almost no line of text enters."""
    body = [line for line in lines if len(line["text"]) >= 12]
    if len(body) < 10:
        return []
    covered = [0] * (int(width) + 2)
    for line in body:
        chars = sorted(line["chars"], key=lambda c: c["x0"])
        spans, start, end = [], chars[0]["x0"], chars[0]["x1"]
        for char in chars[1:]:
            if char["x0"] - end > 7:
                spans.append((start, end))
                start = char["x0"]
            end = max(end, char["x1"])
        spans.append((start, end))
        for x0, x1 in spans:
            for x in range(max(0, int(x0)), min(len(covered), int(x1) + 1)):
                covered[x] += 1
    limit = max(1, len(body) * 0.12)
    runs, start = [], None
    for x in range(int(width * 0.15), int(width * 0.85)):
        free = covered[x] <= limit
        if free and start is None:
            start = x
        if not free and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, int(width * 0.85)))
    found = []
    for x0, x1 in runs:
        if x1 - x0 < 7:
            continue
        middle = (x0 + x1) / 2
        left = sum(line["x1"] <= middle + 2 for line in body)
        right = sum(line["x0"] >= middle - 2 for line in body)
        split = sum(line["x0"] < x0 and line["x1"] > x1 and
                    not any(c["x0"] < x1 and c["x1"] > x0 for c in line["chars"]) for line in body)
        if left + split >= 5 and right + split >= 5:
            found.append(middle)
    return found


def _split(lines, gutters, height):
    result = []
    for line in lines:
        parts, chars = [], sorted(line["chars"], key=lambda c: c["x0"])
        current = [chars[0]]
        margin = line["top"] < 0.1 * height or line["bottom"] > 0.9 * height
        for char in chars[1:]:
            gap = char["x0"] - current[-1]["x1"]
            crossed = (margin and gap > 12) or any(
                current[-1]["x1"] <= g + 3 and char["x0"] >= g - 3 and gap > 5 for g in gutters)
            if crossed:
                parts.append(current)
                current = []
            current.append(char)
        parts.append(current)
        for index, part in enumerate(parts):
            item = _fragment(line, part)
            item["after_gap"] = index > 0
            if item["text"]:
                result.append(item)
    return result


def _column(line, gutters):
    """Column index, or None for a line that runs across a gutter."""
    if any(line["x0"] < g - 4 and line["x1"] > g + 4 for g in gutters):
        return None
    middle = (line["x0"] + line["x1"]) / 2
    return sum(middle > g for g in gutters)


def _ordered(lines, gutters):
    """Reading order: bands between full-width lines, then column by column."""
    lines = sorted(lines, key=lambda line: (line["top"], line["x0"]))
    bands, band = [], []
    for line in lines:
        column = _column(line, gutters)
        line["column"] = column
        if column is None:
            if band:
                bands.append(band)
            bands.append([line])
            band = []
        else:
            band.append(line)
    if band:
        bands.append(band)
    ordered = []
    for band in bands:
        for column in sorted({line["column"] or 0 for line in band}):
            ordered.extend(_cells([line for line in band if (line["column"] or 0) == column]))
    return ordered


def _cells(lines):
    """Lines of one column; cells set side by side inside it are read one after the other."""
    lines = sorted(lines, key=lambda line: (line["top"], line["x0"]))
    width = max(line["x1"] for line in lines) - min(line["x0"] for line in lines)
    for marker in [line for line in lines if MARKER.fullmatch(line["text"])]:
        row = [line for line in lines if line is not marker and line["x0"] > marker["x1"] and
               min(line["bottom"], marker["bottom"]) - max(line["top"], marker["top"]) >
               0.5 * (marker["bottom"] - marker["top"])]
        if row:
            target = min(row, key=lambda line: line["x0"])
            target["text"] = marker["text"] + " " + target["text"]
            target["x0"] = marker["x0"]
            target["marker_x1"] = marker["x1"]
            lines = [line for line in lines if line is not marker]

    def partner(index):
        line = lines[index]
        for other in lines[max(0, index - 3):index + 4]:
            overlap = min(line["bottom"], other["bottom"]) - max(line["top"], other["top"])
            if (other is not line and overlap > 0.5 * (line["bottom"] - line["top"]) and
                    abs(other["size"] - line["size"]) <= 0.6 and
                    max(other["x1"] - other["x0"], line["x1"] - line["x0"]) < 0.6 * width):
                if other["x0"] > line["x1"] + 10 or line["x0"] > other["x1"] + 10:
                    return other
        return None

    result, index = [], 0
    while index < len(lines):
        other = partner(index)
        if other is None:
            result.append(lines[index])
            index += 1
            continue
        edge = max(lines[index]["x0"], other["x0"]) - 4
        left, right = [], []
        while index < len(lines):
            item = lines[index]
            placed = left + right
            if placed:
                last = max(entry["bottom"] for entry in placed)
                if item["top"] - last > 0.9 * (item["size"] or 10) or item["x0"] < edge < item["x1"]:
                    break
                if item["x0"] >= edge and partner(index) is None and not right:
                    break
            (right if item["x0"] >= edge else left).append(item)
            index += 1
        for item in right:
            item["column"] = (item["column"] or 0) + 0.5
        result.extend(left + right)
    return result


def _join(left, right):
    if left.endswith("-") and right[:1].islower():
        head = re.search(r"([A-Za-z%s123]+)-$" % LIGATURE, left)
        tail = re.match(r"[a-z%s123]+" % LIGATURE, right)
        if head and tail:
            word, guesses = _resolve(head.group(1) + tail.group(0))
            # A word split by hyphenation; a compound keeps its printed hyphen.
            if not guesses and _known(word):
                return left[:-1] + right
        return left + right
    if re.search(r"\S[-_/]$", left) and not re.search(r"\s[-–—]$", left):
        return left + right  # a printed hyphen, underscore or slash at the line end
    if re.search(r"https?://\S*[/._-]$", left) and re.match(r"^\S+$", right.split(" ")[0]) \
            and not right[:1].isupper():
        return left + right  # URL wrapped inside itself
    return left + " " + right


def _paragraphs(lines, page_height):
    """Group ordered lines of one page into blocks."""
    blocks = []
    footnote_top = None
    for line in lines:
        if len(line["text"]) <= 2 and not re.search(r"[A-Za-z0-9]", line["text"]):
            continue  # an ornament
        kind = _kind(line, footnote_top)
        if BULLET.match(line["text"]):
            kind = "list_item"
        previous = blocks[-1] if blocks else None
        last = previous["lines"][-1] if previous else None
        same_column = last is not None and last.get("column") == line.get("column")
        gap = line["top"] - last["bottom"] if last else 999
        size = line["size"] or 10
        same_style = (last is not None and abs(last["size"] - line["size"]) <= 0.6 and
                      (previous["kind"] != "heading" or line["bold_ratio"] >= 0.5))
        merge = False
        all_bold = previous is not None and all(item["bold_ratio"] >= 0.9 for item in previous["lines"])
        if all_bold and line["bold_ratio"] < 0.5 and sum(len(i["text"]) for i in previous["lines"]) < 200:
            same_style = False  # a run-in heading above its paragraph
            previous["kind"] = "heading" if previous["kind"] == "paragraph" else previous["kind"]
        if (previous and not all_bold and line["bold_ratio"] >= 0.9 and last["bold_ratio"] < 0.5 and
                (TERMINAL.search(last["text"]) or
                 last["x1"] < max(item["x1"] for item in previous["lines"]) - 30 or
                 re.search(r"https?://\S+$", last["text"]))):
            same_style = False  # a heading right below the end of a paragraph
        if last is not None and LEADER.search(last["text"]):
            same_style = False  # a table-of-contents entry ends at its page number
        if previous and same_column and same_style and -2 <= gap <= 0.75 * size:
            first = previous["lines"][0]
            left = min(item["x0"] for item in previous["lines"][1:]) if len(previous["lines"]) > 1 else None
            indented = line["x0"] - (left if left is not None else first["x0"]) > 5
            starts_item = kind == "list_item" or BULLET.match(line["text"])
            short_last = last["x1"] < max(item["x1"] for item in previous["lines"]) - 0.25 * (
                max(item["x1"] for item in previous["lines"]) - min(item["x0"] for item in previous["lines"]))
            if previous["kind"] == "heading" or all_bold:
                merge = kind == "heading" or (line["bold_ratio"] >= 0.5 and len(line["text"]) < 80)
            elif starts_item:
                merge = False
            elif previous["kind"] == "list_item":
                merge = line["x0"] >= first["x0"] + 3 or len(previous["lines"]) > 1 and abs(line["x0"] - left) < 3
            elif len(previous["lines"]) == 1:
                # second line: an outdent after a first-line indent, or flush
                merge = line["x0"] <= first["x0"] + 3 or (first["x0"] - line["x0"]) > 0
                if indented and TERMINAL.search(last["text"]):
                    merge = False
            else:
                merge = not (indented and (TERMINAL.search(last["text"]) or short_last))
                if short_last and TERMINAL.search(last["text"]) and gap > 0.35 * size:
                    merge = False
        if merge:
            previous["lines"].append(line)
        else:
            blocks.append({"kind": kind, "lines": [line]})
    result = []
    for block in blocks:
        text = ""
        for line in block["lines"]:
            text = line["text"] if not text else _join(text, line["text"])
        box = [round(min(l["x0"] for l in block["lines"]), 1), round(min(l["top"] for l in block["lines"]), 1),
               round(max(l["x1"] for l in block["lines"]), 1), round(max(l["bottom"] for l in block["lines"]), 1)]
        text, guesses = _resolve(text)
        lines = block["lines"]
        left = min(l["x0"] for l in lines[1:]) if len(lines) > 1 else None
        result.append({"kind": block["kind"], "text": text, "bbox": box,
                       "column": lines[0].get("column"), "guesses": guesses,
                       "first_x0": lines[0]["x0"], "body_x0": left, "last_x1": lines[-1]["x1"],
                       "bold": lines[0]["bold_ratio"] >= 0.5,
                       "size": statistics.median(l["size"] for l in lines)})
    return result


def page_blocks(page, number, keep):
    """New text blocks of one page; ``keep`` are existing figure/table blocks."""
    boxes = [ref["bbox"] for block in keep for ref in block["source_refs"] if ref["page"] == number]
    lines = []
    for line in _text_lines(page):
        if not line.get("chars"):
            continue
        middle = ((line["x0"] + line["x1"]) / 2, (line["top"] + line["bottom"]) / 2)
        if any(b[0] - 2 <= middle[0] <= b[2] + 2 and b[1] - 2 <= middle[1] <= b[3] + 2 for b in boxes):
            continue
        lines.append(line)
    narrow = {}
    for line in lines:
        for char in line["chars"]:
            if char["text"] == "f":
                key = (char.get("fontname"), round(char["size"], 1))
                narrow[key] = min(narrow.get(key, 99), char["x1"] - char["x0"])
    for line in lines:
        line["narrow"] = narrow
    gutters = _gutters(lines, page.width)
    lines = _split(lines, gutters, page.height)
    body = [line for line in lines if len(line["text"]) >= 30]
    numbers = []
    if body:
        left, right = min(line["x0"] for line in body), max(line["x1"] for line in body)
        for line in lines:
            if (re.fullmatch(r"[\divxlc ]{1,7}", line["text"]) and
                    (line["x1"] < left or line["x0"] > right or
                     line["top"] < 0.1 * page.height or line["bottom"] > 0.9 * page.height)):
                numbers.append(line)  # a page number in a margin
    lines = _ordered([line for line in lines if not any(line is n for n in numbers)], gutters)
    blocks = _paragraphs(lines, page.height)
    for line in numbers:
        blocks.append({"kind": "paragraph", "text": line["text"], "bbox": [
            round(line["x0"], 1), round(line["top"], 1), round(line["x1"], 1), round(line["bottom"], 1)],
            "column": None, "guesses": [], "first_x0": line["x0"], "body_x0": None,
            "last_x1": line["x1"], "bold": False, "size": line["size"], "page_number": True})
    return blocks, gutters


def _mark_furniture(blocks, pages):
    """Running headers, footers and page numbers: recurring short texts in a margin."""
    groups = {}
    for block in blocks:
        if "_geometry" not in block:
            continue
        text = html.unescape(block["html"]).strip()
        box, height = block["source_refs"][0]["bbox"], block["_geometry"][5]
        if len(text) <= 200 and (box[3] < 0.1 * height or box[1] > 0.9 * height):
            groups.setdefault(re.sub(r"\d+", "#", text), []).append(block)
    for members in groups.values():
        if len(members) >= 3:
            for block in members:
                block["page_furniture"] = True


def _continuations(blocks):
    """Join a paragraph that runs on into the next column or page."""
    result = []
    edges = {}
    for block in blocks:
        if "_geometry" in block and not block.get("page_furniture"):
            key = (block["source_page"], block["column_reflow"]["column"])
            box = block["source_refs"][0]["bbox"]
            left, right = edges.get(key, (999, 0))
            edges[key] = (min(left, box[0]), max(right, box[2]))
    for block in blocks:
        previous = next((item for item in reversed(result) if not item.get("page_furniture")), None)
        if (previous is not None and "_geometry" in block and "_geometry" in previous and
                not block.get("page_furniture") and block["kind"] == "paragraph" and
                previous["kind"] in {"paragraph", "list_item"}):
            here = (block["source_page"], block["column_reflow"]["column"])
            last_ref = previous["source_refs"][-1]
            there = (last_ref["page"], previous["_last_column"] if "_last_column" in previous
                     else previous["column_reflow"]["column"])
            first_x0, _, _, size, bold, _ = block["_geometry"]
            previous_first, previous_body, last_x1, previous_size, previous_bold, _ = previous["_geometry"]
            left, right = edges[here]
            previous_left, previous_right = edges.get(there, (0, 0))
            text, previous_text = html.unescape(block["html"]), html.unescape(previous["html"])
            full_line = last_x1 >= previous_right - 0.12 * (previous_right - previous_left)
            if (here != there and here[1] is not None and there[1] is not None and
                    abs(size - previous_size) <= 0.6 and bold == previous_bold and
                    not TERMINAL.search(previous_text) and full_line and
                    (first_x0 - left < 4 or text[:1].islower() or
                     (previous_body is not None and
                      abs((first_x0 - left) - (previous_body - previous_left)) < 4)) and
                    not BULLET.match(text) and
                    (text[:1].islower() or not re.search(r"https?://\S+$", previous_text))):
                previous["html"] = html.escape(_join(previous_text, text))
                previous["source_hash"] = hashlib.sha256(
                    (previous["kind"] + "\n" + previous["html"] + "\n").encode()).hexdigest()[:16]
                previous["source_refs"].append(block["source_refs"][0])
                previous["_last_column"] = here[1]
                previous["_geometry"] = previous["_geometry"][:2] + (block["_geometry"][2],) + previous["_geometry"][3:]
                guesses = block["column_reflow"].get("ligature_guesses")
                if guesses:
                    previous["column_reflow"].setdefault("ligature_guesses", []).extend(guesses)
                continue
        result.append(block)
    for block in result:
        block.pop("_last_column", None)
    return result


def _pages(value, count):
    if not value:
        return list(range(1, count + 1))
    pages = set()
    for part in value.split(","):
        first, _, last = part.partition("-")
        pages.update(range(int(first), int(last or first) + 1))
    return sorted(pages)


def main():
    import pdfplumber
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("key")
    cli.add_argument("--pages")
    cli.add_argument("--apply", action="store_true")
    args = cli.parse_args()
    path = ROOT / "data" / (args.key + "-trans.json")
    document = json.loads(path.read_text())
    old = document["contents"]
    with pdfplumber.open(str(ROOT / "data" / (args.key + ".pdf"))) as pdf:
        selected = _pages(args.pages, len(pdf.pages))
        kept = [block for block in old
                if block["kind"] in {"figure", "table"} and not block.get("page_furniture")]
        new, by_page = [], {}
        for number in selected:
            keep = [block for block in kept if block["source_page"] == number]
            items, gutters = page_blocks(pdf.pages[number - 1], number, keep)
            entries = [(item["bbox"][1], item["column"], None, item) for item in items]
            page_new = []
            for index, item in enumerate(items, 1):
                kind = item["kind"]
                text = item["text"]
                if kind == "list_item":
                    text = BULLET.sub("", LIST_ITEM.sub("", text, count=1), count=1)
                source = html.escape(text)
                block = {"id": "pdf-p%04d-c%04d" % (number, index), "kind": kind, "html": source,
                         "source_hash": hashlib.sha256((kind + "\n" + source + "\n").encode()).hexdigest()[:16],
                         "html_ja": "", "status": "untranslated", "extraction_status": "needs_review",
                         "source_page": number, "source_refs": [{"page": number, "bbox": item["bbox"]}],
                         "column_reflow": {"column": item["column"], "gutters": [round(g, 1) for g in gutters]}}
                if item.get("page_number"):
                    block["page_furniture"] = True
                if item["guesses"]:
                    block["column_reflow"]["ligature_guesses"] = item["guesses"]
                block["_geometry"] = (item["first_x0"], item["body_x0"], item["last_x1"], item["size"],
                                      item["bold"], pdf.pages[number - 1].height)
                if kind == "heading":
                    block["level"] = 2 if item["size"] < 16 else 1
                if kind == "list_item":
                    marker = LIST_ITEM.match(item["text"])
                    block["ordered"] = bool(marker and marker.group(1))
                    block["ordinal"] = int(marker.group(1)) if marker and marker.group(1) else None
                    block["depth"] = 0
                page_new.append(block)
            # Existing figures and tables go after the last text block above them in their column.
            for block in keep:
                box = block["source_refs"][0]["bbox"]
                column = sum((box[0] + box[2]) / 2 > g for g in gutters)
                wide = any(box[0] < g - 4 and box[2] > g + 4 for g in gutters)
                position = 0
                for index, other in enumerate(page_new):
                    if other["kind"] in {"figure", "table"} and other in keep:
                        other_box, other_column = other["source_refs"][0]["bbox"], None
                    else:
                        other_box, other_column = other["source_refs"][0]["bbox"], other["column_reflow"]["column"]
                    before = other_box[1] < box[1] if (wide or other_column is None or other_column == column) \
                        else other_column < column
                    if before:
                        position = index + 1
                page_new.insert(position, block)
            by_page[number] = page_new
            new.extend(page_new)
    _mark_furniture(new, len(selected))
    new = _continuations(new)
    for block in new:
        block.pop("_geometry", None)
    if not args.apply:
        for block in new:
            if block.get("page_furniture"):
                continue
            print("%s %-9s col=%s %s" % (block["id"], block["kind"],
                                         block.get("column_reflow", {}).get("column", "-"), block["html"][:2000]))
            print()
        return
    if args.pages:
        raise SystemExit("--apply rewrites the whole document; omit --pages")
    document["contents"] = new
    document["column_reflow"] = {"method": "gutter_split_column_order",
                                 "replaced_blocks": len(old), "blocks": len(new)}
    document["extraction_warnings"] = [w for w in document.get("extraction_warnings", [])
                                       if not (isinstance(w, str) and "二段組" in w)]
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(args.key, "blocks", len(old), "->", len(new))


if __name__ == "__main__":
    main()
