"""Generate the static side-by-side reading page."""

from datetime import datetime

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .translation import audit_translations


PDF_URL = "https://doi.org/10.6028/NIST.SP.800-63b-4"


def build_site(document, meta, template_path, output_path):
    audit_translations(document)
    visible = []
    translated = 0
    stale = 0
    headings = []
    for block in document["contents"]:
        item = dict(block)
        item["english_html"] = Markup(block["html"])
        item["japanese_html"] = Markup(block["html_ja"])
        if block["html_ja"] and block["status"] in {"draft", "reviewed"}:
            translated += 1
        elif block["status"] == "stale":
            item["html_ja"] = ""
            item["status"] = "stale"
            stale += 1
        elif not block["html_ja"]:
            item["html_ja"] = ""
            item["status"] = "missing"
        visible.append(item)
        if block["kind"] == "heading":
            headings.append({"id": block["id"], "text": " ".join(
                BeautifulSoup(block["html"], "html.parser").stripped_strings),
                "level": block["level"]})

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    fetched_at = meta.get("fetched_at")
    if fetched_at:
        fetched_at = datetime.fromisoformat(fetched_at).strftime("%Y-%m-%d")
    page = env.get_template(template_path.name).render(
        title=document["title"]["text"], number=document.get("number", "SP 800-63B-4"),
        subtitle=document.get("subtitle", "Authentication & Authenticator Management"),
        description=document.get("description", "SP 800-63B の英文と日本語訳を段落ごとに並べた閲覧用ページです。"),
        source_url=document["source_url"], pdf_url=document.get("pdf_url", PDF_URL),
        fetched_at=fetched_at or "取得日不明", headings=headings,
        blocks=visible, translated=translated, total=len(visible), stale=stale,
    )
    output_path.write_text(page, encoding="utf-8")
