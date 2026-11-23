"""Compare the Final SP 800 and IR lists on CSRC with the local catalogs and translations.

    python scripts/check_nist_updates.py [--json] [--skip STEM ...] [--no-remote]
    python scripts/check_nist_updates.py --register STEM

The first form changes nothing. It reports, for each series, the number of Final publications
on CSRC, in the local catalog and translated here, and lists:

- missing: on CSRC, not translated here. "next" is the one to translate today: the oldest
  release date first, so that nothing waits forever. A publication with a remote branch
  claude/translate-nist-<stem> (a pull request waiting to merge) is not chosen again.
- removed: in the local catalog, no longer a Final row on CSRC (usually withdrawn).
- date_changed: the release date on CSRC differs from the catalog (possibly a new edition).

Removed and changed publications are only reported; deciding what to do is left to a person.

--register adds one missing publication to its catalog, with the PDF URL and DOI from its record
page, so that main.py can fetch and parse it. Other catalog records are left as they are.
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from update_ir_final_catalog import fetch, record_details, stem_of  # noqa: E402

SERIES = {
    "sp800": {"url": "https://csrc.nist.gov/publications/sp800", "label": "SP",
              "catalog": "sp800-final-catalog.json"},
    "ir": {"url": "https://csrc.nist.gov/publications/ir", "label": "IR",
           "catalog": "ir-final-catalog.json"},
}
# Handled by hand (decided by the site's owner): never chosen for translation or reported as removed.
EXCLUDED = {
    "ir-7275r2": "CSRC・DOI・nvlpubs・Web アーカイブのどこにも原本が無い",
    "ir-7621r1": "CSRC で廃止されたが、翻訳済みのページは特別対応として残す",
}
# A parsing failure must not look like a mass withdrawal.
MIN_LIVE_RATIO = 0.9
BRANCH_PREFIX = "claude/translate-nist-"


def iso_date(value):
    value = value.strip()
    for layout in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, layout).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("Unknown date: %r" % value)


def sp_stem_of(record_url):
    """/pubs/sp/800/221/a/final → sp800-221a"""
    parts = [p for p in record_url.split("/pubs/sp/800/")[1].split("/") if p and p != "final"]
    return "sp800-" + "".join(parts).lower()


def stem_for(series, record_url):
    return sp_stem_of(record_url) if series == "sp800" else stem_of(record_url)


def parse_list(series, raw):
    """The Final rows of a CSRC publication list."""
    config = SERIES[series]
    table = BeautifulSoup(raw, "html.parser").find("table")
    if table is None:
        raise RuntimeError("No publication table on " + config["url"])
    records = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 5 or cells[0].get_text(strip=True) != config["label"]:
            continue
        if cells[3].get_text(strip=True) != "Final":
            continue
        number = re.sub(r"\s+", " ", cells[1].get_text(" ", strip=True))
        if series == "sp800" and not number.startswith("800-"):
            continue
        link = cells[2].find("a", id=re.compile(r"^pub-title-link-\d"))
        if link is None:
            continue
        record_url = urllib.parse.urljoin(config["url"], link["href"])
        records.append({
            "series": series,
            "number": number if series == "sp800" else "IR " + number,
            "title": re.sub(r"\s+", " ", link.get_text(" ", strip=True)),
            "status": "Final",
            "release_date": iso_date(cells[4].get_text(strip=True)),
            "record_url": record_url,
            "stem": stem_for(series, record_url),
        })
    return records


def catalog_path(root, series):
    return Path(root) / "data" / SERIES[series]["catalog"]


def local_stem(series, entry):
    if entry.get("stem"):
        return entry["stem"]
    if entry.get("json_path"):
        return Path(entry["json_path"]).name.removesuffix("-trans.json")
    return stem_for(series, entry["record_url"])


def is_translated(root, stem):
    return (Path(root) / "data" / (stem + "-trans.json")).is_file() and \
        (Path(root) / "html" / (stem + ".html")).is_file()


def compare(root, series, live, pending_stems=frozenset()):
    catalog = json.loads(catalog_path(root, series).read_text(encoding="utf-8"))["records"]
    if len(live) < len(catalog) * MIN_LIVE_RATIO:
        raise RuntimeError("%s: only %d Final rows on CSRC for %d in the catalog; the page may have changed"
                           % (series, len(live), len(catalog)))
    by_url = {entry["record_url"]: entry for entry in catalog}
    live_urls = {record["record_url"] for record in live}
    translated, excluded, missing, date_changed = 0, [], [], []
    for record in live:
        entry = by_url.get(record["record_url"])
        stem = local_stem(series, entry) if entry else record["stem"]
        record = dict(record, stem=stem)
        if stem in EXCLUDED:
            excluded.append({"stem": stem, "reason": EXCLUDED[stem]})
        elif is_translated(root, stem):
            translated += 1
        else:
            missing.append(dict(record, pending_pr=stem in pending_stems))
        if entry and iso_date(entry["release_date"]) != record["release_date"]:
            date_changed.append({"stem": stem, "number": record["number"], "catalog": iso_date(entry["release_date"]),
                                 "csrc": record["release_date"], "record_url": record["record_url"]})
    removed = [{"stem": local_stem(series, entry), "number": entry["number"], "title": entry["title"],
                "record_url": entry["record_url"]}
               for entry in catalog if entry["record_url"] not in live_urls and not entry.get("withdrawn")
               and local_stem(series, entry) not in EXCLUDED]
    return {"csrc": len(live), "catalog": len(catalog), "translated": translated, "excluded": excluded,
            "missing": missing, "removed": removed, "date_changed": date_changed}


def choose_next(results, skip=()):
    """The oldest publication that is neither waiting in a pull request nor skipped."""
    candidates = [record for result in results.values() for record in result["missing"]
                  if not record["pending_pr"] and record["stem"] not in skip]
    candidates.sort(key=lambda r: (r["release_date"], r["series"] != "sp800", r["stem"]))
    return candidates[0] if candidates else None


def pending_branches(root):
    output = subprocess.run(["git", "ls-remote", "--heads", "origin", BRANCH_PREFIX + "*"], cwd=root,
                            capture_output=True, text=True, check=True, timeout=60).stdout
    return {line.split("refs/heads/" + BRANCH_PREFIX, 1)[1].strip()
            for line in output.splitlines() if "refs/heads/" + BRANCH_PREFIX in line}


def register(root, record):
    """Add one publication to its catalog; returns the catalog record."""
    details = record_details({key: record[key] for key in ("number", "title", "status", "release_date",
                                                          "record_url", "stem")})
    if not details.get("pdf_url"):
        raise RuntimeError("No PDF found for " + record["stem"])
    series = record["series"]
    path = catalog_path(root, series)
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if any(entry["record_url"] == record["record_url"] for entry in catalog["records"]):
        raise RuntimeError(record["stem"] + " is already in the catalog")
    if series == "sp800":
        details.update(translation_status="not_started", translated_blocks=0, total_blocks=0,
                       json_path="data/%s-trans.json" % record["stem"], html_path="html/%s.html" % record["stem"])
    position = next((index for index, entry in enumerate(catalog["records"])
                     if iso_date(entry["release_date"]) <= record["release_date"]), len(catalog["records"]))
    catalog["records"].insert(position, details)
    catalog["record_count"] = len(catalog["records"])
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return details


def report_text(results, chosen):
    lines = []
    for series, result in results.items():
        lines.append("%-5s CSRC %d / catalog %d / translated %d / excluded %d / missing %d" % (
            SERIES[series]["label"], result["csrc"], result["catalog"], result["translated"],
            len(result["excluded"]), len(result["missing"])))
        for record in result["missing"]:
            lines.append("  missing  %s  %s  %s%s" % (record["release_date"], record["stem"], record["title"],
                                                     "  (PR waiting)" if record["pending_pr"] else ""))
        for record in result["removed"]:
            lines.append("  removed  %s  %s  %s" % (record["stem"], record["title"], record["record_url"]))
        for record in result["date_changed"]:
            lines.append("  date     %s  %s -> %s" % (record["stem"], record["catalog"], record["csrc"]))
    lines.append("next: " + (chosen["stem"] if chosen else "none"))
    return "\n".join(lines)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--json", action="store_true", help="print the result as JSON")
    cli.add_argument("--skip", action="append", default=[], metavar="STEM", help="do not choose this publication")
    cli.add_argument("--no-remote", action="store_true", help="do not look for branches on origin")
    cli.add_argument("--register", metavar="STEM", help="add this missing publication to its catalog")
    args = cli.parse_args()
    pending = set() if args.no_remote else pending_branches(ROOT)
    results = {series: compare(ROOT, series, parse_list(series, fetch(config["url"])), pending)
               for series, config in SERIES.items()}
    if args.register:
        record = next((item for result in results.values() for item in result["missing"]
                       if item["stem"] == args.register), None)
        if record is None:
            raise SystemExit(args.register + " is not a missing publication")
        print(json.dumps(register(ROOT, record), ensure_ascii=False, indent=2))
        return
    chosen = choose_next(results, args.skip)
    if args.json:
        print(json.dumps({"series": results, "next": chosen}, ensure_ascii=False, indent=2))
    else:
        print(report_text(results, chosen))


if __name__ == "__main__":
    main()
