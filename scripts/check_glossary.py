"""Check translations against the shared glossary (data/glossary.json).

    python scripts/check_glossary.py [KEY ...] [--json OUT]

Reports each translated block whose Japanese uses a forbidden rendering of a glossary term,
except those recorded as acceptable in data/glossary-exceptions.json. With no KEY, every
document is checked. Exits 1 when a violation remains.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "data" / "glossary.json"
EXCEPTIONS = ROOT / "data" / "glossary-exceptions.json"


def load_rules(path=GLOSSARY):
    rules = json.loads(Path(path).read_text())["rules"]
    for rule in rules:
        rule["_forbid"] = re.compile(rule["forbid"])
        rule["_en"] = re.compile(rule["en"], re.I) if rule.get("en") else None
        rule["_unless_en"] = re.compile(rule["unless_en"], re.I) if rule.get("unless_en") else None
    return rules


def load_exceptions(path=EXCEPTIONS):
    """{document: {block id: [rule id, ...]}}"""
    path = Path(path)
    return json.loads(path.read_text())["exceptions"] if path.exists() else {}


def applies(rule, english):
    """Whether a rule concerns a text whose English source is `english` (None: no source)."""
    if rule["_en"] is None:
        return True
    if english is None or not rule["_en"].search(english):
        return False
    return not (rule["_unless_en"] and rule["_unless_en"].search(english))


def violations(rules, japanese, english):
    return [rule["id"] for rule in rules if japanese and applies(rule, english) and rule["_forbid"].search(japanese)]


def check_document(key, rules, exceptions):
    found = []
    trans = ROOT / "data" / (key + "-trans.json")
    if trans.exists():
        document = json.loads(trans.read_text())
        allowed = exceptions.get(key, {})
        for block in document["contents"]:
            for rule_id in violations(rules, block.get("html_ja"), block.get("html", "")):
                if rule_id not in allowed.get(block["id"], []):
                    found.append({"document": key, "id": block["id"], "rule": rule_id,
                                  "html": block.get("html", ""), "html_ja": block["html_ja"]})
        for field in ("title_ja", "subtitle_ja", "description"):
            for rule_id in violations(rules, document.get(field), None):
                found.append({"document": key, "id": field, "rule": rule_id, "html_ja": document[field]})
    summary = ROOT / "data" / (key + "-summary.json")
    if summary.exists():
        for index, sentence in enumerate(json.loads(summary.read_text()).get("summary", [])):
            for rule_id in violations(rules, sentence, None):
                found.append({"document": key, "id": "summary[%d]" % index, "rule": rule_id, "html_ja": sentence})
    return found


def all_keys():
    names = {p.name[:-len("-trans.json")] for p in (ROOT / "data").glob("*-trans.json")}
    names |= {p.name[:-len("-summary.json")] for p in (ROOT / "data").glob("*-summary.json")}
    return sorted(names)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("keys", nargs="*")
    cli.add_argument("--json", type=Path, help="write the violations to this file")
    args = cli.parse_args()
    rules, exceptions = load_rules(), load_exceptions()
    found = [item for key in (args.keys or all_keys()) for item in check_document(key, rules, exceptions)]
    if args.json:
        args.json.write_text(json.dumps(found, ensure_ascii=False, indent=1) + "\n")
    counts = {}
    for item in found:
        counts[item["rule"]] = counts.get(item["rule"], 0) + 1
    for item in found[:50]:
        match = next(r for r in rules if r["id"] == item["rule"])["_forbid"].search(item["html_ja"])
        start = max(0, match.start() - 20)
        print("%s %s [%s] …%s…" % (item["document"], item["id"], item["rule"],
                                   item["html_ja"][start:match.end() + 20].replace("\n", " ")))
    print("violations:", len(found), counts)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
