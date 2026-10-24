"""Suspend reviewed translations whose PDF source has not been verified.

Dry-run by default. Preserve content and archive prior review metadata so that
an old translation review is not mistaken for approval of the current source.
"""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nist_translater.translation import audit_translations


def suspend(document):
    changed = []
    if document.get("source_format") != "pdf":
        return changed
    for block in document["contents"]:
        if block["status"] != "reviewed" or block.get("extraction_status") == "verified":
            continue
        original = deepcopy(block)
        previous = {key: block.pop(key) for key in (
            "translation_check", "translation_review", "translation_fix_rounds") if key in block}
        history = block.setdefault("unverified_source_review_history", [])
        history.append({"prior_status": "reviewed", "source_hash": block["source_hash"],
                        "extraction_status": block.get("extraction_status"),
                        "reason": "原本未照合のため、旧訳レビューを現行原文の承認として扱わない。",
                        "previous_review": previous})
        block["status"] = "draft"
        changed.append(original)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report already exists; preserve prior decisions and choose a new path")
    pending, report = {}, []
    for path in sorted((ROOT / "data").glob("*-trans.json")):
        document = json.loads(path.read_text())
        originals = suspend(document)
        if not originals:
            continue
        audit_translations(document)
        pending[path] = document
        report.append({"document": path.stem.replace("-trans", ""),
                       "original_blocks": originals, "count": len(originals)})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"applied": args.apply, "documents": report}, ensure_ascii=False, indent=2) + "\n")
    if args.apply:
        for path, document in pending.items():
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print("applied" if args.apply else "dry-run", "documents", len(pending),
          "blocks", sum(r["count"] for r in report))


if __name__ == "__main__":
    main()
