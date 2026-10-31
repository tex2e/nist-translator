"""Snapshot the Final NIST IR (Interagency or Internal Report) list from CSRC.

    python scripts/update_ir_final_catalog.py [--jobs N]

Writes data/ir-final-catalog.json. The CSRC list (https://csrc.nist.gov/publications/ir) shows
the current edition of each report; rows with Status=Final are kept. Each record page gives the
PDF download URL, the DOI, and whether the report has been withdrawn.
Each record's "stem" (ir-8286ar1, ir-8170upd1) names its files: data/<stem>.pdf,
data/<stem>-trans.json, html/<stem>.html.
"""

import argparse
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://csrc.nist.gov/publications/ir"
OUTPUT = ROOT / "data" / "ir-final-catalog.json"
AGENT = {"User-Agent": "nist-translater/0.1 (bilingual reading copy)"}


def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def stem_of(record_url):
    """/pubs/ir/8286/a/r1/final → ir-8286ar1"""
    parts = [p for p in record_url.split("/pubs/ir/")[1].split("/") if p and p != "final"]
    return "ir-" + "".join(parts).lower()


def record_details(record):
    soup = BeautifulSoup(fetch(record["record_url"]), "html.parser")
    pdf = doi = None
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not doi and href.startswith("https://doi.org/10.6028/"):
            doi = href.strip()
        # nvlpubs for most reports; older ones are on CSRC (/files/...) or tsapps (get_pdf.cfm)
        if not pdf and (href.lower().endswith(".pdf") or "get_pdf.cfm" in href) and "markup" not in href:
            pdf = urljoin(record["record_url"], href)
    withdrawn = soup.find(id=lambda x: x and "pub-withdrawn" in x)
    record.update({
        "pdf_url": pdf,
        "doi": doi,
        "withdrawn": bool(withdrawn and withdrawn.get_text(strip=True)),
    })
    return record


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--jobs", type=int, default=4)
    args = cli.parse_args()
    soup = BeautifulSoup(fetch(SOURCE_URL), "html.parser")
    records = []
    for row in soup.find("table").find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 5 or cells[0].get_text(strip=True) != "IR" or cells[3].get_text(strip=True) != "Final":
            continue
        link = cells[2].find("a", id=re.compile(r"^pub-title-link-\d"))
        record_url = urljoin(SOURCE_URL, link["href"])
        records.append({
            "number": "IR " + re.sub(r"\s+", " ", cells[1].get_text(" ", strip=True)),
            "title": re.sub(r"\s+", " ", link.get_text(" ", strip=True)),
            "status": "Final",
            "release_date": datetime.strptime(cells[4].get_text(strip=True), "%m/%d/%Y").strftime("%Y-%m-%d"),
            "record_url": record_url,
            "stem": stem_of(record_url),
        })
    with ThreadPoolExecutor(args.jobs) as pool:
        records = list(pool.map(record_details, records))
    catalog = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCE_URL,
        "selection_rule": "Current CSRC NIST IR rows with Series=IR and Status=Final.",
        "record_count": len(records),
        "records": records,
    }
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    print(len(records), "records;", sum(1 for r in records if not r["pdf_url"]), "without a PDF;",
          sum(r["withdrawn"] for r in records), "withdrawn")


if __name__ == "__main__":
    main()
