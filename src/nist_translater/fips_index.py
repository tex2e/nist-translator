"""Build the static index of the NIST FIPS translations (html/fips-index.html).

The SP 800 index (index_page.py, html/index.html) is left untouched; this
page reuses its progress counting and lists the FIPS publications only.
"""

import json
from collections import Counter
from pathlib import Path
from string import Template

from .fips_documents import FIPS_DOCUMENTS
from .index_page import _format_number, _load_document, _render_row

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path("data/fips-final-catalog.json")
OUTPUT = Path("html/fips-index.html")


def catalog_records():
    """One record per FIPS publication, in the shape the SP 800 index uses."""
    records = []
    for key, spec in FIPS_DOCUMENTS.items():
        records.append({
            "number": spec["number"].replace("FIPS ", ""),
            "title": spec["title"],
            "status": "Final",
            "release_date": spec.get("release_date", ""),
            "record_url": spec["catalog_record_url"],
            "json_path": "data/%s-trans.json" % spec["file_stem"],
            "html_path": "html/%s.html" % spec["file_stem"],
        })
    return records


def write_catalog(root=ROOT):
    path = Path(root) / CATALOG
    path.write_text(json.dumps({
        "source_url": "https://csrc.nist.gov/publications/fips",
        "selection_rule": "Current CSRC FIPS rows with Status=Final, except FIPS 140-2 (superseded by FIPS 140-3).",
        "record_count": len(FIPS_DOCUMENTS),
        "records": catalog_records(),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _row(record, progress):
    # The shared row renderer labels numbers "SP"; FIPS rows say "FIPS".
    return (_render_row(record, progress)
            .replace('aria-label="SP ', 'aria-label="FIPS ')
            .replace('>SP %s<' % record["number"], '>FIPS %s<' % record["number"])
            .replace('<td class="number">SP ', '<td class="number">FIPS '))


def build_fips_index(root=ROOT):
    root = Path(root).resolve()
    records = sorted(catalog_records(), key=lambda record: [
        int(part) if part.isdigit() else part for part in record["number"].replace("-", " ").split()])
    rows = [(record, _load_document(root, record)) for record in records]
    counts = Counter(progress["status"] for _, progress in rows)
    page = Template((root / "templates" / "fips-index.html").read_text(encoding="utf-8"))
    html = page.substitute(
        document_total=_format_number(len(records)),
        page_total=_format_number(sum(progress["html_available"] for _, progress in rows)),
        created_total=_format_number(counts["created"] + counts["reviewed"]),
        reviewed_total=_format_number(counts["reviewed"]),
        in_progress_total=_format_number(counts["in_progress"]),
        block_total=_format_number(sum(progress["total"] for _, progress in rows)),
        translated_total=_format_number(sum(progress["translated"] for _, progress in rows)),
        source_only_total=_format_number(sum(progress["source_only"] for _, progress in rows)),
        pending_total=_format_number(sum(max(0, progress["total"] - progress["processed"])
                                         for _, progress in rows)),
        table_rows="\n".join(_row(record, progress) for record, progress in rows),
    )
    output = root / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print("Built", build_fips_index())
