"""Final judgment on drafts that codex still flags after its correction rounds.

    python scripts/resolve_flagged.py export OUT_DIR VERDICT_ROOT [--size N]
    python scripts/resolve_flagged.py apply OUT_DIR

export writes one batch per document with every draft whose translation_check
is "codex-issue", together with codex's latest note and suggestion (found in the
*.verdict.json files under VERDICT_ROOT, newest file wins). The judge writes
<batch>.answer.json next to each batch: a list with one object per block,
{"id", "source_hash", "decision": "keep" | "fix", "html_ja" (the final
translation when "fix", else ""), "note"}.

apply accepts an answer only when the source hash still matches and a fixed
translation keeps the English HTML structure, formulas and requirement words.
Accepted blocks become "reviewed" with translation_check "claude-resolve";
anything else is listed and left as it is.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.nist_translater.translation import audit_translations  # noqa: E402
from translation_review import _valid_fix, read_json, write_json  # noqa: E402


def export(out_dir, verdict_root, size):
    notes = {}
    for path in sorted(verdict_root.rglob("*.verdict.json"), key=lambda p: p.stat().st_mtime):
        key = path.name.split(".")[0]
        for item in read_json(path):
            if item.get("verdict") == "issue":
                notes[(key, item["id"])] = {"note": item.get("note", ""),
                                            "codex_suggestion": item.get("suggested_ja", "")}
    out_dir.mkdir(parents=True, exist_ok=True)
    total = batches = 0
    for path in sorted((ROOT / "data").glob("*-trans.json")):
        key = path.name[:-len("-trans.json")]
        document = read_json(path)
        items = [dict({"id": b["id"], "kind": b["kind"], "source_hash": b["source_hash"],
                       "source_page": b.get("source_page"), "en": b["html"], "ja": b["html_ja"]},
                      **notes.get((key, b["id"]), {"note": "", "codex_suggestion": ""}))
                 for b in document["contents"]
                 if b.get("status") == "draft" and b.get("translation_check") == "codex-issue"]
        for start in range(0, len(items), size):
            group = items[start:start + size]
            write_json(out_dir / ("%s.%03d.batch.json" % (key, start // size + 1)),
                       {"document": document.get("number", key), "key": key, "blocks": group})
            batches += 1
        total += len(items)
    print("Exported %d blocks in %d batches to %s" % (total, batches, out_dir))


def apply(out_dir):
    counts, problems, answers = Counter(), [], {}
    for batch in sorted(out_dir.glob("*.batch.json")):
        answer = batch.with_name(batch.name.replace(".batch.json", ".answer.json"))
        if not answer.exists():
            problems.append(batch.name + ": no answer")
            continue
        answers.setdefault(read_json(batch)["key"], []).extend(read_json(answer))
    for key, items in sorted(answers.items()):
        path = ROOT / "data" / (key + "-trans.json")
        document = read_json(path)
        blocks = {b["id"]: b for b in document["contents"]}
        for item in items:
            block = blocks.get(item.get("id"))
            if block is None or block.get("source_hash") != item.get("source_hash"):
                counts["skipped"] += 1
                problems.append("%s %s: gone or source changed" % (key, item.get("id")))
                continue
            if item.get("decision") == "fix":
                if not _valid_fix(block, item.get("html_ja", "")):
                    counts["rejected"] += 1
                    problems.append("%s %s: fix changes structure, formulas or requirement words"
                                    % (key, item["id"]))
                    continue
                block["html_ja"] = item["html_ja"]
            elif item.get("decision") != "keep":
                counts["rejected"] += 1
                problems.append("%s %s: bad decision" % (key, item["id"]))
                continue
            block["status"] = "reviewed"
            block["translation_check"] = "claude-resolve"
            block["translation_resolve_note"] = item.get("note", "")
            counts[item["decision"]] += 1
        audit_translations(document)
        write_json(path, document)
    print(" ".join("%s=%d" % kv for kv in sorted(counts.items())) or "nothing applied")
    for line in problems:
        print("PROBLEM", line)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = cli.add_subparsers(dest="command", required=True)
    e = sub.add_parser("export")
    e.add_argument("out_dir", type=Path)
    e.add_argument("verdict_root", type=Path)
    e.add_argument("--size", type=int, default=30)
    a = sub.add_parser("apply")
    a.add_argument("out_dir", type=Path)
    args = cli.parse_args()
    if args.command == "export":
        export(args.out_dir, args.verdict_root, args.size)
    else:
        apply(args.out_dir)


if __name__ == "__main__":
    main()
