"""Keep official marks out of the published pages.

    python scripts/withhold_marks.py LIST.json

The NIST logo and the Department of Commerce seal are protected marks; this
site is an unofficial translation and must not display them. LIST.json holds
``[document key, block id, mark]`` entries (mark: ``nist_logo``, ``doc_seal``
``contains_nist_logo`` for a larger figure that shows the logo, ``person_photo``
for a photograph of people, ``other_logo`` for another organisation's logo,
``decorative`` for banners, stock photos and other decoration, ``third_party_image`` for an image credited to or taken from a third party) chosen by looking at the images. Each listed figure block gets
``official_mark``; the page builder then prints a short note in place of the
image, and the image file is removed from ``html/assets``. The block and its
provenance stay in the data.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    entries = json.loads(Path(sys.argv[1]).read_text())
    by_key = {}
    for key, identifier, mark in entries:
        by_key.setdefault(key, {})[identifier] = mark
    counts = Counter()
    for key, marks in sorted(by_key.items()):
        path = ROOT / "data" / (key + "-trans.json")
        document = json.loads(path.read_text())
        for block in document["contents"]:
            mark = marks.get(block["id"])
            if not mark:
                continue
            block["official_mark"] = mark
            counts[mark] += 1
            sources = re.findall(r'<img[^>]*src="([^"]+)"', block["html"])
            for source in sources + ([block["source_image"]] if block.get("source_image") else []):
                image = ROOT / "html" / source
                if image.exists():
                    image.unlink()
                    counts["files removed"] += 1
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(dict(counts))


if __name__ == "__main__":
    main()
