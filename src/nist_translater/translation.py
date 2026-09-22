"""Translation operations and HTML-integrity checks for the document JSON."""

import re
from collections import Counter

from bs4 import BeautifulSoup, NavigableString, Tag


TRANSLATABLE = {"heading", "paragraph", "list_item", "note", "definition_term", "definition", "table"}
NORMATIVE = re.compile(r"\b(?:SHALL NOT|SHOULD NOT|NEED NOT|SHALL|SHOULD|MAY|CANNOT|CAN)\b")
STATUSES = {"untranslated", "draft", "reviewed", "stale", "source_only"}


def contents(document):
    value = document.get("contents")
    if not isinstance(value, list):
        raise ValueError("Document must contain a contents array")
    return value


def source_text(block):
    return " ".join(BeautifulSoup(block["html"], "html.parser").stripped_strings)


def _tag_shape(node):
    if isinstance(node, NavigableString):
        return None
    if not isinstance(node, Tag):
        return None
    attrs = tuple(sorted((name, tuple(value) if isinstance(value, list) else value)
                         for name, value in node.attrs.items()))
    children = tuple(shape for child in node.children if (shape := _tag_shape(child)) is not None)
    return node.name, attrs, children


def _tag_inventory(html):
    soup = BeautifulSoup("<fragment>%s</fragment>" % html, "html.parser")
    return Counter((tag.name, tuple(sorted(
        (name, tuple(value) if isinstance(value, list) else value)
        for name, value in tag.attrs.items()))) for tag in soup.find_all(True))


def _has_balanced_tags(html):
    void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    stack = []
    for match in re.finditer(r"<\s*(/?)\s*([A-Za-z][\w:-]*)\b[^>]*>", html):
        closing, name = match.groups()
        name = name.lower()
        if name in void or match.group(0).rstrip().endswith("/>"):
            continue
        if closing:
            if not stack or stack.pop() != name:
                return False
        else:
            stack.append(name)
    return not stack


def assert_same_html_structure(source_html, translated_html):
    """Allow text and span reordering while preserving every tag and attribute."""
    if (_tag_inventory(source_html) != _tag_inventory(translated_html)
            or not _has_balanced_tags(translated_html)):
        raise ValueError("Translated HTML tags or attributes differ from the source")


def audit_translations(document):
    ids = set()
    changed = 0
    for block in contents(document):
        key = block.get("id")
        if not isinstance(key, str) or key in ids:
            raise ValueError("Invalid or duplicate content ID: " + str(key))
        ids.add(key)
        if not isinstance(block.get("source_hash"), str):
            raise ValueError("Missing source hash: " + key)
        if not isinstance(block.get("html"), str):
            raise ValueError("Source HTML must be text: " + key)
        if not isinstance(block.get("html_ja"), str):
            raise ValueError("Translation must be text: " + key)
        status = block.get("status")
        if status not in STATUSES:
            raise ValueError("Invalid translation status: " + key)
        if status in {"draft", "reviewed"} and not block["html_ja"].strip():
            raise ValueError("Translated block is empty: " + key)
        if status in {"draft", "reviewed"}:
            assert_same_html_structure(block["html"], block["html_ja"])
            if Counter(NORMATIVE.findall(block["html_ja"])) != Counter(NORMATIVE.findall(source_text(block))):
                raise ValueError("Requirement terms differ in stored translation: " + key)
        if status == "stale":
            changed += 1
    return changed


def make_queue(document):
    return [
        {"id": block["id"], "source_hash": block["source_hash"], "html": block["html"], "html_ja": ""}
        for block in contents(document)
        if block["kind"] in TRANSLATABLE and block["status"] in {"untranslated", "stale"}
    ]


def merge_translations(document, incoming):
    if not isinstance(incoming, list):
        raise ValueError("Import file must contain a JSON array")
    blocks = {block["id"]: block for block in contents(document)}
    count = 0
    for item in incoming:
        key = item.get("id")
        if key not in blocks:
            raise ValueError("Unknown block ID: " + str(key))
        block = blocks[key]
        if item.get("source_hash") != block["source_hash"]:
            raise ValueError("Source changed for block: " + str(key))
        japanese = item.get("html_ja", "")
        if not japanese:
            continue
        if not isinstance(japanese, str):
            raise ValueError("Translation must be text: " + str(key))
        if block["status"] == "reviewed":
            continue
        assert_same_html_structure(block["html"], japanese)
        if Counter(NORMATIVE.findall(japanese)) != Counter(NORMATIVE.findall(source_text(block))):
            raise ValueError("Requirement terms differ for " + key)
        block["html_ja"] = japanese
        block["status"] = "draft"
        count += 1
    return count


def carry_translations(previous, current):
    """Preserve compatible translations; mark changed source HTML as stale."""
    old = {block["id"]: block for block in contents(previous)}
    for block in contents(current):
        prior = old.get(block["id"])
        prior_html_ja = (prior or {}).get("html_ja", (prior or {}).get("ja", ""))
        if not prior or not prior_html_ja:
            continue
        block["html_ja"] = prior_html_ja
        if prior.get("html") == block["html"] and prior.get("kind") == block["kind"]:
            try:
                assert_same_html_structure(block["html"], block["html_ja"])
                block["status"] = prior.get("status", "draft")
            except ValueError:
                block["status"] = "stale"
        else:
            block["status"] = "stale"
    return current
