"""Drop extraction warnings of pages whose text has all been checked against the original.

    python scripts/clear_checked_warnings.py KEY ...

The extractor warns about pages it may have read in the wrong order
("PDF p.7: 二段組の可能性があるため…"). Once every text block of such a page has
been checked page by page against the original, the warning no longer applies.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = {"paragraph", "heading", "list_item", "note", "footnote", "math", "code", "table"}


def main():
    for key in sys.argv[1:]:
        path = ROOT / "data" / (key + "-trans.json")
        document = json.loads(path.read_text())
        open_pages = {ref["page"] for block in document["contents"]
                      if block["kind"] in TEXT and not block.get("page_furniture")
                      and block.get("extraction_status") != "verified"
                      for ref in block.get("source_refs", [])}
        kept = []
        for warning in document.get("extraction_warnings", []):
            match = re.match(r"PDF p\.(\d+):", warning)
            if match is None or int(match.group(1)) in open_pages:
                kept.append(warning)
        removed = len(document.get("extraction_warnings", [])) - len(kept)
        document["extraction_warnings"] = kept
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        print(key, "removed", removed, "kept", len(kept))


if __name__ == "__main__":
    main()
