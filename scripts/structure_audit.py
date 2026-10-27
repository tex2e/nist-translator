"""Find merged and missing paragraphs by comparing blocks with the PDF text layer.

    python scripts/structure_audit.py KEY [--pages 140-160] [--out FILE]

The PDF's text layer is split into paragraphs: a new paragraph starts after a
vertical gap clearly larger than the line spacing, or where the font changes
between a bold heading line and body text. For every PDF paragraph the start
is looked up in the document's blocks (text normalised to letters and digits):

- ``merged``: the paragraph starts inside a block, not at its beginning, so
  two paragraphs (or a heading and a paragraph) share one block;
- ``missing``: the paragraph's start is found in no block.

Running heads, page numbers and the side note are skipped. This is a
detector: every finding is checked against the page image before a repair.
"""

import argparse
import html
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent


def norm(text):
    return re.sub(r"[^a-z0-9]", "", html.unescape(re.sub(r"<[^>]+>", " ", text)).lower())


def _lines(page):
    words = page.extract_words(extra_attrs=["fontname", "size"], keep_blank_chars=False, use_text_flow=True)
    lines = []
    for word in words:
        if word["x0"] < 60 or word["top"] < 60 or word["bottom"] > page.height - 50:
            continue  # side note, running head, page number
        if lines and abs(lines[-1]["top"] - word["top"]) < 3:
            line = lines[-1]
            line["words"].append(word)
            line["bottom"] = max(line["bottom"], word["bottom"])
        else:
            lines.append({"top": word["top"], "bottom": word["bottom"], "words": [word]})
    for line in lines:
        line["text"] = " ".join(word["text"] for word in line["words"])
        fonts = [word["fontname"] for word in line["words"]]
        line["bold"] = all("Bold" in font or "Arial" in font for font in fonts)
        line["x0"] = line["words"][0]["x0"]
        line["size"] = round(max(word["size"] for word in line["words"]))
    return lines


def paragraphs(page):
    lines = _lines(page)
    groups = []
    for index, line in enumerate(lines):
        if index:
            previous = lines[index - 1]
            gap = line["top"] - previous["bottom"]
            height = previous["bottom"] - previous["top"]
            # Footnotes are set smaller; each starts with its number.
            footnote = line["size"] < 11 and re.match(r"^\d+\s", line["text"]) is not None
            new = (gap > 0.45 * height or line["bold"] != previous["bold"] or footnote or
                   abs(line["size"] - previous["size"]) >= 2 or
                   re.match(r"^(\d+\.|[a-z]\.|•|\(\w\))\s", line["text"]) is not None)
        if not index or new:
            groups.append([])
        groups[-1].append(line)
    return [{"text": " ".join(line["text"] for line in group), "top": group[0]["top"],
             "heading": group[0]["bold"],
             "bbox": [round(min(w["x0"] for line in group for w in line["words"]), 1),
                      round(group[0]["top"], 1),
                      round(max(w["x1"] for line in group for w in line["words"]), 1),
                      round(group[-1]["bottom"], 1)]} for group in groups]


def audit(key, pages=None):
    document = json.loads((ROOT / "data" / (key + "-trans.json")).read_text())
    blocks = [block for block in document["contents"]
              if not block.get("page_furniture") and not block.get("duplicate_artifact_of")
              and not block.get("math_duplicate_of") and block["kind"] != "figure"]
    findings = []
    with pdfplumber.open(ROOT / "data" / (key + ".pdf")) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            if pages and number not in pages:
                continue
            near = [block for block in blocks
                    if any(abs(ref["page"] - number) <= 1 for ref in block.get("source_refs", []))]
            texts = [(block, norm(block["html"])) for block in near]
            for position, paragraph in enumerate(paragraphs(page)):
                # Blocks keep list items and footnotes without their marker.
                # A long probe: lists repeat their opening words ("Cryptoperiod:
                # Given the use of an approved algorithm ...") from item to item.
                probe = norm(re.sub(r"^(\d+\.?|[a-z]\.|•|\(\w\))\s+", "", paragraph["text"]))[:80]
                if len(probe) < 12:
                    continue
                hits = [(block, text.find(probe)) for block, text in texts if probe in text]
                # Prefer the blocks printed on this page over similar text nearby.
                here = [(block, offset) for block, offset in hits
                        if any(ref["page"] == number for ref in block.get("source_refs", []))]
                hits = here or hits
                if not hits:
                    findings.append({"page": number, "type": "missing", "text": paragraph["text"][:160]})
                elif all(offset > 3 for _, offset in hits):  # a footnote keeps its number
                    block, offset = hits[0]
                    starts_new = paragraph["heading"] or re.match(
                        r"^(\d+\.|[a-z]\.|•|\(\w\))\s", paragraph["text"]) is not None
                    if position == 0 and block["source_page"] < number and not starts_new:
                        continue  # the paragraph runs on from the page before
                    findings.append({"page": number, "type": "merged", "id": block["id"],
                                     "kind": block["kind"], "heading": paragraph["heading"],
                                     "offset": offset, "bbox": paragraph["bbox"],
                                     "text": paragraph["text"][:160]})
    return findings


def _pages(spec):
    pages = set()
    for part in spec.split(","):
        low, _, high = part.partition("-")
        pages.update(range(int(low), int(high or low) + 1))
    return pages


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("key")
    cli.add_argument("--pages", type=_pages)
    cli.add_argument("--out", type=Path)
    args = cli.parse_args()
    findings = audit(args.key, args.pages)
    counts = {}
    for item in findings:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    print(args.key, counts)
    if args.out:
        args.out.write_text(json.dumps(findings, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
