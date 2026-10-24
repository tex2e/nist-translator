"""Reuse unambiguous reviewed translations of exactly identical PDF blocks.

Recipients remain draft: an approved donor is not a recipient-context review.
Dry-run by default; validate every affected document before writing any of them.
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nist_translater.translation import audit_translations, merge_translations

KINDS = {"paragraph", "heading", "list_item", "note", "footnote"}


def eligible(block):
    return (block["kind"] in KINDS and block.get("extraction_status") == "verified"
            and not any(block.get(key) for key in ("page_furniture", "math_duplicate_of", "duplicate_artifact_of")))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    args.report = args.report.resolve()
    if args.report.exists():
        parser.error("Report already exists; preserve prior evidence and choose a new path")
    documents, donors = {}, defaultdict(list)
    for path in sorted((ROOT / "data").glob("*-trans.json")):
        doc = json.loads(path.read_text())
        if doc.get("source_format") != "pdf":
            continue
        documents[path] = doc
        for block in doc["contents"]:
            if eligible(block) and block["status"] == "reviewed" and block["html_ja"].strip():
                donors[(block["kind"], block["html"])].append((path, block))
    changes, sources, affected = [], {}, set()
    for path, doc in documents.items():
        incoming = []
        for block in doc["contents"]:
            if not eligible(block) or block["status"] not in {"untranslated", "stale"}:
                continue
            choices = donors.get((block["kind"], block["html"]), [])
            if not choices or len({b["html_ja"] for _, b in choices}) != 1:
                continue
            donor_path, donor = choices[0]
            assert donor["kind"] == block["kind"] and donor["html"] == block["html"]
            source_key = digest(donor["kind"] + "\n" + donor["html"])
            sources.setdefault(source_key, {"document": str(donor_path.relative_to(ROOT)), "block": deepcopy(donor)})
            original = deepcopy(block)
            old_review = {key: block.pop(key) for key in ("translation_check", "translation_review", "translation_fix_rounds") if key in block}
            if old_review:
                block.setdefault("translation_reuse_previous_reviews", []).append(old_review)
            block["translation_reuse"] = {
                "method": "exact-kind-and-html-reviewed-donor", "recipient_review": "pending",
                "donor_document": str(donor_path.relative_to(ROOT)), "donor_id": donor["id"],
                "donor_source_hash": donor["source_hash"], "recipient_source_hash": block["source_hash"],
                "translation_hash": digest(donor["html_ja"]),
                "source_record": source_key, "report_file": str(args.report.relative_to(ROOT)),
            }
            incoming.append({"id": block["id"], "source_hash": block["source_hash"], "html_ja": donor["html_ja"]})
            changes.append({"document": str(path.relative_to(ROOT)), "original": original,
                            "donor_record": source_key, "translation_hash": digest(donor["html_ja"])})
        if incoming:
            assert merge_translations(doc, incoming) == len(incoming)
            audit_translations(doc)
            affected.add(path)
    report = {"applied": args.apply, "recipient_status": "draft", "donors": sources,
              "changes": changes, "count": len(changes), "document_count": len(affected)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.apply:
        for path in sorted(affected):
            path.write_text(json.dumps(documents[path], ensure_ascii=False, indent=2) + "\n")
    print("applied" if args.apply else "dry-run", "blocks", len(changes), "documents", len(affected), "recipient reviews pending")


if __name__ == "__main__":
    main()
