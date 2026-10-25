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
        top = min(block["source_refs"][0]["bbox"][1] for block in members) - 8
        bottom = (caption_block["source_refs"][0]["bbox"][1] - 2
                  if caption_block["source_page"] == page_number and
                  caption_block["source_refs"][0]["bbox"][1] > top else
                  max(block["source_refs"][0]["bbox"][3] for block in members) + 8)
        width = pdfs[key][page_number - 1].get_size()[0]
        box = [60, max(0, top), width - 60, bottom]
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
