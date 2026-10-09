"""Turn paragraphs that start with an unmapped bullet glyph into list items.

    python scripts/fix_bullet_glyphs.py [KEY ...]

Some PDFs draw bullets with a symbol font that has no Unicode mapping, and the
extraction wrote them as ``(cid:31)``, ``(cid:131)`` or ``(cid:132)`` at the
start of the paragraph (or as a lone ``o`` for second-level bullets). Such a
block becomes a ``list_item`` without the marker; the same marker is removed
from the start of its translation.
"""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLYPH = re.compile(r"^\(cid:(\d+)\) ?")
SMALL_O = re.compile(r"^o (?=[A-Z])")


def main():
    keys = sys.argv[1:] or sorted(path.name[:-len("-trans.json")]
                                  for path in (ROOT / "data").glob("*-trans.json"))
    total = Counter()
    for key in keys:
        path = ROOT / "data" / (key + "-trans.json")
        document = json.loads(path.read_text())
        if document.get("source_format") != "pdf":
            continue
        count = 0
        for block in document["contents"]:
            if block["kind"] != "paragraph" or block.get("extraction_status") == "verified":
                continue
            glyph = GLYPH.match(block["html"])
            marker = glyph or SMALL_O.match(block["html"])
            if not marker:
                continue
            block["html"] = block["html"][marker.end():]
            translated = block.get("html_ja") or ""
            block["html_ja"] = re.sub(r"^(?:\(cid:\d+\)|o|[•・◦○])\s*", "", translated)
            block["kind"] = "list_item"
            block["ordered"], block["ordinal"] = False, None
            block["depth"] = 1 if (not glyph or glyph.group(1) == "132") else 0
            block["source_hash"] = hashlib.sha256(
                (block["kind"] + "\n" + block["html"] + "\n" +
                 block.get("source_image_hash", "")).encode("utf-8")).hexdigest()[:16]
            count += 1
        if count:
            total[key] = count
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(sum(total.values()), "blocks in", len(total), "documents")


if __name__ == "__main__":
    main()
