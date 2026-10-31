"""Apply Opus's final judgments on the codex flags for the です・ます rewordings (2026-10-31).

    python scripts/apply_desu_masu_judgments.py FLAGS.json JUDGMENT.json [...] [--dry-run]

FLAGS.json holds the flagged items ({"n", "doc", "id", "after", ...}); each judgment is
{"n", "decision": "keep" | "fix", "new"}. For a fix, the part where "after" and "new" differ
(with a few characters of context) is replaced in the block's html_ja, only when that text
occurs there exactly once and the keywords are unchanged.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NORMATIVE = re.compile(r"\b(?:SHALL NOT|SHOULD NOT|NEED NOT|SHALL|SHOULD|MAY(?!\s+\d{4}\b)|CANNOT|CAN)\b")


def changed_span(after, new, context=6):
    start = 0
    while start < min(len(after), len(new)) and after[start] == new[start]:
        start += 1
    end = 0
    while end < min(len(after), len(new)) - start and after[-1 - end] == new[-1 - end]:
        end += 1
    start = max(0, start - context)
    return after[start:len(after) - end], new[start:len(new) - end]


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("flags", type=Path)
    cli.add_argument("judgments", nargs="+", type=Path)
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    flags = {f["n"]: f for f in json.loads(args.flags.read_text())}
    documents, counts, rejected = {}, Counter(), []
    for path in args.judgments:
        for judgment in json.loads(path.read_text()):
            counts[judgment["decision"]] += 1
            if judgment["decision"] != "fix":
                continue
            flag = flags[judgment["n"]]
            old, new = changed_span(flag["after"], judgment["new"].strip())
            if Counter(NORMATIVE.findall(old)) != Counter(NORMATIVE.findall(new)):
                rejected.append((judgment["n"], "keywords differ"))
                continue
            if flag["doc"] not in documents:
                documents[flag["doc"]] = json.loads((ROOT / "data" / (flag["doc"] + "-trans.json")).read_text())
            block = next(b for b in documents[flag["doc"]]["contents"] if b["id"] == flag["id"])
            if not old or block["html_ja"].count(old) != 1:
                rejected.append((judgment["n"], "not found once: " + old))
                continue
            block["html_ja"] = block["html_ja"].replace(old, new)
            counts["applied"] += 1
    if not args.dry_run:
        for doc, document in documents.items():
            (ROOT / "data" / (doc + "-trans.json")).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(dict(counts))
    for item in rejected:
        print("  ", item)


if __name__ == "__main__":
    main()
