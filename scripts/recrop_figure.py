"""Crop a figure again from the original page, replacing a bad crop.

    python scripts/recrop_figure.py SPEC.json

SPEC.json lists ``[document key, figure block id, caption block id, [other
figure block ids that are pieces of the same figure]]``. The figure's area is
found as in figure_from_text.py (the drawing just above its caption, with its
labels). The figure keeps its id; its image, hash and description are reset,
so the figure is described and checked again. The pieces are hidden.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import figure_from_text as F  # noqa: E402


def main():
    import pypdfium2
    entries = json.loads(Path(sys.argv[1]).read_text())
    documents = {}
    for key, figure_id, caption_id, pieces in entries:
        document = documents.setdefault(key, json.loads((ROOT / "data" / (key + "-trans.json")).read_text()))
        blocks = {block["id"]: block for block in document["contents"]}
        figure, caption = blocks[figure_id], blocks[caption_id]
        page_number = figure["source_page"]
        box = F._drawing_box(key, page_number, 60, caption["html"])
        if box is None:
            print(key, figure_id, "no drawing found; left as it was")
            continue
        pdf = pypdfium2.PdfDocument(str(ROOT / "data" / (key + ".pdf")))
        width = pdf[page_number - 1].get_size()[0]
        crop = [60, max(0, box[1] - 6), width - 60, box[3] + 2]
        name = "p%04d-drawing-%s.png" % (page_number, figure_id[-4:])
        image_hash = F._crop(pdf, page_number, crop, ROOT / "html" / "assets" / key / name)
        html = '<img src="assets/%s/%s" alt="PDF原本のp.%dにある図">' % (key, name, page_number)
        figure.update(html=html, html_ja="", status="untranslated", extraction_status="needs_review",
                      source_image_hash=image_hash,
                      source_refs=[{"page": page_number, "bbox": [round(value, 1) for value in crop]}],
                      source_hash=hashlib.sha256(("figure\n" + html + "\n" + image_hash).encode()).hexdigest()[:16])
        for field in ("crop_problem", "translation_check", "review_note", "extraction_check"):
            figure.pop(field, None)
        for piece in pieces:
            blocks[piece]["page_furniture"] = True
            blocks[piece]["figure_text_of"] = figure_id
        print(key, figure_id, "box", [round(value) for value in crop])
    for key, document in documents.items():
        (ROOT / "data" / (key + "-trans.json")).write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
