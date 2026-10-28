"""Pin every page whose blocks are all checked against the original PDF.

    python scripts/pin_verified_pages.py KEY [--dry-run]

A pinned page (source_repairs.pages) keeps its canonical blocks when the same
PDF is extracted again, instead of the extractor's raw blocks. Only pages on
which every block (including hidden ones) has extraction_status "verified" are
pinned, so the canonical text there has been compared with the original. Pages
with no canonical block are left alone. The PDF hash binds the pinning: a
different PDF needs a new comparison.
"""

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("key", help="file name without -trans.json, e.g. sp800-90b")
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    path = ROOT / "data" / (args.key + "-trans.json")
    document = json.loads(path.read_text())
    pdf = ROOT / "data" / (args.key + ".pdf")
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != document["source_sha256"]:
        raise SystemExit("local PDF differs from the canonical source_sha256")
    pages = defaultdict(list)
    for block in document["contents"]:
        pages[block["source_page"]].append(block)
    ready = sorted(p for p, blocks in pages.items()
                   if all(b.get("extraction_status") == "verified" for b in blocks))
    waiting = sorted(set(pages) - set(ready))
    repair = document.setdefault("source_repairs", {"source_sha256": document["source_sha256"],
                                                    "pages": [], "original_blocks": [], "history": []})
    if repair["source_sha256"] != document["source_sha256"]:
        raise SystemExit("source_repairs belong to another PDF")
    added = sorted(set(ready) - set(repair["pages"]))
    print(json.dumps({"pinned_before": len(repair["pages"]), "added": len(added),
                      "not_ready": waiting}, ensure_ascii=False))
    if args.dry_run or not added:
        return
    repair.setdefault("history", []).append({k: copy.deepcopy(v) for k, v in repair.items()
                                             if k not in ("original_blocks", "history")})
    repair["pages"] = sorted(set(repair["pages"]) | set(added))
    repair["reason"] = ("Pin pages whose blocks are all verified against the original, so a reparse of "
                        "the same PDF keeps the checked canonical text, structure and restored math.")
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
