"""Restore the "i" of fi/ffi ligatures that some PDFs drop from their text layer.

    python scripts/fix_lost_fi.py [--dry-run] KEY ...

In some LaTeX-made FIPS PDFs the text layer maps the "fi" ligature to "f":
"specified" is extracted as "specifed", "first" as "frst", "coefficient" as
"coeffcient". A word is changed only when putting an "i" after one of its f's gives
a word that is far more common (at least 5 times, and 20 times as often as
the word itself). Known words are collected from
the English text of every document in data/ (the SP 800 texts are checked
against their originals). Only the source text is changed; source_hash is
recomputed, so a translation made from the broken text would show as changed.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORD = re.compile(r"[A-Za-z]+")


def vocabulary(skip):
    words = Counter()
    for path in (ROOT / "data").glob("*-trans.json"):
        if path.name[:-len("-trans.json")] in skip:
            continue
        for block in json.loads(path.read_text()).get("contents", []):
            words.update(word.lower() for word in WORD.findall(re.sub(r"<[^>]+>", " ", block.get("html", ""))))
    return words


def repaired(word, known):
    # Other documents may carry the same broken word, so a word counts as
    # broken when the repaired spelling is far more common than it is.
    lower = word.lower()
    if "f" not in lower:
        return None
    for index, char in enumerate(lower):
        if char == "f":
            candidate = lower[:index + 1] + "i" + lower[index + 1:]
            if known[candidate] >= 5 and known[candidate] > 20 * known[lower]:
                fixed = word[:index + 1] + "i" + word[index + 1:]
                return fixed.upper() if word.isupper() else fixed
    return None


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--dry-run", action="store_true")
    cli.add_argument("keys", nargs="+")
    args = cli.parse_args()
    known = vocabulary(set(args.keys))
    for key in args.keys:
        path = ROOT / "data" / (key + "-trans.json")
        document = json.loads(path.read_text())
        changes, blocks = Counter(), 0

        def fix(match):
            replacement = repaired(match.group(0), known)
            if replacement:
                changes[match.group(0) + " -> " + replacement] += 1
                return replacement
            return match.group(0)

        for block in document["contents"]:
            # Only text outside tags and outside LaTeX is touched.
            parts = re.split(r"(<[^>]+>|\\\(.*?\\\)|\\\[.*?\\\])", block["html"])
            new = "".join(part if index % 2 else WORD.sub(fix, part) for index, part in enumerate(parts))
            if new != block["html"]:
                blocks += 1
                block["html"] = new
                block["source_hash"] = hashlib.sha256((
                    block["kind"] + "\n" + new + "\n" + block.get("source_image_hash", "")
                    if block.get("source_image_hash") else block["kind"] + "\n" + new + "\n"
                ).encode()).hexdigest()[:16]
        print(key, "blocks", blocks, "words", sum(changes.values()))
        for change, count in changes.most_common():
            print("   %3d  %s" % (count, change))
        if not args.dry_run:
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
