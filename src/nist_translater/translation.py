"""Translation operations and HTML-integrity checks for the document JSON."""

import html
import re
from collections import Counter

from bs4 import BeautifulSoup, NavigableString, Tag

from .pdf_equations import inline_katex_html


TRANSLATABLE = {"heading", "paragraph", "list_item", "note", "definition_term", "definition", "table", "figure", "footnote", "math"}
NORMATIVE = re.compile(r"\b(?:SHALL NOT|SHOULD NOT|NEED NOT|SHALL|SHOULD|MAY(?!\s+\d{4}\b)|CANNOT|CAN)\b")


def requirement_terms(text):
    """Uppercase requirement keywords; a heading set entirely in capitals has none."""
    if not re.search(r"[a-z]", text):
        return Counter()
    return Counter(NORMATIVE.findall(text))


STATUSES = {"untranslated", "draft", "reviewed", "stale", "source_only"}


def contents(document):
    value = document.get("contents")
    if not isinstance(value, list):
        raise ValueError("Document must contain a contents array")
    return value


def source_text(block):
    value = block["html"]
    if "<" not in value:
        return " ".join(html.unescape(value).split())
    return " ".join(BeautifulSoup(value, "html.parser").stripped_strings)


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
    inventory = Counter()
    for tag in soup.find_all(True):
        attrs = []
        for name, value in tag.attrs.items():
            # Alternative text is user-facing text and should be localized for images.
            # Keep the attribute itself while allowing its value to differ by language.
            if tag.name == "img" and name == "alt":
                value = "<localized-alt>"
            attrs.append((name, tuple(value) if isinstance(value, list) else value))
        inventory[(tag.name, tuple(sorted(attrs)))] += 1
    return inventory


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


def assert_same_html_structure(source_html, translated_html, *, preserve_math=False):
    """Preserve tags and functional attributes while allowing translated image alt text."""
    # English ordinal suffixes (10<sup>th</sup>) have no Japanese counterpart,
    # so a translation may drop any number of those superscripts.
    without_ordinals = re.sub(r"<sup>(?:st|nd|rd|th)</sup>", "", source_html)
    full, least, found = (_tag_inventory(source_html), _tag_inventory(without_ordinals),
                          _tag_inventory(translated_html))
    plain_sup = ("sup", ())
    same = ({**found, plain_sup: 0} == {**full, plain_sup: 0} and
            least[plain_sup] <= found[plain_sup] <= full[plain_sup])
    if not same or not _has_balanced_tags(translated_html):
        raise ValueError("Translated HTML tags or attributes differ from the source")
    pattern = r"\\\(.*?\\\)|\\\[.*?\\\]"
    formula_text = re.compile(r"\\text\{[^{}]*\}")

    def formula_signature(formula):
        # TeX text labels and spacing may be localized without changing the equation.
        signature = re.sub(r"P\\text\{-value\}s?", "P", formula)
        signature = formula_text.sub("", signature)
        signature = re.sub(r"\\(?:left|right)\b", "", signature)
        return re.sub(r"\s+", "", signature)

    source_formulas = Counter(
        formula_signature(formula)
        for formula in re.findall(pattern, html.unescape(source_html), re.S)
    )
    translated_formulas = Counter(
        formula_signature(formula)
        for formula in re.findall(pattern, html.unescape(translated_html), re.S)
    )
    if preserve_math and source_formulas != translated_formulas:
        raise ValueError("Translated LaTeX formulas differ from the source")


def audit_translations(document):
    from .source_quality import encoding_issues
    blocks = {b["id"]: b for b in contents(document)}
    for issue in encoding_issues(document):
        block = blocks[issue["id"]]
        if block.get("extraction_status") == "verified" or block.get("status") == "reviewed":
            raise ValueError("Replacement character cannot be verified/reviewed: " + block["id"])
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
        if block.get("kind") == "math":
            inline_katex_html(block["html"])
            inline_katex_html(block["html_ja"])
        status = block.get("status")
        if status not in STATUSES:
            raise ValueError("Invalid translation status: " + key)
        if document.get("source_format") == "pdf":
            if block.get("extraction_status") not in {"needs_review", "verified"}:
                raise ValueError("Invalid PDF extraction status: " + key)
            if not isinstance(block.get("source_page"), int) or block["source_page"] < 1:
                raise ValueError("Missing PDF page reference: " + key)
            if not isinstance(block.get("source_refs"), list) or not block["source_refs"]:
                raise ValueError("Missing PDF source region: " + key)
        if status in {"draft", "reviewed"} and not block["html_ja"].strip():
            raise ValueError("Translated block is empty: " + key)
        if status in {"draft", "reviewed"}:
            assert_same_html_structure(block["html"], block["html_ja"])
            if Counter(NORMATIVE.findall(block["html_ja"])) != requirement_terms(source_text(block)):
                raise ValueError("Requirement terms differ in stored translation: " + key)
        if document.get("source_format") == "pdf" and status == "reviewed" and block.get("extraction_status") != "verified":
            raise ValueError("PDF source must be verified before translation review: " + key)
        if status == "stale":
            changed += 1
    blocks_by_id = {block["id"]: block for block in contents(document)}
    block_ids = set(blocks_by_id)
    for block in contents(document):
        parent_id = block.get("duplicate_artifact_of")
        if not parent_id:
            continue
        parent = blocks_by_id.get(parent_id)
        if (not parent or parent.get("kind") != "table" or
                parent.get("source_page") != block.get("source_page")):
            raise ValueError("Invalid duplicate artifact parent: " + block["id"])
        if block.get("status") != "source_only" or block.get("html_ja"):
            raise ValueError("Duplicate table artifact must remain hidden source-only: " + block["id"])
    grouped_members = set()
    for group in document.get("math_groups", []):
        key = group.get("id")
        members = group.get("members")
        if (not isinstance(key, str) or not isinstance(members, list) or not members
                or not all(isinstance(member, str) and member in block_ids for member in members)):
            raise ValueError("Invalid KaTeX group: " + str(key))
        if len(set(members)) != len(members) or grouped_members.intersection(members):
            raise ValueError("Duplicate block in KaTeX groups: " + key)
        if not isinstance(group.get("tex"), str) or not group["tex"].strip():
            raise ValueError("Missing KaTeX source: " + key)
        if not isinstance(group.get("tex_ja", group["tex"]), str):
            raise ValueError("Invalid Japanese KaTeX source: " + key)
        source_hashes = group.get("source_hashes")
        if (not isinstance(source_hashes, dict) or set(source_hashes) != set(members)
                or any(source_hashes[member] != blocks_by_id[member]["source_hash"]
                       for member in members)):
            raise ValueError("Stale or missing source hashes in KaTeX group: " + key)
        grouped_members.update(members)
    return changed


def make_queue(document):
    return [
        {"id": block["id"], "source_hash": block["source_hash"], "html": block["html"], "html_ja": ""}
        for block in contents(document)
        if (block["kind"] in TRANSLATABLE and block["status"] in {"untranslated", "stale"}
            and not block.get("duplicate_artifact_of")
            and not block.get("page_furniture")
            and not block.get("math_duplicate_of")
            and "\ufffd" not in html.unescape(block["html"])
            and (block["kind"] != "figure" or source_text(block)))
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
        if "\ufffd" in html.unescape(block["html"]) or (isinstance(japanese, str) and "\ufffd" in html.unescape(japanese)):
            raise ValueError("Repair replacement characters before translating: " + key)
        if not japanese:
            continue
        if block.get("kind") == "math":
            inline_katex_html(japanese)
        if not isinstance(japanese, str):
            raise ValueError("Translation must be text: " + str(key))
        if block["status"] == "reviewed":
            continue
        assert_same_html_structure(block["html"], japanese, preserve_math=True)
        if Counter(NORMATIVE.findall(japanese)) != requirement_terms(source_text(block)):
            raise ValueError("Requirement terms differ for " + key)
        block["html_ja"] = japanese
        block["status"] = "draft"
        count += 1
    return count


def carry_translations(previous, current):
    """Preserve compatible translations; mark changed source HTML as stale."""
    from .pdf_source_repairs import preserve_source_repairs
    current = preserve_source_repairs(previous, current)
    previous_blocks = contents(previous)
    old = {block["id"]: block for block in previous_blocks}
    by_hash = {}
    if current.get("source_format") == "pdf":
        for prior in previous_blocks:
            by_hash.setdefault((prior.get("kind"), prior.get("source_hash")), []).append(prior)
    used = set()
    for block in contents(current):
        if block.get("duplicate_artifact_of"):
            block["html_ja"] = ""
            block["status"] = "source_only"
            continue
        prior = old.get(block["id"])
        exact = (prior and prior.get("html") == block["html"] and
                 prior.get("kind") == block["kind"] and
                 (current.get("source_format") != "pdf" or
                  prior.get("source_hash") == block["source_hash"]))
        if by_hash and not exact:
            matches = [candidate for candidate in by_hash.get(
                (block["kind"], block["source_hash"]), []) if candidate["id"] not in used]
            same_page = [candidate for candidate in matches
                         if candidate.get("source_page") == block.get("source_page")]
            if same_page:
                matches = same_page
            if len(matches) > 1:
                current_ref = next(iter(block.get("source_refs", [])), {})
                current_box = current_ref.get("bbox", [])
                def region_distance(candidate):
                    old_ref = next(iter(candidate.get("source_refs", [])), {})
                    old_box = old_ref.get("bbox", [])
                    return (sum(abs(left - right) for left, right in zip(current_box, old_box))
                            if len(current_box) == len(old_box) == 4 else float("inf"))
                distances = [(region_distance(candidate), candidate) for candidate in matches]
                nearest = min(distance for distance, _ in distances)
                matches = [candidate for distance, candidate in distances
                           if distance == nearest] if nearest < float("inf") else matches
            if len(matches) == 1:
                prior = matches[0]
                exact = prior.get("html") == block["html"]
        if prior:
            used.add(prior["id"])
        if exact and prior.get("extraction_status") == "verified":
            block["extraction_status"] = "verified"
        prior_html_ja = (prior or {}).get("html_ja", (prior or {}).get("ja", ""))
        if (not prior or prior.get("kind") != block.get("kind") or
                (block.get("kind") == "figure" and not exact) or not prior_html_ja):
            continue
        block["html_ja"] = prior_html_ja
        if exact:
            try:
                assert_same_html_structure(block["html"], block["html_ja"])
                block["status"] = prior.get("status", "draft")
            except ValueError:
                block["status"] = "stale"
        else:
            block["status"] = "stale"
    # Keep hand-authored PDF formula groups across reparses only while every
    # source block they cover is unchanged. A changed extraction drops the
    # affected group so stale TeX cannot hide newly extracted source text.
    if previous.get("math_groups"):
        current_blocks = {block["id"]: block for block in contents(current)}
        preserved = []
        for group in previous["math_groups"]:
            hashes = group.get("source_hashes", {})
            if all(member in current_blocks and
                   current_blocks[member].get("source_hash") == hashes.get(member)
                   for member in group.get("members", [])):
                preserved.append(group)
        if preserved:
            current["math_groups"] = preserved
    return current
