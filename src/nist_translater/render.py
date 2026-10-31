"""Generate the static side-by-side reading page."""

from datetime import datetime
import html

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .translation import audit_translations
from .source_quality import assert_publishable_source


PDF_URL = "https://doi.org/10.6028/NIST.SP.800-63b-4"
# Pictures the site does not reproduce: (English label, Japanese label, reason).
OFFICIAL_MARKS = {
    "nist_logo": ("NIST logo", "NIST のロゴ", "公的な標章のため"),
    "doc_seal": ("U.S. Department of Commerce seal", "米国商務省の紋章", "公的な標章のため"),
    "contains_nist_logo": ("Figure that shows the NIST logo", "NIST のロゴが写っている図",
                           "公的な標章のため"),
    "person_photo": ("Photograph of people", "人物の写真", "人物が写っているため"),
    "other_logo": ("Logo of an organization or program", "組織・プログラムのロゴ", "ロゴのため"),
    "decorative": ("Decorative picture", "装飾の画像", "本文を読むのに必要のない装飾のため"),
}


def asset_version():
    """Short hash of the site's CSS, added to its URL so browsers fetch a changed file."""
    import hashlib
    from pathlib import Path
    static = Path(__file__).resolve().parents[2] / "static"
    digest = hashlib.sha256()
    for name in ("style.css", "header.css"):
        digest.update((static / name).read_bytes())
    return digest.hexdigest()[:10]


def build_site(document, meta, template_path, output_path):
    assert_publishable_source(document)
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
            # Group formulas/prefixes can differ from individual member text.
            # audit_translations validates the explicit group review hash.
            item["status"] = "reviewed" if math_group.get("status") == "reviewed" else "draft"
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
        excerpt = block.get("third_party_excerpt")
        if excerpt:
            # Text another party owns, reprinted by NIST with permission: the data keeps
            # no text, and the page shows a note that points to the original page.
            item = dict(block)
            item["english_html"] = Markup(
                '<span class="withheld-mark">[Excerpt from %s, © %s — not reproduced on this unofficial site]</span>'
                % (html.escape(excerpt["source"]), html.escape(excerpt["holder"])))
            item["html_ja"] = "［%s からの引用。第三者（%s）の著作物のため、この非公式サイトには掲載していない。原本 PDF を参照。］" % (
                excerpt["source"], excerpt["holder"])
            item["japanese_html"] = Markup(html.escape(item["html_ja"]))
            item["status"] = "source_only"
            if document.get("source_format") == "pdf" and block.get("source_page"):
                item["source_page_url"] = document["source_url"] + "#page=%d" % block["source_page"]
            visible.append(item)
            continue
        # Empty extraction records have no source content to pair. Showing
        # "translation pending" for them creates misleading blank rows.
        if not block["html"].strip():
            continue
        item = dict(block)
        item["english_html"] = Markup(block["html"])
        if block["kind"] == "list_item":
            ordinal = str(block.get("ordinal") or "").strip()
            if not block.get("ordered") or not ordinal:
                item["list_marker"] = "•"
            else:
                # "2." or "(a)" already carry their punctuation; "2" and "ii" get a period
                item["list_marker"] = ordinal if ordinal[-1] in ".)]" else ordinal + "."
        item["japanese_html"] = Markup(block["html_ja"])
        # An unverified table is shown as the image of the original; its
        # extracted text is offered below as an unchecked reference.
        if (block["kind"] == "table" and block.get("source_image") and
                block.get("extraction_status") == "needs_review" and not block.get("official_mark")):
            item["image_authoritative"] = True
        if block.get("official_mark"):
            # An unofficial translation must not display protected official marks.
            name_en, name_ja, reason = OFFICIAL_MARKS[block["official_mark"]]
            sources = [image.get("src", "") for image in
                       BeautifulSoup(block["html"], "html.parser").find_all("img")]
            for source in sources + [block.get("source_image") or ""]:
                published = output_path.parent / source
                if source and published.is_file():
                    published.unlink()  # a re-extraction may have written it again
            item["source_image"] = None  # a crop of the original that shows the mark
            if block["kind"] != "figure":
                # A photo or seal extracted as a table or text: show the same note as a
                # withheld figure, never the extracted text around it.
                item["kind"] = "figure"
                item["status"] = "source_only"
            if item["kind"] == "figure":
                item["english_html"] = Markup(
                    '<span class="withheld-mark">[%s — not reproduced on this unofficial site]</span>'
                    % name_en)
                described = BeautifulSoup(block["html_ja"] or "", "html.parser").find("img")
                item["figure_description"] = (
                    (described.get("alt", "") + " " if described and
                     block["official_mark"] not in {"nist_logo", "doc_seal"} else "") +
                    "［%s。%s、この非公式サイトには掲載していない。原本 PDF を参照。］" % (name_ja, reason))
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
        orig_url=document.get("orig_url") or document.get("pdf_url", PDF_URL),
        release_date=document.get("release_date", ""),
        summary=document.get("summary") or [],
        source_format=document.get("source_format", "html"),
        series=document.get("series", "Digital Identity Guidelines · Revision 4"),
        included_pages=document.get("included_pages", []),
        extraction_partial=document.get("extraction_partial", False),
        extraction_pending=sum(block.get("extraction_status") == "needs_review" and
                               not block.get("image_authoritative") and not block.get("official_mark")
                               for block in visible),
        extraction_warnings=document.get("extraction_warnings", []),
        has_math=bool(math_groups) or any(
            block.get("kind") == "math" or "data-tex=" in block.get("html", "") or
            "\\(" in block.get("html", "") or "\\[" in block.get("html", "")
            for block in document["contents"]),
        home_url=document.get("home_url", "index.html"),
        math_preservation=document.get("math_preservation"),
        math_pending=sum(block.get("kind") == "math" and
                         not any(block.get(key) for key in ("math_duplicate_of", "duplicate_artifact_of",
                                                            "page_furniture", "figure_text_of")) and
                         (block.get("extraction_status") == "needs_review" or
                          block.get("status") != "reviewed")
                         for block in document["contents"]),
        fetched_at=fetched_at or "", headings=headings, asset_version=asset_version(),
        blocks=visible, translated=translated, total=len(visible), stale=stale,
    )
    output_path.write_text(page, encoding="utf-8")
