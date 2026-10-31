"""Metadata for the Final NIST IRs (Interagency or Internal Reports), from data/ir-final-catalog.json.

Keys and file stems are "ir-<number>" taken from the CSRC record path (ir-8286ar1, ir-8170upd1),
so the files never clash with SP 800 or FIPS files. A report without a PDF on CSRC is skipped.
The Japanese title is filled in from the translated document when it exists.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "ir-final-catalog.json"
SERIES = "NIST Interagency or Internal Report · PDF 原文抽出"


def _ir_documents():
    if not CATALOG.is_file():
        return {}
    documents = {}
    for record in json.loads(CATALOG.read_text(encoding="utf-8"))["records"]:
        if not record.get("pdf_url"):
            continue
        stem = record["stem"]
        spec = {
            "family": "ir",
            "number": record["number"],
            "title": record["title"],
            "title_ja": "",
            "subtitle_ja": "",
            "slug": stem,
            "file_stem": stem,
            "home_url": "index.html?series=ir",
            "description": "",
            "source_format": "pdf",
            "source_url": record["pdf_url"],
            "pdf_url": record.get("doi") or record["pdf_url"],
            "catalog_record_url": record["record_url"],
            "release_date": record["release_date"],
            "series": SERIES,
        }
        trans = ROOT / "data" / (stem + "-trans.json")
        if trans.is_file():
            document = json.loads(trans.read_text(encoding="utf-8"))
            for key in ("title_ja", "subtitle_ja", "description"):
                if document.get(key):
                    spec[key] = document[key]
        documents[stem] = spec
    return documents


IR_DOCUMENTS = _ir_documents()
