"""SP 800 publications added through data/sp800-final-catalog.json.

scripts/check_nist_updates.py --register gives a new publication "stem" and "pdf_url" in the
catalog. Publications listed by hand in documents.py have neither and are not touched here.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "sp800-final-catalog.json"
SERIES = "NIST Special Publication · PDF 原文抽出"


def catalog_documents():
    if not CATALOG.is_file():
        return {}
    documents = {}
    for record in json.loads(CATALOG.read_text(encoding="utf-8"))["records"]:
        if not (record.get("pdf_url") and record.get("stem")):
            continue
        slug = record["stem"].removeprefix("sp800-")
        spec = {
            "number": "SP " + record["number"],
            "title": record["title"],
            "title_ja": "",
            "subtitle_ja": "",
            "slug": slug,
            "description": "",
            "source_format": "pdf",
            "source_url": record["pdf_url"],
            "pdf_url": record.get("doi") or record["pdf_url"],
            "catalog_record_url": record["record_url"],
            "release_date": record["release_date"],
            "series": SERIES,
        }
        trans = ROOT / "data" / (record["stem"] + "-trans.json")
        if trans.is_file():
            document = json.loads(trans.read_text(encoding="utf-8"))
            for key in ("title_ja", "subtitle_ja", "description"):
                if document.get(key):
                    spec[key] = document[key]
        documents[slug] = spec
    return documents
