"""Replace forbidden renderings with the glossary's term, for rules marked "replace".

    python scripts/unify_terms.py [KEY ...] [--dry-run]

Applies to block translations (html_ja, split_from_ja), the document's Japanese title,
subtitle and description, the summary, and the Japanese strings in documents.py. A rule
with an English condition ("en") only touches blocks whose English source matches it, so
it never applies to the title or the summary.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_glossary import ROOT, all_keys, applies, load_rules  # noqa: E402


def unify(text, rules, english, counts):
    if not text:
        return text
    for rule in rules:
        if applies(rule, english):
            text, n = rule["_forbid"].subn(rule["ja"], text)
            counts[rule["id"]] += n
    return text


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("keys", nargs="*")
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    rules = [rule for rule in load_rules() if rule.get("replace")]
    counts, changed = Counter(), []
    for key in args.keys or all_keys():
        trans = ROOT / "data" / (key + "-trans.json")
        if trans.exists():
            document = json.loads(trans.read_text())
            before = json.dumps(document, ensure_ascii=False)
            for block in document["contents"]:
                for field in ("html_ja", "split_from_ja"):
                    if block.get(field):
                        block[field] = unify(block[field], rules, block.get("html", ""), counts)
            for field in ("title_ja", "subtitle_ja", "description"):
                if document.get(field):
                    document[field] = unify(document[field], rules, None, counts)
            if json.dumps(document, ensure_ascii=False) != before:
                changed.append(trans.name)
                if not args.dry_run:
                    write_json(trans, document)
        summary_path = ROOT / "data" / (key + "-summary.json")
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            new = [unify(sentence, rules, None, counts) for sentence in summary.get("summary", [])]
            if new != summary.get("summary", []):
                summary["summary"] = new
                changed.append(summary_path.name)
                if not args.dry_run:
                    write_json(summary_path, summary)
    if not args.keys:
        source = ROOT / "src" / "nist_translater" / "documents.py"
        text = source.read_text()
        new = unify(text, rules, None, counts)
        if new != text:
            changed.append(source.name)
            if not args.dry_run:
                source.write_text(new)
    print("files changed:", len(changed))
    print("replacements:", dict(counts))


if __name__ == "__main__":
    main()
