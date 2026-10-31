"""Turn the printed table of contents into a navigable one (display only; the data is unchanged).

The original's "Table of Contents", "List of Tables" and "List of Figures" were extracted
as one paragraph per line, e.g. "1.1 Purpose — 1" or "Executive Summary ...... iv". On the
page each line becomes a link to the heading (or table/figure) it names, indented by its
section depth, without the page number.
"""

import re
import warnings

from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

TOC_HEADING = re.compile(r"^\s*(table of contents|contents|list of (tables|figures|algorithms|examples))\s*$", re.I)
# a page number at the end of a line: "— 12", "......... iv", " A-3", " 12"
PAGE = re.compile(r"\s*(?:\.{2,}|…+|[—–]|\s)\s*(?:[ivxlcdm]{1,7}|\d{1,4}|[A-Z]-\d{1,3})\s*$", re.I)
NUMBER = re.compile(r"^\s*(?:(?:Appendix|Annex|Chapter|Section)\s+)?([A-Z]|\d{1,2})((?:\.\d{1,3})*)\.?(?=\s|$|[:.]|(?<=\d)[A-Z][a-z])", re.I)
WORD_NUMBERS = ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN")
LABEL = re.compile(r"^\s*(Table|Figure|Algorithm|Example)\s+([A-Z]?-?\d+(?:[.-]\d+)*)", re.I)


def plain(markup):
    return re.sub(r"\s+", " ", " ".join(BeautifulSoup(markup or "", "html.parser").stripped_strings)).strip()


LEADER = re.compile(r"(?:\s*(?:\.\s*){2,}|\s*…+)\s*$")


def strip_page(text):
    """The entry text without its page number and dot leaders ("....", ". . . .", "…")."""
    stripped = LEADER.sub("", text)
    if stripped == text:
        stripped = LEADER.sub("", PAGE.sub("", text))
    return stripped.strip()


def entry_key(text):
    """("number", "1.2") or ("label", "table 3") or ("title", normalized words)."""
    chapter = re.match(r"^\s*CHAPTER\s+(%s)\b" % "|".join(WORD_NUMBERS), text, re.I)
    if chapter:
        return ("number", str(WORD_NUMBERS.index(chapter.group(1).upper()) + 1))
    label = LABEL.match(text)
    if label:
        return ("label", "%s %s" % (label.group(1).lower(), label.group(2).lower()))
    number = NUMBER.match(text)
    if number and (number.group(2) or number.group(1).isdigit()
                   or text.lstrip().lower().startswith(("appendix", "annex", "section"))):
        return ("number", (number.group(1) + number.group(2)).upper())
    return ("title", re.sub(r"[^a-z0-9]+", " ", text.lower()).strip())


def depth_of(key):
    if key[0] == "number":
        return 1 + key[1].count(".")
    return 1


def words(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def title_words(text):
    """Content words of an entry or target, without its number or label."""
    text = LABEL.sub("", NUMBER.sub("", re.sub(r"^\s*CHAPTER\s+\w+", "", text, flags=re.I)))
    # "identifcation": some PDFs lost the "fi" ligature, so compare words without it
    return {word.replace("fi", "") for word in re.findall(r"[a-z]{3,}", text.lower())}


def find_targets(blocks, start):
    """Candidate blocks for each key, in page order: headings first, then short other blocks.

    Some section titles were extracted as paragraphs, so those are kept as later candidates.
    """
    headings, others = {}, {}
    for block in blocks[start:]:
        text = plain(block.get("html"))
        if not text:
            continue
        keys = [entry_key(text), ("title", words(text)), ("title", words(NUMBER.sub("", text)))]
        label = LABEL.match(text)
        if label:
            keys.append(("label", "%s %s" % (label.group(1).lower(), label.group(2).lower())))
        bucket = headings if block["kind"] == "heading" else others
        if block["kind"] != "heading" and len(text) > 150 and not label:
            continue
        for key in keys:
            bucket.setdefault(key, []).append((block["id"], text, block["kind"]))
    for key, candidates in others.items():
        headings.setdefault(key, []).extend(candidates)
    return headings


CAPTION = re.compile(r"^\s*(Table|Figure|Algorithm|Example)\s+[A-Z]?-?\d+(?:[.-]\d+)*\s*(?:[.:–—-]|$)", re.I)


def choose(candidates, entry):
    """The first candidate that is the same section: its words overlap the entry's title,
    or it is only the bare number or label ("APPENDIX D", "Chapter 9") with the title in the next block.
    For a table or figure, a caption ("Table 3.", "Table 3:", or the table/figure block itself)
    comes before prose that mentions it ("Table 3 provides ...")."""
    wanted = title_words(entry)
    if LABEL.match(entry):
        captions = [c for c in candidates if c[2] in ("table", "figure") or CAPTION.match(c[1])]
        candidates = captions + [c for c in candidates if c not in captions]
    for block_id, text, kind in candidates:
        # a block that is not a heading must look like a title, not prose that mentions it
        if kind != "heading" and kind not in ("table", "figure") and len(text) > len(entry) + 30:
            continue
        found = title_words(text)
        if not wanted or not found:
            return block_id
        overlap = len(wanted & found)
        if overlap * 3 >= len(wanted) * 2 and (len(wanted) > 2 or overlap == len(wanted)):
            return block_id
    return None


def printed_toc(blocks):
    """{block id: {"depth", "target", "en", "ja"}} for the lines of the printed TOC.

    `blocks` are the visible blocks in page order (with "html" and "html_ja").
    """
    result = {}
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if not (block["kind"] == "heading" and TOC_HEADING.match(plain(block["html"]))):
            index += 1
            continue
        lines, cursor = [], index + 1
        while cursor < len(blocks):
            candidate = blocks[cursor]
            text = plain(candidate.get("html"))
            if candidate["kind"] == "heading" and TOC_HEADING.match(text):
                break
            if candidate["kind"] not in ("paragraph", "list_item", "heading") or not (PAGE.search(text) or LEADER.search(text)):
                break
            lines.append(candidate)
            cursor += 1
        toc_ids = {line["id"] for line in lines} | {block["id"]}
        rest = [b for b in blocks[cursor:] + blocks[:index] if b["id"] not in toc_ids]
        targets = find_targets(rest, 0)
        for line in lines:
            text = strip_page(plain(line["html"]))
            key = entry_key(text)
            target = choose(targets.get(key, []), text)
            if target is None:
                target = choose(targets.get(("title", words(NUMBER.sub("", LABEL.sub("", text)))), []), text)
            result[line["id"]] = {"depth": min(depth_of(key), 4), "target": target, "en": text,
                                  "ja": strip_page(plain(line.get("html_ja"))) or text}
        index = cursor
    return result
