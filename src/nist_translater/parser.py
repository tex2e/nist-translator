"""Extract ordered reading blocks from the NIST single-page HTML."""

import hashlib
import html
import re
from collections import defaultdict
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag


SOURCE_URL = "https://pages.nist.gov/800-63-4/sp800-63b.html"
HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
INLINE_TAGS = {"strong", "em", "code", "sup", "sub", "small", "kbd"}


def clean_text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def safe_url(value, source_url=SOURCE_URL):
    resolved = urljoin(source_url, value or "")
    return resolved if resolved.startswith(("https://pages.nist.gov/", "https://doi.org/", "https://")) else ""


def inline_html(node, source_url=SOURCE_URL):
    if isinstance(node, NavigableString):
        return html.escape(str(node))
    if not isinstance(node, Tag):
        return ""
    if "header-link" in node.get("class", []):
        return ""
    if node.name == "br":
        return "<br>"
    if node.name == "img":
        source = safe_url(node.get("src"), source_url)
        if not source:
            return ""
        return '<img src="%s" alt="%s" loading="lazy">' % (
            html.escape(source, quote=True), html.escape(node.get("alt", ""), quote=True))
    content = "".join(inline_html(child, source_url) for child in node.children)
    if node.name == "a":
        target = safe_url(node.get("href"), source_url) if node.get("href") else ""
        return '<a href="%s">%s</a>' % (html.escape(target, quote=True), content) if target else content
    if node.name in INLINE_TAGS:
        return "<%s>%s</%s>" % (node.name, content, node.name)
    return content


def inner_html(node, source_url=SOURCE_URL):
    return "".join(inline_html(child, source_url) for child in node.children)


def table_html(table, source_url=SOURCE_URL):
    parts = ["<table>"]
    if table.get("latex-caption"):
        parts.append("<caption>%s</caption>" % html.escape(table["latex-caption"]))
    for row in table.select("tr"):
        parts.append("<tr>")
        for cell in row.find_all(["th", "td"], recursive=False):
            tag = cell.name
            parts.append("<%s>%s</%s>" % (tag, inner_html(cell, source_url), tag))
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def parse_document(source, number="SP 800-63B-4", source_url=SOURCE_URL,
                   min_blocks=500, min_headings=50):
    soup = BeautifulSoup(source, "html.parser")
    root = soup.select_one("body > div.container > div.row")
    if root is None:
        raise ValueError("NIST body structure changed: content row not found")

    blocks = []
    headings = []
    section = "front"
    section_counts = defaultdict(int)
    heading_counts = defaultdict(int)
    ids = set()

    def add(kind, node, content=None, text_override=None, **extra):
        nonlocal section
        text = clean_text(node) if text_override is None else text_override
        if not text and kind != "figure":
            return
        if kind == "heading":
            base = node.get("id") or re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            heading_counts[base] += 1
            section = base if heading_counts[base] == 1 else "%s-%d" % (base, heading_counts[base])
            block_id = section
        else:
            section_counts[section] += 1
            block_id = "%s--%04d" % (section, section_counts[section])
        if block_id in ids:
            raise ValueError("Duplicate block ID: " + block_id)
        ids.add(block_id)
        content = inner_html(node, source_url) if content is None else content
        block = {
            "id": block_id, "kind": kind, "html": content,
            "source_hash": hashlib.sha256(
                (kind + "\n" + content).encode("utf-8")
            ).hexdigest()[:16],
            **extra,
        }
        blocks.append(block)
        if kind == "heading":
            headings.append({"id": block_id, "text": text, "level": extra["level"]})

    def add_list(list_node, depth=0):
        for ordinal, item in enumerate(list_node.find_all("li", recursive=False), start=1):
            # Nested lists become separate aligned blocks in document order.
            content = "".join(inline_html(child, source_url) for child in item.children
                              if not isinstance(child, Tag) or child.name not in ("ul", "ol"))
            text = " ".join(" ".join(child.stripped_strings) if isinstance(child, Tag)
                            else str(child).strip() for child in item.children
                            if not isinstance(child, Tag) or child.name not in ("ul", "ol"))
            add("list_item", item, content=content.strip(), text_override=" ".join(text.split()), depth=depth,
                ordered=list_node.name == "ol", ordinal=ordinal)
            for nested in item.find_all(["ul", "ol"], recursive=False):
                add_list(nested, depth + 1)

    for node in root.find_all(recursive=False):
        if node.name in HEADING_TAGS:
            # The link icon is not part of the heading text.
            for icon in node.select("a.header-link"):
                icon.decompose()
            add("heading", node, level=HEADING_TAGS[node.name], source_anchor=node.get("id"))
        elif node.name == "p":
            if re.match(r"^[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2} \d{4} ", clean_text(node)):
                continue  # HTML build timestamp, outside the publication body.
            kind = "figure" if node.find("img") else "paragraph"
            add(kind, node)
        elif node.name in ("ul", "ol"):
            add_list(node)
        elif node.name == "blockquote":
            for paragraph in node.find_all("p", recursive=False):
                add("note", paragraph)
        elif node.name == "table":
            add("table", node, content=table_html(node, source_url))
        elif node.name == "dl":
            for child in node.find_all(["dt", "dd"], recursive=False):
                add("definition_term" if child.name == "dt" else "definition", child)
        elif node.name == "div" and "footnotes" in node.get("class", []):
            for item in node.select("li[role='doc-endnote']"):
                add("footnote", item)
        elif node.name == "div" and "highlighter-rouge" in node.get("class", []):
            # These blocks contain LaTeX pagination commands, not reader content.
            continue
        else:
            raise ValueError("Unexpected top-level NIST element: " + str(node.name))

    if len(blocks) < min_blocks or len(headings) < min_headings:
        raise ValueError("Unexpectedly little %s content was parsed (%d blocks, %d headings)" % (
            number, len(blocks), len(headings)))
    for block in blocks:
        block["html_ja"] = ""
        block["status"] = "untranslated" if block["kind"] in {
            "heading", "paragraph", "list_item", "note", "definition_term", "definition", "table"
        } else "source_only"
    return {
        "title": {"text": "NIST " + number, "html_ja": ""},
        "number": number,
        "created_at": "",
        "updated_by": "",
        "source_url": source_url,
        "source_fetched_at": "",
        "contents": blocks,
    }
