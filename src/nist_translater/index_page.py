"""Build the site's top page: one searchable list of the SP 800 and FIPS translations."""

import json
import re
from html import escape
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("html/index.html")


PAGE = Template((ROOT / "templates/index.html").read_text(encoding="utf-8"))


def _format_number(value):
    return format(int(value), ",")


def _natural(text):
    """Sort key text: "SP 800-53 Rev. 5" before "SP 800-53A", numbers compared by value."""
    return "".join("%06d" % int(part) if part.isdigit() else part.lower()
                   for part in re.split(r"(\d+)", text))


def _render_row(entry):
    """One row of the list: number, English and Japanese titles, publication date."""
    esc = lambda value: escape(str(value or ""), quote=True)
    href = esc(entry["href"])
    withdrawn = '<span class="tag">廃止</span>' if entry["withdrawn"] else ""
    title_ja = '<span class="ja" lang="ja">%s</span>' % esc(entry["title_ja"]) if entry["title_ja"] else ""
    date = entry["date"]
    return (
        '<tr data-series="%s" data-withdrawn="%s" data-order="%s" data-date="%s" data-search="%s">'
        '<td class="number"><a href="%s">%s</a></td>'
        '<td class="title"><a href="%s" tabindex="-1"><span class="en" lang="en">%s%s</span>%s</a></td>'
        '<td class="date">%s</td>'
        '</tr>'
    ) % (
        entry["series"], "1" if entry["withdrawn"] else "0", esc(entry["order"]), esc(date),
        esc(" ".join((entry["number"], entry["title"], entry["title_ja"], entry["summary"]))),
        href, esc(entry["number"]), href, esc(entry["title"]), withdrawn, title_ja,
        '<time datetime="%s">%s</time>' % (esc(date), esc(date)) if date else "—",
    )


def _entries(root):
    """Every document with a page: SP 800 (current and withdrawn) and FIPS."""
    from .cli import release_date
    from .documents import DOCUMENTS, document_paths
    entries = []
    for key, spec in DOCUMENTS.items():
        paths = document_paths(root, key)
        if not paths["html"].is_file():
            continue
        # the Japanese title shown in the page's blue panel; a title that is only the number is no title
        title_ja = next((value for value in (spec.get("subtitle_ja"), spec.get("title_ja"))
                         if value and re.search(r"[ぁ-んァ-ヶ一-龥]", value)), "")
        summary = ""
        summary_path = paths["json"].with_name(paths["json"].name.replace("-trans.json", "-summary.json"))
        if summary_path.is_file():
            summary = " ".join(json.loads(summary_path.read_text(encoding="utf-8")).get("summary", []))
        fips = key.startswith("fips-")
        entries.append({
            "series": "fips" if fips else "sp800",
            "number": spec["number"],
            "title": spec["title"],
            "title_ja": title_ja,
            "date": release_date(spec),
            "withdrawn": "廃止" in spec.get("series", ""),
            "href": paths["html"].name,
            "summary": summary,
            # SP 800 first, then FIPS; within a series by number
            "order": ("2 " if fips else "1 ") + _natural(spec["number"]),
        })
    return sorted(entries, key=lambda entry: entry["order"])


def build_translation_index(root=ROOT):
    root = Path(root).resolve()
    entries = _entries(root)
    sp_total = sum(entry["series"] == "sp800" for entry in entries)
    fips_total = sum(entry["series"] == "fips" for entry in entries)
    html = PAGE.substitute(
        site_header=(Path(__file__).resolve().parents[2] / "templates" / "header.html").read_text(encoding="utf-8"),
        all_total=_format_number(len(entries)),
        sp_total=_format_number(sp_total),
        fips_total=_format_number(fips_total),
        rows="\n".join(_render_row(entry) for entry in entries),
    )
    output_path = root / OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    output = build_translation_index()
    print("Built", output)
