"""Build the static index for the available NIST SP 800 translations."""

import json
from collections import Counter
from html import escape
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path("data/sp800-final-catalog.json")
OUTPUT = Path("html/index.html")


PAGE = Template("""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="NIST SP 800の英日対訳資料一覧">
  <title>NIST SP 800 英日対訳一覧</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #182230;
      --muted: #586575;
      --line: #d8e0e8;
      --blue: #145da0;
      --blue-dark: #0d416f;
      --pale: #f3f7fb;
      --green: #176b45;
      --amber: #8a5100;
      --red: #9f2929;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f6f8fa;
      color: var(--ink);
      font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    a { color: var(--blue); }
    a:hover { color: var(--blue-dark); }
    .site-header {
      background: #fff;
      border-bottom: 1px solid var(--line);
    }
    .header-inner, main, footer {
      width: min(1180px, calc(100% - 2rem));
      margin: 0 auto;
    }
    .header-inner {
      min-height: 58px;
      display: flex;
      align-items: center;
    }
    .brand {
      color: var(--ink);
      font-size: 1rem;
      font-weight: 750;
      text-decoration: none;
    }
    main { padding: 2rem 0 3rem; }
    .eyebrow {
      margin: 0 0 .35rem;
      color: var(--blue);
      font-size: .75rem;
      font-weight: 750;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 2.5rem);
      line-height: 1.2;
    }
    .lede {
      max-width: 78ch;
      margin: .8rem 0 1.1rem;
      color: #394656;
    }
    .notice {
      max-width: 90ch;
      margin: 0 0 1.5rem;
      padding: .75rem 1rem;
      border-left: 3px solid var(--blue);
      background: #fff;
      color: #394656;
      font-size: .9rem;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: .8rem;
      margin: 1.25rem 0 1.5rem;
    }
    .stat {
      min-height: 88px;
      padding: .85rem 1rem;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .stat-label { display: block; color: var(--muted); font-size: .78rem; }
    .stat-value { display: block; margin-top: .15rem; font-size: 1.35rem; font-weight: 750; }
    .block-summary { color: var(--muted); font-size: .88rem; margin: -.5rem 0 1.5rem; }
    .controls {
      display: flex;
      gap: .8rem;
      align-items: end;
      flex-wrap: wrap;
      margin-bottom: .7rem;
    }
    .field { display: grid; gap: .25rem; }
    .field label { font-size: .8rem; font-weight: 700; }
    input, select {
      min-height: 42px;
      padding: .5rem .7rem;
      border: 1px solid #aebac7;
      border-radius: 5px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    input { width: min(440px, 78vw); }
    select { min-width: 170px; }
    input:focus, select:focus { outline: 3px solid #bedbfa; border-color: var(--blue); }
    .result-count { margin: 0 0 .5rem; color: var(--muted); font-size: .82rem; }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    table { width: 100%; min-width: 900px; border-collapse: collapse; }
    th, td { padding: .75rem .8rem; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #edf3f8;
      color: #334255;
      font-size: .78rem;
      white-space: nowrap;
    }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr:hover { background: #f8fbfe; }
    td.number { width: 140px; white-space: nowrap; font-weight: 700; }
    td.title { min-width: 310px; }
    .title-en { display: block; font-weight: 600; }
    .title-ja { display: block; margin-top: .15rem; color: var(--muted); font-size: .86rem; }
    td.date { width: 105px; white-space: nowrap; color: var(--muted); font-size: .86rem; }
    td.state { width: 155px; }
    .badge {
      display: inline-block;
      padding: .14rem .5rem;
      border-radius: 999px;
      background: #edf1f5;
      color: #394656;
      font-size: .75rem;
      font-weight: 700;
      white-space: nowrap;
    }
    .badge.complete { background: #e5f4ec; color: var(--green); }
    .badge.progress { background: #fff2db; color: var(--amber); }
    .badge.stale { background: #fdeaea; color: var(--red); }
    .progress-cell { min-width: 185px; }
    .bar {
      height: 7px;
      overflow: hidden;
      margin: .12rem 0 .25rem;
      border-radius: 10px;
      background: #e7edf3;
    }
    .bar span { display: block; height: 100%; border-radius: inherit; background: #36815d; }
    .progress-text { color: var(--muted); font-size: .73rem; white-space: nowrap; }
    td.links { width: 125px; white-space: nowrap; }
    td.links a { margin-right: .45rem; font-size: .83rem; font-weight: 650; }
    .disabled-link { color: #8995a0; font-size: .8rem; }
    footer {
      padding: 1rem 0 2rem;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: .8rem;
    }
    @media (max-width: 760px) {
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      main { padding-top: 1.35rem; }
    }
  </style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner"><a class="brand" href="index.html">NIST SP 800 英日対訳</a></div>
  </header>
  <main>
    <p class="eyebrow">NIST Special Publication 800</p>
    <h1>英日対訳資料一覧</h1>
    <p class="lede">NIST SP 800の現行Final資料と、このサイトで閲覧できる英日対訳ページを一覧にしています。資料番号またはタイトルで検索できます。</p>
    <p class="notice">このサイトは非公式の閲覧用資料です。翻訳やPDFからの抽出に誤り・欠落があり得るため、要件の確認にはNISTの原文を参照してください。</p>

    <section class="summary" aria-label="一覧の概要">
      <div class="stat"><span class="stat-label">対象資料</span><strong class="stat-value">$document_total</strong></div>
      <div class="stat"><span class="stat-label">対訳HTMLあり</span><strong class="stat-value">$page_total</strong></div>
      <div class="stat"><span class="stat-label">翻訳完了</span><strong class="stat-value">$complete_total</strong></div>
      <div class="stat"><span class="stat-label">翻訳作業中</span><strong class="stat-value">$in_progress_total</strong></div>
    </section>
    <p class="block-summary">JSON登録分のブロック: $block_total 件（日本語訳 $translated_total 件、原文のみ $source_only_total 件、未訳・要再確認 $pending_total 件）。資料ごとの進捗はJSONから再集計しています。</p>

    <div class="controls">
      <div class="field">
        <label for="search">資料番号・タイトルで検索</label>
        <input id="search" type="search" autocomplete="off" placeholder="例: 800-53、Zero Trust、暗号">
      </div>
      <div class="field">
        <label for="status-filter">進捗で絞り込み</label>
        <select id="status-filter">
          <option value="all">すべて</option>
          <option value="complete">翻訳完了</option>
          <option value="in_progress">翻訳作業中</option>
          <option value="not_started">未着手・原文登録済み</option>
          <option value="stale">要再確認</option>
        </select>
      </div>
    </div>
    <p id="result-count" class="result-count" aria-live="polite">$document_total 件を表示</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">資料番号</th>
            <th scope="col">タイトル</th>
            <th scope="col">刊行日</th>
            <th scope="col">翻訳状態</th>
            <th scope="col">ブロック進捗</th>
            <th scope="col">リンク</th>
          </tr>
        </thead>
        <tbody>
          $table_rows
        </tbody>
      </table>
    </div>
  </main>
  <footer>一覧データ: <a href="https://csrc.nist.gov/publications/sp800">NIST SP 800 Publications</a>。各行の「原文」はNISTの資料ページを開きます。</footer>
  <script>
    (() => {
      const search = document.getElementById("search");
      const statusFilter = document.getElementById("status-filter");
      const rows = Array.from(document.querySelectorAll("tbody tr"));
      const resultCount = document.getElementById("result-count");
      const update = () => {
        const query = search.value.trim().toLocaleLowerCase();
        const filter = statusFilter.value;
        let visible = 0;
        for (const row of rows) {
          const matchesText = row.textContent.toLocaleLowerCase().includes(query);
          const rowStatus = row.dataset.status;
          const matchesStatus = filter === "all"
            || rowStatus === filter
            || (filter === "not_started" && rowStatus === "source_ready");
          row.hidden = !(matchesText && matchesStatus);
          if (!row.hidden) visible += 1;
        }
        resultCount.textContent = visible.toLocaleString("ja-JP") + " 件を表示";
      };
      search.addEventListener("input", update);
      statusFilter.addEventListener("change", update);
      update();
    })();
  </script>
</body>
</html>
""")


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
    stale = counts["stale"]
    total = len(blocks)
    complete = total > 0 and stale == 0 and all(
        (block.get("status") in {"draft", "reviewed"} and bool(block.get("html_ja", "").strip()))
        or block.get("status") == "source_only"
        for block in blocks
    )

    if document is None:
        status = "not_started"
    elif stale:
        status = "stale"
    elif complete:
        status = "complete"
    elif translated or source_only:
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
        "source_only": source_only,
        "processed": translated + source_only,
        "stale": stale,
        "status": status,
        "title_ja": title_ja,
        "html_available": html_available,
        "html_href": html_path.name if html_available else "",
    }


def _format_number(value):
    return format(int(value), ",")


def _render_row(record, progress):
    esc = lambda value: escape(str(value or ""), quote=True)
    number = esc(record.get("number", ""))
    title = esc(record.get("title", ""))
    title_ja = esc(progress["title_ja"])
    release_date = esc(record.get("release_date", ""))
    record_url = esc(record.get("record_url", ""))
    status = progress["status"]
    labels = {
        "complete": ("翻訳完了", "complete"),
        "in_progress": ("翻訳作業中", "progress"),
        "source_ready": ("原文登録済み・未着手", ""),
        "not_started": ("未着手", ""),
        "stale": ("要再確認", "stale"),
    }
    label, badge_class = labels[status]
    badge_class_attr = " " + badge_class if badge_class else ""

    if progress["total"]:
        total = progress["total"]
        processed = progress["processed"]
        percent = min(100, round(processed * 100 / total))
        progress_html = (
            '<div class="bar" role="progressbar" aria-label="処理済み %s / %s ブロック" '
            'aria-valuemin="0" aria-valuemax="100" aria-valuenow="%s"><span style="width:%s%%"></span></div>'
            '<span class="progress-text">日本語訳 %s / %s ・原文のみ %s</span>'
        ) % (
            _format_number(processed), _format_number(total), percent, percent,
            _format_number(progress["translated"]), _format_number(total),
            _format_number(progress["source_only"]),
        )
    else:
        progress_html = '<span class="progress-text">—</span>'

    if progress["html_available"]:
        translation_link = '<a href="%s">対訳</a>' % esc(progress["html_href"])
    else:
        translation_link = '<span class="disabled-link">未生成</span>'
    source_link = '<a href="%s" target="_blank" rel="noopener noreferrer">原文</a>' % record_url
    title_ja_html = '<span class="title-ja" lang="ja">%s</span>' % title_ja if title_ja else ""
    search_text = esc(" ".join((record.get("number", ""), record.get("title", ""), progress["title_ja"])))

    return (
        '<tr data-status="%s" data-search="%s">'
        '<td class="number">SP %s</td>'
        '<td class="title"><span class="title-en">%s</span>%s</td>'
        '<td class="date">%s</td>'
        '<td class="state"><span class="badge%s">%s</span></td>'
        '<td class="progress-cell">%s</td>'
        '<td class="links">%s %s</td>'
        '</tr>'
    ) % (
        esc(status), search_text, number, title, title_ja_html, release_date,
        badge_class_attr, esc(label), progress_html, translation_link, source_link,
    )


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
        document_total=_format_number(len(records)),
        page_total=_format_number(page_total),
        complete_total=_format_number(counts["complete"]),
        in_progress_total=_format_number(counts["in_progress"]),
        block_total=_format_number(block_total),
        translated_total=_format_number(translated_total),
        source_only_total=_format_number(source_only_total),
        pending_total=_format_number(pending_total),
        table_rows="\n".join(_render_row(record, progress) for record, progress in progress_rows),
    )
    output_path = root / OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    output = build_translation_index()
    print("Built", output)
