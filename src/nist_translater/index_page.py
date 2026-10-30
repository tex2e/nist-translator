"""Build the static index for the available NIST SP 800 translations."""

import json
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path("data/sp800-final-catalog.json")
OUTPUT = Path("html/index.html")


PAGE = Template((ROOT / "templates/index.html").read_text(encoding="utf-8"))


def _safe_path(root, relative_path):
    if not relative_path:
        return None
    candidate = (root / str(relative_path)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _load_document(root, record):
    json_path = _safe_path(root, record.get("json_path"))
    html_path = _safe_path(root, record.get("html_path"))
    document = None
    if json_path and json_path.is_file():
        try:
            document = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = None

    blocks = document.get("contents", []) if isinstance(document, dict) else []
    counts = Counter(block.get("status", "untranslated") for block in blocks)
    translated = sum(
        block.get("status") in {"draft", "reviewed"} and bool(block.get("html_ja", "").strip())
        for block in blocks
    )
    source_only = counts["source_only"]
    reviewed = sum(
        block.get("status") == "reviewed" and bool(block.get("html_ja", "").strip())
        for block in blocks
    )
    stale = counts["stale"]
    total = len(blocks)
    complete = translated > 0 and stale == 0 and all(
        (block.get("status") in {"draft", "reviewed"} and bool(block.get("html_ja", "").strip()))
        or block.get("status") == "source_only"
        for block in blocks
    )

    if document is None:
        status = "not_started"
    elif stale:
        status = "stale"
    elif complete:
        status = "reviewed" if reviewed == translated else "created"
    elif translated:
        status = "in_progress"
    else:
        status = "source_ready"

    title_ja = ""
    if isinstance(document, dict):
        title = document.get("title")
        if isinstance(title, dict):
            title_ja = title.get("html_ja", "")
        title_ja = title_ja or document.get("subtitle_ja", "")
    html_available = bool(html_path and html_path.is_file())

    return {
        "document": document,
        "total": total,
        "translated": translated,
        "reviewed": reviewed,
        "source_only": source_only,
        "processed": translated + source_only,
        "stale": stale,
        "status": status,
        "title_ja": title_ja,
        "html_available": html_available,
        "html_href": html_path.name if html_available else "",
        "partial": bool(isinstance(document, dict) and document.get("extraction_partial")),
        "extraction_pending": sum(block.get("extraction_status") == "needs_review" for block in blocks),
    }


def _format_number(value):
    return format(int(value), ",")


def _render_row(record, progress):
    esc = lambda value: escape(str(value or ""), quote=True)
    number = esc(record.get("number", ""))
    title = esc(record.get("title", ""))
    title_ja = esc(progress["title_ja"])
    raw_date = record.get("release_date", "")
    try:
        date_key = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        try:
            date_key = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_key = ""
    release_date = esc(date_key or raw_date)
    record_url = esc(record.get("record_url", ""))
    status = progress["status"]
    labels = {
        "created": ("訳文作成済み", "created"),
        "reviewed": ("訳文レビュー済み", "reviewed"),
        "in_progress": ("翻訳作業中", "progress"),
        "source_ready": ("日本語訳なし", ""),
        "not_started": ("未着手", ""),
        "stale": ("要再確認", "stale"),
    }
    label, badge_class = labels[status]
    badge_class_attr = " " + badge_class if badge_class else ""

    if progress["total"]:
        total = progress["total"]
        percent = 100 if progress["translated"] == total else min(99.9, round(progress["translated"] * 100 / total, 1))
        progress_html = (
            '<div class="bar" role="progressbar" aria-label="日本語訳 %s / %s ブロック" '
            'aria-valuemin="0" aria-valuemax="100" aria-valuenow="%s"><span style="width:%s%%"></span></div>'
            '<span class="progress-text">日本語訳 %s / %s ブロック</span>'
            '<span class="progress-text">訳文レビュー %s / %s</span>'
            '<span class="progress-text">原文保持 %s ブロック</span>'
        ) % (
            _format_number(progress["translated"]), _format_number(total), percent, percent,
            _format_number(progress["translated"]), _format_number(total),
            _format_number(progress["reviewed"]), _format_number(progress["translated"]),
            _format_number(progress["source_only"]),
        )
    else:
        progress_html = '<span class="progress-text">—</span>'

    if progress["html_available"]:
        href = esc(progress["html_href"])
        number = '<a href="%s" aria-label="SP %s の対訳を読む">SP %s</a>' % (href, number, number)
        title = '<a href="%s" class="title-link"><span lang="en">%s</span>%s</a>' % (
            href, title, '<span class="title-ja" lang="ja">%s</span>' % title_ja if title_ja else "")
        translation_link = '<a href="%s">対訳を読む</a>' % href
    else:
        number = 'SP ' + number
        title = '<span lang="en">%s</span>%s' % (
            title, '<span class="title-ja" lang="ja">%s</span>' % title_ja if title_ja else "")
        translation_link = '<span class="disabled-link">対訳ページなし</span>'
    source_link = '<a href="%s" target="_blank" rel="noopener noreferrer" aria-label="SP %s のNIST原文（新しいタブ）">NIST原文 ↗</a>' % (record_url, esc(record.get("number", "")))
    notes = []
    if progress["source_only"]:
        notes.append("原文保持あり")
    if progress["partial"]:
        notes.append("一部収録")
    if progress["extraction_pending"]:
        notes.append("原文抽出の照合待ち")
    state_notes = ''.join('<span class="state-note">%s</span>' % esc(note) for note in notes)
    search_text = esc(" ".join((record.get("number", ""), record.get("title", ""), progress["title_ja"])))

    return (
        '<tr data-status="%s" data-search="%s" data-number="%s" data-date="%s" data-available="%s">'
        '<td class="number">%s</td>'
        '<td class="title">%s</td>'
        '<td class="date" data-label="刊行日">%s</td>'
        '<td class="state" data-label="翻訳状態"><span class="badge%s">%s</span>%s</td>'
        '<td class="progress-cell" data-label="訳文の内訳">%s</td>'
        '<td class="links">%s %s</td>'
        '</tr>'
    ) % (
        esc(status), search_text, esc(record.get("number", "")), esc(date_key),
        "yes" if progress["html_available"] else "no", number, title, release_date or "—",
        badge_class_attr, esc(label), state_notes, progress_html, translation_link, source_link,
    )


def _historical_section(root, records):
    """Withdrawn publications that have a page but are not in the current Final catalog."""
    from .documents import DOCUMENTS
    listed = {record.get("number", "").replace("800-", "") for record in records}
    rows = []
    for key, spec in DOCUMENTS.items():
        if key in listed or key.startswith("fips-") or "歴史資料" not in spec.get("series", ""):
            continue
        page = "sp800-%s.html" % spec.get("slug", key)
        if not (root / "html" / page).is_file():
            continue
        esc = lambda value: escape(str(value or ""), quote=True)
        rows.append('<li><a href="%s">%s</a> %s（%s）</li>' % (
            esc(page), esc(spec["number"]), esc(spec.get("title_ja", "")), esc(spec.get("series", ""))))
    if not rows:
        return ""
    return ('<section class="historical" aria-label="廃止された資料"><h2>廃止された資料（歴史資料）</h2>'
            '<p>NIST が廃止した資料です。現在の要件ではなく、原文の記録・参照用の訳です。上の一覧（現行 Final）には含めていません。</p>'
            '<ul>%s</ul></section>' % "".join(rows))


def build_translation_index(root=ROOT):
    root = Path(root).resolve()
    catalog_path = root / CATALOG
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    records = catalog.get("records", [])
    progress_rows = [(record, _load_document(root, record)) for record in records]
    counts = Counter(progress["status"] for _, progress in progress_rows)

    block_total = sum(progress["total"] for _, progress in progress_rows)
    translated_total = sum(progress["translated"] for _, progress in progress_rows)
    source_only_total = sum(progress["source_only"] for _, progress in progress_rows)
    pending_total = sum(
        max(0, progress["total"] - progress["processed"])
        for _, progress in progress_rows
    )
    page_total = sum(progress["html_available"] for _, progress in progress_rows)

    html = PAGE.substitute(
        site_header=(root / "templates" / "header.html").read_text(encoding="utf-8"),
        document_total=_format_number(len(records)),
        page_total=_format_number(page_total),
        created_total=_format_number(counts["created"] + counts["reviewed"]),
        reviewed_total=_format_number(counts["reviewed"]),
        in_progress_total=_format_number(counts["in_progress"]),
        block_total=_format_number(block_total),
        translated_total=_format_number(translated_total),
        source_only_total=_format_number(source_only_total),
        pending_total=_format_number(pending_total),
        table_rows="\n".join(_render_row(record, progress) for record, progress in progress_rows),
        historical_section=_historical_section(root, records),
    )
    output_path = root / OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    output = build_translation_index()
    print("Built", output)
