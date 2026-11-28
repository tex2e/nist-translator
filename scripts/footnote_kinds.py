"""Mark footnotes that extraction recorded as body text or formulas as footnotes.

    python scripts/footnote_kinds.py [--apply] [KEY ...]

A paragraph or math block counts as a footnote when a reference <sup>N</sup> in the text has
no footnote N on its page or the two pages after it, and this block, printed on one of those
pages, opens with that number ("56 The XOR operation…", "<sup>2</sup>For…"). Headings never
count ("3 cSHAKE" is a section heading on the next page). Blocks in a math group keep their
kind. Only "kind" changes (with "kind_fix"); the text and its translation are unchanged.
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.footnotes import HEAD, PAGE_REACH, footnote_numbers  # noqa: E402

HIDDEN = ("page_furniture", "math_duplicate_of", "duplicate_artifact_of", "figure_text_of",
          "official_mark", "third_party_excerpt")
KINDS = {"paragraph", "math"}
STAMP = "2026-11-28: footnote"


def process(document):
    """Ids of the blocks that are the footnotes of unmatched references."""
    grouped = {member for group in document.get("math_groups", []) for member in group["members"]}
    blocks = [block for block in document["contents"] if not any(block.get(k) for k in HIDDEN)]
    notes = {}
    for index, block in enumerate(blocks):
        if block["kind"] == "footnote":
            for number in footnote_numbers(block["html"]):
                notes.setdefault(number, []).append((index, block.get("source_page") or 0))
    found = []
    for index, block in enumerate(blocks):
        if block["kind"] == "footnote":
            continue
        page = block.get("source_page") or 0
        for match in re.finditer(r"<sup>(\d{1,3})</sup>", block["html"]):
            number = int(match.group(1))
            if any((i > index and 0 <= p - page <= PAGE_REACH) or (i < index and p == page)
                   for i, p in notes.get(number, [])):
                continue
            for other_index, other in enumerate(blocks):
                if (other["kind"] not in KINDS or other["id"] in grouped or other_index == index
                        or not 0 <= (other.get("source_page") or 0) - page <= PAGE_REACH):
                    continue
                head = HEAD.match(other["html"])
                if head and int(head.group(1) or head.group(2)) == number:
                    found.append(other["id"])
                    notes.setdefault(number, []).append((other_index, other.get("source_page") or 0))
                    break
    return found


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("keys", nargs="*")
    args = cli.parse_args()
    total = 0
    for path in sorted(glob.glob(str(ROOT / "data" / "*-trans.json"))):
        key = Path(path).name[:-len("-trans.json")]
        if args.keys and key not in args.keys:
            continue
        document = json.loads(Path(path).read_text())
        found = set(process(document))
        if not found:
            continue
        total += len(found)
        print(key, len(found), " ".join(sorted(found)))
        if args.apply:
            for block in document["contents"]:
                if block["id"] in found:
                    block["kind_fix"] = "%s (was %s)" % (STAMP, block["kind"])
                    block["kind"] = "footnote"
            Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print("blocks:", total)


if __name__ == "__main__":
    main()
