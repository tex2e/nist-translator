"""Generate the static side-by-side reading page."""

from datetime import datetime
import html

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .translation import audit_translations


PDF_URL = "https://doi.org/10.6028/NIST.SP.800-63b-4"
OFFICIAL_MARKS = {
    "nist_logo": ("NIST logo", "NIST のロゴ"),
    "doc_seal": ("U.S. Department of Commerce seal", "米国商務省の紋章"),
    "contains_nist_logo": ("Figure that shows the NIST logo", "NIST のロゴが写っている図"),
}


def build_site(document, meta, template_path, output_path):
    audit_translations(document)
    math_groups = document.get("math_groups", [])
    math_by_member = {
        member: group
        for group in math_groups
        for member in group["members"]
    }
    content_by_id = {block["id"]: block for block in document["contents"]}
    visible = []
    translated = 0
    stale = 0
    headings = []
    for block in document["contents"]:
        if (block.get("duplicate_artifact_of") or block.get("math_duplicate_of") or
                block.get("page_furniture")):
            continue
        math_group = math_by_member.get(block["id"])
        if math_group:
            if block["id"] != math_group["members"][0]:
                continue
            members = [content_by_id[key] for key in math_group["members"]]
            pages = sorted({item["source_page"] for item in members})
            item = dict(block)
            item["kind"] = "math"
            item["html_ja"] = math_group.get("tex_ja", math_group["tex"])
            item["status"] = "draft"
            item["extraction_status"] = (
                "needs_review" if any(part.get("extraction_status") == "needs_review"
                                      for part in members) else "verified"
            )
            prefix_en = math_group.get("prefix_html", "")
            prefix_ja = math_group.get("prefix_html_ja", "")
            item["english_html"] = Markup(
                prefix_en + '<div class="math-content">'
                + html.escape(math_group["tex"]) + "</div>"
            )
            item["japanese_html"] = Markup(
                prefix_ja + '<div class="math-content">'
                + html.escape(math_group.get("tex_ja", math_group["tex"])) + "</div>"
            )
            item["source_page"] = pages[0]
            item["source_page_end"] = pages[-1]
            if document.get("source_format") == "pdf":
                item["source_page_url"] = document["source_url"] + "#page=%d" % pages[0]
            visible.append(item)
            if item["html_ja"]:
                translated += 1
            if item["extraction_status"] == "needs_review":
                item["extraction_pending"] = True
            continue
        # Empty extraction records have no source content to pair. Showing
        # "translation pending" for them creates misleading blank rows.
        if not block["html"].strip():
            continue
        item = dict(block)
        item["english_html"] = Markup(block["html"])
        item["japanese_html"] = Markup(block["html_ja"])
        if block.get("official_mark"):
            # An unofficial translation must not display protected official marks.
            name_en, name_ja = OFFICIAL_MARKS[block["official_mark"]]
            sources = [image.get("src", "") for image in
                       BeautifulSoup(block["html"], "html.parser").find_all("img")]
            for source in sources + [block.get("source_image") or ""]:
                published = output_path.parent / source
                if source and published.is_file():
                    published.unlink()  # a re-extraction may have written it again
            item["source_image"] = None  # a crop of the original that shows the mark
            if block["kind"] == "figure":
                item["english_html"] = Markup(
                    '<span class="withheld-mark">[%s — not reproduced on this unofficial site]</span>'
                    % name_en)
                described = BeautifulSoup(block["html_ja"] or "", "html.parser").find("img")
                item["figure_description"] = (
                    (described.get("alt", "") + " " if described and
                     block["official_mark"] == "contains_nist_logo" else "") +
                    "［%s。公的な標章のため、この非公式サイトには掲載していない。原本 PDF を参照。］" % name_ja)
        elif block["kind"] == "figure" and block["html_ja"]:
            translated_figure = BeautifulSoup(block["html_ja"], "html.parser").find("img")
            item["figure_description"] = translated_figure.get("alt", "") if translated_figure else ""
        if document.get("source_format") == "pdf" and block.get("source_page"):
            item["source_page_url"] = document["source_url"] + "#page=%d" % block["source_page"]
        if block["html_ja"] and block["status"] in {"draft", "reviewed"}:
            translated += 1
        elif block["status"] == "stale":
            item["html_ja"] = ""
            item["status"] = "stale"
            stale += 1
        elif block["status"] == "source_only":
            item["html_ja"] = ""
            item["status"] = "source_only"
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
        title=document["title"]["text"], title_ja=document["title"].get("html_ja", ""),
        number=document.get("number", "SP 800-63B-4"),
        subtitle=document.get("subtitle", "Authentication & Authenticator Management"),
        subtitle_ja=document.get("subtitle_ja", ""),
        description=document.get("description", "SP 800-63B の英文と日本語訳を段落ごとに並べた閲覧用ページです。"),
        source_url=document["source_url"], pdf_url=document.get("pdf_url", PDF_URL),
        source_format=document.get("source_format", "html"),
        series=document.get("series", "Digital Identity Guidelines · Revision 4"),
        included_pages=document.get("included_pages", []),
        extraction_partial=document.get("extraction_partial", False),
        extraction_pending=sum(block.get("extraction_status") == "needs_review"
                               for block in visible),
        extraction_warnings=document.get("extraction_warnings", []),
        has_math=bool(math_groups) or any(block.get("kind") == "math" or "data-tex=" in block.get("html", "") for block in document["contents"]),
        math_preservation=document.get("math_preservation"),
        math_pending=sum(block.get("kind") == "math" and
                         (block.get("extraction_status") == "needs_review" or
                          block.get("status") != "reviewed")
                         for block in document["contents"]),
        fetched_at=fetched_at or "取得日不明", headings=headings,
        blocks=visible, translated=translated, total=len(visible), stale=stale,
    )
    output_path.write_text(page, encoding="utf-8")
