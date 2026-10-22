"""Restore quotation marks that some PDFs map to other glyphs in their text layer.

In these documents the print shows “ ” ‘ but the text layer gives ― ‖ ‗
(checked against page images). Only the source text changes; the Japanese
translations use their own quotation marks, so their status is kept.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLYPHS = {"―": "“", "‖": "”", "‗": "‘"}


def fix(key):
    path = ROOT / "data" / (key + "-trans.json")
    document = json.loads(path.read_text())
    changed = 0
    for block in document["contents"]:
        for field in ("html", "html_ja"):
            text = block.get(field)
            if text and any(glyph in text for glyph in GLYPHS):
                for glyph, mark in GLYPHS.items():
                    text = text.replace(glyph, mark)
                block[field] = text
                if field == "html":
                    block["source_hash"] = hashlib.sha256(
                        (block["kind"] + "\n" + text + "\n").encode()).hexdigest()[:16]
                    changed += 1
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, "blocks", changed)


if __name__ == "__main__":
    for key in sys.argv[1:]:
        fix(key)
