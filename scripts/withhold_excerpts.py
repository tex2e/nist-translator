"""Withhold third-party copyrighted excerpts that NIST reprinted with permission.

    python scripts/withhold_excerpts.py

SP 800-160 Vol. 1 Rev. 1 reprints the purpose statement of each ISO/IEC/IEEE 15288:2015
process "with permission from IEEE". That permission was given to NIST, not to this site,
so the English text and its translation are removed from the data (also from the
archived records) and the page shows a note that points to the original PDF instead.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCERPT = {"source": "ISO/IEC/IEEE 15288:2015", "holder": "IEEE"}
PURPOSE = re.compile(r"^The purpose of the .+? process is ")


def text(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def withhold(block):
    block.update(html="", html_ja="", status="source_only", third_party_excerpt=dict(EXCERPT))


def main():
    path = ROOT / "data" / "sp800-160v1r1-trans.json"
    document = json.loads(path.read_text())
    count = 0
    for block in document["contents"]:
        if block.get("third_party_excerpt") or (not block.get("page_furniture") and PURPOSE.match(text(block["html"]))):
            withhold(block)
            count += 1
    archived = [b for b in document.get("math_preservation", {}).get("rebuilt_blocks", [])
                + document.get("source_repairs", {}).get("original_blocks", [])
                if PURPOSE.match(text(b.get("html")))]
    for block in archived:
        withhold(block)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print("withheld", count, "blocks and", len(archived), "archived records")


if __name__ == "__main__":
    main()
