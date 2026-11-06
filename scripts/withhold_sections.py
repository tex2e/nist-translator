"""Withhold whole sections that reproduce another party's work (e.g. presenters' slides).

    python scripts/withhold_sections.py SPEC.json

SPEC.json: [{"document", "first", "last", "source", "holder"}]. Every block from "first" to
"last" (inclusive, in document order) loses its English text and translation, as in
scripts/withhold_excerpts.py, and gets "third_party_excerpt" {"source", "holder"}; archived
copies in source_repairs are emptied too, and images the blocks pointed to are deleted.
The page shows one note per withheld run (consecutive blocks of the same source).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    by_document = {}
    for entry in spec:
        by_document.setdefault(entry["document"], []).append(entry)
    for key, entries in by_document.items():
        path = ROOT / "data" / (key + "-trans.json")
        document = json.loads(path.read_text())
        ids = [block["id"] for block in document["contents"]]
        withheld = set()
        for entry in entries:
            first, last = ids.index(entry["first"]), ids.index(entry["last"])
            excerpt = {"source": entry["source"], "holder": entry["holder"]}
            for block in document["contents"][first:last + 1]:
                for source in re.findall(r'src="([^"]+)"', block.get("html", "")):
                    image = ROOT / "html" / source
                    if image.is_file():
                        image.unlink()
                block.update(html="", html_ja="", status="source_only", third_party_excerpt=excerpt)
                for drop in ("alt_en", "alt_ja", "source_image", "translation_check"):
                    block.pop(drop, None)
                withheld.add(block["id"])
        # pages where every visible block is withheld: archived records from them go too
        pages = {}
        for block in document["contents"]:
            if not block.get("page_furniture"):
                pages.setdefault(block["source_page"], []).append(block["id"] in withheld)
        whole = {page for page, flags in pages.items() if all(flags)}
        for archived in document.get("source_repairs", {}).get("original_blocks", []):
            split_parent = any(i.startswith(archived["id"] + "-") for i in withheld)
            if archived["id"] in withheld or split_parent or archived.get("source_page") in whole:
                archived.update(html="", html_ja="")
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        print(key, len(withheld), "blocks withheld")


if __name__ == "__main__":
    main()
