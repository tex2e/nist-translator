"""Apply explicit assistant self-review decisions to unchanged reviewed snapshots.

This validates decisions already made by reading the bilingual text. It never
judges translation quality, infers approval, or attributes the work to Claude.
Input is a JSON array with document path, id, source HTML/hash, initial Japanese
SHA-256, final Japanese, verdict, reviewer, date and a correction recheck flag.
"""
import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nist_translater.translation import assert_same_html_structure, audit_translations


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def apply(decisions_path):
    decisions_path = decisions_path.resolve()
    decisions = json.loads(decisions_path.read_text())
    documents, seen = {}, set()
    corrected = 0
    for verdict in decisions:
        path = (ROOT / verdict["document"]).resolve()
        if path.parent != ROOT / "data" or not path.name.endswith("-trans.json"):
            raise ValueError("Expected a canonical translation JSON path")
        key = (path, verdict["id"])
        if key in seen:
            raise ValueError("Duplicate decision")
        seen.add(key)
        if path not in documents:
            documents[path] = json.loads(path.read_text())
        doc = documents[path]
        block = next(b for b in doc["contents"] if b["id"] == verdict["id"])
        assert block["status"] == "draft", "Already applied or no longer draft"
        assert doc.get("source_format") != "pdf" or block["extraction_status"] == "verified"
        assert not any(block.get(k) for k in ("page_furniture", "duplicate_artifact_of", "math_duplicate_of"))
        assert block["kind"] == verdict["kind"] and block["html"] == verdict["en"] and block["source_hash"] == verdict["source_hash"]
        assert digest(block["html_ja"]) == verdict["initial_translation_hash"]
        assert verdict["reviewer"] == "gpt-6.1-sol" and verdict["mode"] == "self-review"
        assert verdict["verdict"] == "ok" and verdict["note"].strip()
        final_ja = verdict["final_ja"]
        changed = final_ja != block["html_ja"]
        if changed:
            assert verdict["rechecked_after_correction"] is True
            corrected += 1
        assert digest(final_ja) == verdict["translation_hash"]
        assert_same_html_structure(block["html"], final_ja, preserve_math=True)
        prior_review = {k: deepcopy(block[k]) for k in ("translation_check", "translation_review", "translation_fix_rounds") if k in block}
        if prior_review:
            block.setdefault("translation_review_history", []).append(prior_review)
        block.pop("translation_fix_rounds", None)
        block["html_ja"] = final_ja
        block["status"] = "reviewed"
        block["translation_check"] = "gpt-self-review"
        block["translation_review"] = {
            "reviewer": verdict["reviewer"], "mode": "self-review", "date": verdict["date"],
            "source_hash": block["source_hash"], "translation_hash": digest(final_ja),
            "initial_verdict": "issue" if changed else "ok",
            "verdict_file": str(decisions_path.relative_to(ROOT)),
        }
        if block.get("translation_reuse"):
            block["translation_reuse"]["recipient_review"] = "self-reviewed-corrected" if changed else "self-reviewed"
            block["translation_reuse"]["recipient_translation_hash"] = digest(final_ja)
    for document in documents.values():
        audit_translations(document)
    for path, document in documents.items():
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print("self-reviewed", len(decisions), "corrected", corrected, "documents", len(documents))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions", type=Path)
    apply(parser.parse_args().decisions)
