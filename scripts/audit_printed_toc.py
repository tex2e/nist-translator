"""Audit how the original's printed table of contents is shown on every page.

    python scripts/audit_printed_toc.py [--out FILE]

For each document it reports:
  missed      a TOC-like title or a run of dotted/page-numbered lines that is not formatted
  cut         the block right after a formatted TOC still looks like a TOC line
  leftover    an entry that still shows dot leaders or a trailing page number
  unsplit     an entry that still holds several section numbers (lines merged in extraction)
  ja          the Japanese entry is missing or has a different section number
  unlinked    an entry with no heading or figure/table to link to
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.printed_toc import (LEADER, PAGE, TOC_HEADING, entry_key, is_toc_title,  # noqa: E402
                                         plain, printed_toc)

HIDDEN = ("page_furniture", "duplicate_artifact_of", "math_duplicate_of", "figure_text_of",
          "official_mark", "third_party_excerpt")
SECTION_START = re.compile(r"(?:^|\s)(\d{1,2}(?:\.\d{1,3})+|[A-Z]\.\d{1,3}(?:\.\d{1,3})*)\s+[A-Z]")
TOCLIKE = re.compile(r"(?:\.\s*){4,}\s*(?:[ivxlcdm]{1,7}|\d{1,4}(?:-\d{0,3})?|[A-Z]-\d{1,3})?\s*$", re.I)


def audit(path):
    document = json.loads(Path(path).read_text())
    blocks = [b for b in document["contents"] if not any(b.get(k) for k in HIDDEN)]
    toc = printed_toc(blocks)
    report = {"lines": 0, "entries": 0, "missed": [], "cut": [], "leftover": [], "unsplit": [], "ja": [], "unlinked": []}
    ids = [index for index, block in enumerate(blocks) if block["id"] in toc]
    report["lines"] = len(ids)
    for index, block in enumerate(blocks):
        text = plain(block.get("html"))
        if block["id"] in toc:
            continue
        if is_toc_title(blocks, index) or TOC_HEADING.match(text):
            # the first lines after a title may be the document title repeated (skipped)
            if index + 1 < len(blocks) and not any(b["id"] in toc for b in blocks[index + 1:index + 5]):
                report["missed"].append((block["id"], text[:60]))
        elif TOCLIKE.search(text) and len(text) < 300 and block.get("source_page", 99) < 20:
            report["missed"].append((block["id"], text[:60]))
    # a TOC that stops early: the next block after a run still looks like a TOC line
    for index in ids:
        if index + 1 < len(blocks) and blocks[index + 1]["id"] not in toc:
            following = plain(blocks[index + 1].get("html"))
            if TOCLIKE.search(following) or (PAGE.search(following) and SECTION_START.match(" " + following)):
                report["cut"].append((blocks[index + 1]["id"], following[:60]))
    for block_id, line in toc.items():
        for entry in line["entries"]:
            report["entries"] += 1
            if LEADER.search(entry["en"]) or re.search(r"(?:\.\s*){3,}", entry["en"]):
                report["leftover"].append((block_id, entry["en"][:60]))
            starts = SECTION_START.findall(" " + entry["en"])
            if len(starts) > 1:
                report["unsplit"].append((block_id, entry["en"][:80]))
            ja_key = entry_key(entry["ja"]) if entry["ja"] else None
            if not entry["ja"] or (entry["key"][0] == "number" and ja_key != entry["key"]
                                   and not re.match(r"\s*(第|付録|付属書|附属書)", entry["ja"])):
                report["ja"].append((block_id, entry["en"][:40], entry["ja"][:40]))
            if not entry["target"]:
                report["unlinked"].append((block_id, entry["en"][:60]))
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--out", type=Path)
    args = cli.parse_args()
    results = {}
    for path in sorted(glob.glob(str(ROOT / "data" / "*-trans.json"))):
        results[Path(path).name[:-len("-trans.json")]] = audit(path)
    keys = ("missed", "cut", "leftover", "unsplit", "ja", "unlinked")
    totals = {key: sum(len(r[key]) for r in results.values()) for key in keys}
    print("documents with a formatted TOC:", sum(1 for r in results.values() if r["lines"]),
          "entries:", sum(r["entries"] for r in results.values()))
    print("totals:", totals)
    for key in keys:
        worst = sorted(((len(r[key]), name) for name, r in results.items() if r[key]), reverse=True)[:8]
        print(" ", key, worst)
    if args.out:
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
