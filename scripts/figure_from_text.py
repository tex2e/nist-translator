"""Turn the text of a drawing that was extracted as body text back into a figure.

    python scripts/figure_from_text.py SPEC.json

Some PDFs draw their figures with vector graphics and real text, so the
extractor reads every label as a paragraph ("Back of", "65.5", ...). SPEC.json
lists ``[document key, first block id, last block id, caption block id]``
chosen by looking at the page. The blocks from first to last (in document
order, all on one page) are the figure's labels: they get ``page_furniture``
and ``figure_text_of`` so that they leave the body text but stay in the data.
A figure block with a crop of the original page takes their place. The crop
spans the text width, from just above the first label to just above the
caption, so that the lines and boxes of the drawing are included.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCALE = 2.0  # 144 dpi, as for the extractor's figure crops


def _crop(pdf, page_number, box, path):
    page = pdf[page_number - 1]
    width, height = page.get_size()
    left, top, right, bottom = box
    # pdfium crops by the distance from each edge: left, bottom, right, top.
    image = page.render(scale=SCALE, crop=(left, height - bottom, width - right, top)).to_pil()
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _caption_top(page, caption_html):
    """Where the caption ("Figure 9." ...) is printed, found in the PDF text."""
    match = re.match(r"\s*((?:Figure|Fig\.)\s*[A-Z]?\d+[.:])", re.sub(r"<[^>]+>", "", caption_html))
    if not match:
        return None
    label = match.group(1).replace(" ", "")
    words = page.extract_words()
    for index, word in enumerate(words):
        joined = "".join(item["text"] for item in words[index:index + 2]).replace(" ", "")
        if joined.startswith(label):
            return word["top"]
    return None


def _drawing_box(key, page_number, upper, caption_html):
    """The drawing printed just above its caption.

    Start from the graphics (lines, boxes, curves) nearest above the caption and
    take in further graphics upwards while the gap stays small, then the
    characters inside that area.
    """
    import pdfplumber
    with pdfplumber.open(str(ROOT / "data" / (key + ".pdf"))) as pdf:
        page = pdf.pages[page_number - 1]
        lower = _caption_top(page, caption_html)
        if lower is None:
            return None
        # Do not run into a figure printed above this one: stop below its caption.
        others = [word["bottom"] for word in page.extract_words()
                  if re.match(r"(Figure|Table)$", word["text"]) and word["bottom"] < lower - 2]
        upper = max([upper] + [bottom + 2 for bottom in others])
        graphics = sorted((item for item in page.lines + page.rects + page.curves
                           if item["bottom"] <= lower + 1 and item["top"] >= upper - 1 and
                           item["bottom"] - item["top"] < page.height * 0.9),
                          key=lambda item: -item["bottom"])
        if not graphics:
            return None
        top, bottom = graphics[0]["top"], graphics[0]["bottom"]
        if lower - bottom > 40:
            return None
        for item in graphics[1:]:
            if item["bottom"] < top - 24:
                break
            top = min(top, item["top"])
        chars = [item for item in page.chars if item["top"] >= top - 14 and item["bottom"] <= lower - 1]
        items = [item for item in graphics if item["top"] >= top - 1] + chars
    return [min(item["x0"] for item in items), min(item["top"] for item in items),
            max(item["x1"] for item in items), max(item["bottom"] for item in items)]


def main():
    import pypdfium2
    entries = json.loads(Path(sys.argv[1]).read_text())
    documents, pdfs = {}, {}
    for key, first, last, caption in entries:
        if key not in documents:
            documents[key] = json.loads((ROOT / "data" / (key + "-trans.json")).read_text())
            pdfs[key] = pypdfium2.PdfDocument(str(ROOT / "data" / (key + ".pdf")))
        document, contents = documents[key], documents[key]["contents"]
        ids = [block["id"] for block in contents]
        start, end = ids.index(first), ids.index(last)
        members = contents[start:end + 1]
        page_number = members[0]["source_page"]
        if any(block["source_page"] != page_number for block in members):
            raise ValueError("%s %s..%s spans pages" % (key, first, last))
        caption_block = contents[ids.index(caption)]
        caption_top = (caption_block["source_refs"][0]["bbox"][1]
                       if caption_block["source_page"] == page_number else None)
        # The drawing lies between the body text before it and its caption.
        before = [block for block in contents[:start]
                  if block.get("source_page") == page_number and not block.get("page_furniture")
                  and block["kind"] != "figure" and block.get("source_refs")]
        known = [ref["bbox"][3] for ref in (before[-1]["source_refs"] if before else [])
                 if ref["page"] == page_number and ref["bbox"][3] - ref["bbox"][1] < 600]
        box = _drawing_box(key, page_number, 60, caption_block["html"])
        if box is None:
            labels = [block["source_refs"][0]["bbox"] for block in members]
            box = [min(b[0] for b in labels), min(b[1] for b in labels) - 8,
                   max(b[2] for b in labels), max(b[3] for b in labels) + 8]
        top, bottom = box[1] - 6, box[3] + 2  # little room below: the caption follows closely
        width = pdfs[key][page_number - 1].get_size()[0]
        box = [60, max(0, top), width - 60, bottom]
        # Figures printed side by side share one crop: the labels of the second
        # go with the figure already made for the first.
        twin = next((block for block in contents if block.get("figure_from_text") is not None
                     and block["source_page"] == page_number and
                     block["source_refs"][0]["bbox"] == [round(value, 1) for value in box]), None)
        if twin is not None:
            twin["figure_from_text"] += [block["id"] for block in members]
            for block in members:
                block["page_furniture"] = True
                block["figure_text_of"] = twin["id"]
            print(key, twin["id"], "shares the crop with labels", len(members))
            continue
        number = sum(block.get("figure_from_text") is not None for block in contents
                     if block.get("source_page") == page_number) + 1
        name = "p%04d-drawing-%02d.png" % (page_number, number)
        slug = key  # FIPS asset folders are named after the key
        image_hash = _crop(pdfs[key], page_number, box, ROOT / "html" / "assets" / slug / name)
        figure_id = "pdf-p%04d-g%04d" % (page_number, number)
        html = '<img src="assets/%s/%s" alt="PDF原本のp.%dにある図">' % (slug, name, page_number)
        figure = {
            "id": figure_id, "kind": "figure", "html": html,
            "source_hash": hashlib.sha256(
                ("figure\n" + html + "\n" + image_hash).encode()).hexdigest()[:16],
            "html_ja": "", "status": "untranslated", "extraction_status": "needs_review",
            "source_page": page_number,
            "source_refs": [{"page": page_number, "bbox": [round(value, 1) for value in box]}],
            "source_image_hash": image_hash,
            "figure_from_text": [block["id"] for block in members],
            "extraction_note": "図の中の文字が本文として抽出されていたため、原本の図として切り出した",
        }
        for block in members:
            block["page_furniture"] = True
            block["figure_text_of"] = figure_id
        contents.insert(start, figure)
        print(key, figure_id, "labels", len(members), "box", [round(value) for value in box])
    for key, document in documents.items():
        (ROOT / "data" / (key + "-trans.json")).write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
