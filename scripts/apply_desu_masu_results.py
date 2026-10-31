"""Apply the reviewed です・ます rewordings and heading changes to the data.

    python scripts/apply_desu_masu_results.py RESULT.json [...] [--headings HEADINGS.json] [--dry-run]

A rewording {"doc", "id", "old", "new"} is applied only when `old` occurs exactly once in the
block's html_ja, and `old` and `new` have the same tags and the same requirement keywords
(SHALL, SHOULD, MAY, ...). A heading {"doc", "id", "html_ja"} is applied only when its tags
match the current heading. Items with "skip": true are ignored.
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NORMATIVE = re.compile(r"\b(?:SHALL NOT|SHOULD NOT|NEED NOT|SHALL|SHOULD|MAY(?!\s+\d{4}\b)|CANNOT|CAN)\b")
TAGS = re.compile(r"<[^>]+>")


def same_markup(old, new):
    return TAGS.findall(old) == TAGS.findall(new) and Counter(NORMATIVE.findall(old)) == Counter(NORMATIVE.findall(new))


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("results", nargs="*", type=Path)
    cli.add_argument("--headings", type=Path)
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    edits, headings = defaultdict(list), defaultdict(dict)
    for path in args.results:
        for item in json.loads(path.read_text()):
            if not item.get("skip") and item.get("old") and item.get("new") is not None:
                edits[item["doc"]].append(item)
    if args.headings:
        for item in json.loads(args.headings.read_text()):
            if not item.get("skip") and item.get("html_ja"):
                headings[item["doc"]][item["id"]] = item["html_ja"]
    counts = Counter()
    rejected = []
    for doc in sorted(set(edits) | set(headings)):
        path = ROOT / "data" / (doc + "-trans.json")
        document = json.loads(path.read_text())
        blocks = {block["id"]: block for block in document["contents"]}
        for item in edits.get(doc, []):
            block = blocks.get(item["id"])
            text = block.get("html_ja", "") if block else ""
            if text.count(item["old"]) != 1:
                counts["rejected: old not found once"] += 1
                rejected.append((doc, item["id"], "old not found once", item["old"][:40]))
                continue
            if not same_markup(item["old"], item["new"]):
                counts["rejected: tags or keywords differ"] += 1
                rejected.append((doc, item["id"], "tags or keywords differ", item["new"][:40]))
                continue
            block["html_ja"] = text.replace(item["old"], item["new"])
            counts["reworded"] += 1
        for block_id, html_ja in headings.get(doc, {}).items():
            block = blocks.get(block_id)
            if not block or block["kind"] != "heading" or TAGS.findall(block["html_ja"]) != TAGS.findall(html_ja):
                counts["rejected heading"] += 1
                rejected.append((doc, block_id, "heading tags differ", html_ja[:40]))
                continue
            block["html_ja"] = html_ja
            counts["heading"] += 1
        if not args.dry_run:
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(dict(counts))
    for item in rejected[:20]:
        print("  ", item)


if __name__ == "__main__":
    main()
