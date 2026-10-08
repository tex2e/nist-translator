"""Mark running headers, footers and page numbers that were extracted as blocks.

    python scripts/mark_page_furniture.py [--dry-run] [KEY ...]

A short text that recurs (digits aside) on many pages and sits in the top or
bottom margin is page furniture, not content. Such a block gets
``page_furniture: true``: it is left out of the reading page and of the
translation work, and a paragraph that continues over a page break is no
longer cut off by it. Nothing is deleted.
"""

import argparse
import html
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.storage import read_json, write_json  # noqa: E402

TAG = re.compile(r"<[^>]+>")
TOP, BOTTOM = 75, 715  # points; the margins of a letter page
SKIP = {"figure", "source_excerpt", "table", "math"}


def furniture(document):
    """The blocks of a document that are page furniture."""
    blocks = [block for block in document["contents"]
              if block.get("source_refs") and len(block["source_refs"]) == 1 and
              block["kind"] not in SKIP and not block.get("paragraph_merge")]
    pages = len({block.get("source_page") for block in document["contents"]})
    groups = defaultdict(list)
    for block in blocks:
        text = html.unescape(TAG.sub("", block["html"])).strip()
        if text and len(text) <= 140:
            groups[re.sub(r"\d+", "#", text)].append(block)
    found = []
    for members in groups.values():
        in_margin = [block for block in members
                     if block["source_refs"][0]["bbox"][3] < TOP or
                     block["source_refs"][0]["bbox"][1] > BOTTOM]
        # Recurring, and nearly always in a margin: the few occurrences in the
        # body (a chapter title that is also its running header) are kept.
        if len(members) >= max(4, pages * 0.15) and len(in_margin) >= len(members) * 0.8:
            found += in_margin
    return found


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--dry-run", action="store_true")
    cli.add_argument("keys", nargs="*")
    args = cli.parse_args()
    keys = args.keys or sorted(path.name[:-len("-trans.json")]
                               for path in (ROOT / "data").glob("*-trans.json"))
    total = Counter()
    for key in keys:
        path = ROOT / "data" / (key + "-trans.json")
        document = read_json(path)
        if document.get("source_format") != "pdf":
            continue
        found = [block for block in furniture(document) if not block.get("page_furniture")]
        if not found:
            continue
        total[key] = len(found)
        if not args.dry_run:
            for block in found:
                block["page_furniture"] = True
            write_json(path, document)
    for key, count in total.most_common():
        print(key, count)
    print("%d blocks in %d documents%s" % (
        sum(total.values()), len(total), " (dry run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
