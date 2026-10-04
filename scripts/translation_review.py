"""Hand draft translations to reviewers in batches and apply their verdicts.

Only blocks whose English source is trustworthy are offered for review: every
block of an HTML-sourced document, and PDF blocks with
``extraction_status=verified``.

    python scripts/translation_review.py export [--size N] [--fixed] OUT_DIR [KEY ...]
    python scripts/translation_review.py apply VERDICT_DIR [--issues FILE]

``export`` writes ``<key>.<nnn>.batch.json``; a reviewer answers each with
``<key>.<nnn>.verdict.json``: a JSON array of
``{"id", "source_hash", "verdict": "ok" | "issue", "note", "suggested_ja"}``.

``apply`` marks ``ok`` blocks as ``reviewed``. For an ``issue`` it stores the
reviewer's corrected translation but keeps the block a draft; ``export --fixed``
then offers only those corrected blocks, so a correction is cleared by a later,
independent review rather than by the reviewer who wrote it. A block that is
still disputed after ``MAX_FIX_ROUNDS`` corrections stays a draft.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.storage import read_json, write_json  # noqa: E402
from collections import Counter  # noqa: E402

from nist_translater.translation import (  # noqa: E402
    NORMATIVE, assert_same_html_structure, audit_translations, source_text)

REVIEW_TAG = "claude-review"   # translation accepted by a reviewer
FIX_TAG = "claude-fix"         # reviewer's correction stored, awaiting re-review
ISSUE_TAG = "claude-issue"     # disputed; left as a draft for a human
MAX_FIX_ROUNDS = 2
MAX_BATCH_CHARS = 45000


def _reviewable(document, block):
    return (block.get("status") == "draft" and block.get("html_ja", "").strip() and
            not block.get("duplicate_artifact_of") and
            (document.get("source_format") != "pdf" or
             block.get("extraction_status") == "verified"))


def _keys(names):
    return names or sorted(path.name[:-len("-trans.json")]
                           for path in (ROOT / "data").glob("*-trans.json"))


def export(out_dir, size, names, fixed):
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = blocks = 0
    for key in _keys(names):
        document = read_json(ROOT / "data" / (key + "-trans.json"))
        wanted = FIX_TAG if fixed else None
        items = [{"id": block["id"], "kind": block["kind"],
                  "source_hash": block["source_hash"],
                  "en": block["html"], "ja": block["html_ja"]}
                 for block in document["contents"]
                 if _reviewable(document, block) and block.get("translation_check") == wanted]
        groups, chars = [[]], 0
        for item in items:
            length = len(item["en"]) + len(item["ja"])
            if groups[-1] and (len(groups[-1]) >= size or chars + length > MAX_BATCH_CHARS):
                groups.append([])
                chars = 0
            groups[-1].append(item)
            chars += length
        for index, group in enumerate(group for group in groups if group):
            write_json(out_dir / ("%s.%03d.batch.json" % (key, index + 1)), {
                "document": document.get("number", key),
                "title": document.get("subtitle", ""),
                "blocks": group})
            batches += 1
        blocks += len(items)
    print("Exported %d blocks in %d batches to %s" % (blocks, batches, out_dir))


def _valid_fix(block, japanese):
    if not isinstance(japanese, str) or not japanese.strip() or japanese == block["html_ja"]:
        return False
    try:
        # A correction to a restored math block must leave its formulas alone.
        assert_same_html_structure(block["html"], japanese,
                                   preserve_math=block["kind"] == "math")
    except ValueError:
        return False
    return Counter(NORMATIVE.findall(japanese)) == Counter(NORMATIVE.findall(source_text(block)))


def apply(verdict_dir, issues_path):
    verdicts, rejected = {}, []
    for batch_path in sorted(verdict_dir.glob("*.batch.json")):
        path = batch_path.with_name(batch_path.name.replace(".batch.json", ".verdict.json"))
        if not path.exists():
            rejected.append(batch_path.name + ": no verdict file")
            continue
        try:
            answers = read_json(path)
            expected = [item["id"] for item in read_json(batch_path)["blocks"]]
            if (sorted(item["id"] for item in answers) != sorted(expected) or
                    any(item["verdict"] not in {"ok", "issue"} for item in answers)):
                raise ValueError("verdicts do not cover the batch exactly")
        except (ValueError, KeyError, TypeError) as error:
            rejected.append("%s: %s" % (path.name, error))
            continue
        verdicts.setdefault(batch_path.name.split(".")[0], []).extend(answers)
    issues = read_json(issues_path, default=[]) if issues_path else []
    counts = Counter()
    for key, answers in sorted(verdicts.items()):
        path = ROOT / "data" / (key + "-trans.json")
        document = read_json(path)
        blocks = {block["id"]: block for block in document["contents"]}
        for answer in answers:
            block = blocks[answer["id"]]
            # The source or the translation may have changed since the export.
            if answer.get("source_hash") != block["source_hash"] or not _reviewable(document, block):
                counts["skipped"] += 1
                continue
            if answer["verdict"] == "ok":
                block["status"] = "reviewed"
                block["translation_check"] = REVIEW_TAG
                counts["reviewed"] += 1
                continue
            rounds = block.get("translation_fix_rounds", 0)
            fix = answer.get("suggested_ja", "")
            if rounds < MAX_FIX_ROUNDS and _valid_fix(block, fix):
                block["html_ja"] = fix
                block["translation_check"] = FIX_TAG
                block["translation_fix_rounds"] = rounds + 1
                action = "fixed"
            else:
                block["translation_check"] = ISSUE_TAG
                action = "unresolved"
            counts[action] += 1
            issues.append({"document_key": key, "id": block["id"], "action": action,
                           "round": rounds + 1, "note": answer.get("note", "")})
        audit_translations(document)
        write_json(path, document)
    if issues_path:
        write_json(issues_path, issues)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())) or "nothing applied")
    for line in rejected:
        print("REJECTED", line)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = cli.add_subparsers(dest="command", required=True)
    exporter = commands.add_parser("export")
    exporter.add_argument("out_dir", type=Path)
    exporter.add_argument("--size", type=int, default=40, help="blocks per batch")
    exporter.add_argument("--fixed", action="store_true",
                          help="only corrected drafts awaiting re-review")
    exporter.add_argument("keys", nargs="*")
    applier = commands.add_parser("apply")
    applier.add_argument("verdict_dir", type=Path)
    applier.add_argument("--issues", type=Path, help="write blocks with issues to this JSON file")
    args = cli.parse_args()
    if args.command == "export":
        export(args.out_dir, args.size, args.keys, args.fixed)
    else:
        apply(args.verdict_dir, args.issues)


if __name__ == "__main__":
    main()
