"""Snapshot the current Final SP 800 publication list from NIST CSRC."""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.nist_translater.index_page import build_translation_index

SOURCE_URL = "https://csrc.nist.gov/publications/sp800"
OUTPUT = ROOT / "data" / "sp800-final-catalog.json"


def _normal_number(value):
    value = re.sub(r"^\s*SP\s*", "", value, flags=re.I)
    # Keep revision and volume identifiers so one translated edition is not
    # incorrectly counted as every Final revision. The catalog number omits
    # Update labels even when its record URL points at an updated PDF.
    value = re.sub(r"\s*\(?UPDATE\s*[0-9A-Z]+\)?\s*$", "", value, flags=re.I)
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _translation_progress():
    progress = {"by_number": {}, "by_record_url": {}}
    for path in (ROOT / "data").glob("sp800-*-trans.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        number = document.get("number", "")
        key = _normal_number(number)
        blocks = document.get("contents", [])
        if not key or not blocks:
            continue
        translated = sum(
            block.get("status") in {"draft", "reviewed"}
            and bool(block.get("html_ja", "").strip())
            for block in blocks
        )
        source_only = sum(block.get("status") == "source_only" for block in blocks)
        complete = all(
            block.get("status") in {"draft", "reviewed", "source_only"}
            and (block.get("html_ja", "").strip() or block.get("status") == "source_only")
            for block in blocks
        )
        state = "translated" if complete else "in_progress" if translated or source_only else "not_started"
        slug = path.name.removeprefix("sp800-").removesuffix("-trans.json")
        item = {
            "translation_status": state,
            "translated_blocks": translated,
            "source_only_blocks": source_only,
            "total_blocks": len(blocks),
            "json_path": path.relative_to(ROOT).as_posix(),
            "html_path": (ROOT / "html" / ("sp800-%s.html" % slug)).relative_to(ROOT).as_posix(),
        }
        if key:
            progress["by_number"][key] = item
        record_url = document.get("catalog_record_url")
        if record_url:
            progress["by_record_url"][record_url] = item
    return progress


def fetch_catalog():
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "nist-translater/0.1 (bilingual reading copy)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    soup = BeautifulSoup(raw, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("The CSRC SP 800 publication table was not found")

    rows = table.select("tbody tr") or table.select("tr")[1:]
    records = []
    progress = _translation_progress()
    for row in rows:
        series = row.find(id=re.compile(r"^pub-series-\d+$"))
        number = row.find(id=re.compile(r"^pub-number-\d+$"))
        status = row.find(id=re.compile(r"^pub-status-\d+$"))
        release_date = row.find(id=re.compile(r"^pub-release-date-\d+$"))
        title_link = row.find(id=re.compile(r"^pub-title-link-\d+$"))
        if not all((series, number, status, release_date, title_link)):
            continue
        series_text = series.get_text(" ", strip=True)
        number_text = number.get_text(" ", strip=True)
        status_text = status.get_text(" ", strip=True)
        if series_text != "SP" or not number_text.startswith("800-") or status_text != "Final":
            continue
        key = _normal_number(number_text)
        record = {
            "number": number_text,
            "title": title_link.get_text(" ", strip=True),
            "status": status_text,
            "release_date": release_date.get_text(" ", strip=True),
            "record_url": urljoin(SOURCE_URL, title_link.get("href", "")),
        }
        progress_item = progress["by_record_url"].get(record["record_url"])
        if progress_item is None:
            progress_item = progress["by_number"].get(key)
        record.update(progress_item or {
            "translation_status": "not_started",
            "translated_blocks": 0,
            "total_blocks": 0,
        })
        records.append(record)

    if not records:
        raise RuntimeError("No current Final SP 800 records were parsed")
    return {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCE_URL,
        "selection_rule": "Current CSRC SP 800 rows with Series=SP, Number beginning 800-, and Status=Final.",
        "record_count": len(records),
        "records": records,
    }


def main():
    catalog = fetch_catalog()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    translated = sum(item["translation_status"] == "translated" for item in catalog["records"])
    in_progress = sum(item["translation_status"] == "in_progress" for item in catalog["records"])
    print("Saved %d current Final SP 800 records to %s" % (catalog["record_count"], OUTPUT))
    print("Translation progress: %d translated, %d in progress" % (translated, in_progress))
    print("Built", build_translation_index(ROOT))


if __name__ == "__main__":
    main()
