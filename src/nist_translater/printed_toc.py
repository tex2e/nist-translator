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

TOC_HEADING = re.compile(r"^\s*(table of contents|contents|list of (tables|figures|algorithms|examples|appendices)(\s+and\s+(tables|figures|algorithms|examples))?)(\s*\(continued\))?\s*$", re.I)
# a page number at the end of a line: "— 12", "......... iv", " A-3", chapter-page "....2-3" (also cut off as "1-")
# or, after a dash, a page named by its part ("— Intro-iii", "— Appendix-87", "— Front")
PAGE = re.compile(r"\s*(?:(?:\s*[.…]){2,}|\.|…+|[—–]|\s)\s*(?:[A-Z]{1,3}[-–]\d{1,3}|[A-Z]\.\d{1,2}-\d{1,3}|\d{1,4}(?:-\d{0,3})?|[ivxlcdm]{1,7}\b)\s*$"
                  r"|\s*[—–]\s*(?:(?:Intro|Appendix|Annex)\s?[-–]\s?(?:\d{1,3}|[ivxlcdm]{1,7})|Front)\s*$", re.I)
NUMBER = re.compile(r"^\s*(?:(?:Appendix|Annex|Chapter|Section)\s+)?([IVX]{2,4}(?=\.)|[A-Z]|\d{1,2})((?:\.\s?\d{1,3})*)\.?(?=\s|$|[:.]|(?<=\d)[A-Z][a-z])", re.I)
WORD_NUMBERS = ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN")
LABEL_ID = r"(?:[A-Z]{1,4}(?:\([A-Z]\))?-|[A-Z]?-?)\d+(?:[.-]\d+)*"
LABEL = re.compile(r"^\s*(Table|Figure|Fig\.|Algorithm|Example)\s*(%s)" % LABEL_ID, re.I)


def label_name(name):
    name = name.lower().rstrip(".")
    return "figure" if name == "fig" else name


def plain(markup):
    return re.sub(r"\s+", " ", " ".join(BeautifulSoup(markup or "", "html.parser").stripped_strings)).strip()


LEADER = re.compile(r"(?:\s*(?:[.…]\s*){2,}|\s*…+)\s*$")


def strip_page(text):
    """The entry text without its page number and dot leaders ("....", ". . . .", "…")."""
    stripped = LEADER.sub("", text)
    if stripped == text:
        stripped = LEADER.sub("", PAGE.sub("", text))
    return stripped.strip()


def entry_key(text):
    """("number", "1.2") or ("label", "table 3") or ("title", normalized words)."""
    step = re.match(r"^\s*STEP\s+(\d{1,2})\b", text, re.I)
    if step:
        # "STEP 1 DEFINE YOUR SYSTEM" and the heading "STEP 1" (IR 4325); kept apart from section 1
        return ("step", step.group(1))
    chapter = re.match(r"^\s*CHAPTER\s+(%s)\b" % "|".join(WORD_NUMBERS), text, re.I)
    if chapter:
        return ("number", str(WORD_NUMBERS.index(chapter.group(1).upper()) + 1))
    label = LABEL.match(text)
    if label:
        return ("label", "%s %s" % (label_name(label.group(1)), label.group(2).lower()))
    number = NUMBER.match(text)
    if number and (number.group(2) or number.group(1).isdigit()
                   or text.lstrip().lower().startswith(("appendix", "annex", "section"))):
        return ("number", (number.group(1) + number.group(2).replace(" ", "")).upper())
    return ("title", re.sub(r"[^a-z0-9]+", " ", text.lower()).strip())


def depth_of(key):
    if key[0] == "number":
        # "2.0" is how some documents number chapter 2
        return 1 + re.sub(r"(\.0)+$", "", key[1]).count(".")
    return 1


def words(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def title_words(text):
    """Content words of an entry or target, without its number or label."""
    text = LABEL.sub("", NUMBER.sub("", re.sub(r"^\s*(?:CHAPTER|STEP)\s+\w+", "", text, flags=re.I)))
    # "identifcation": some PDFs lost the "fi" ligature, so compare words without it
    return {word.replace("fi", "") for word in re.findall(r"[a-z]{3,}", text.lower())}


def find_targets(blocks, start):
    """Candidate blocks for each key, in page order: headings first, then short other blocks.

    Some section titles were extracted as paragraphs, so those are kept as later candidates.
    """
    headings, others = {}, {}
    for block in blocks[start:]:
        text = plain(block.get("html"))
        if not text and block["kind"] == "figure":
            image = BeautifulSoup(block.get("html") or "", "html.parser").find("img")
            text = (image.get("alt") or "").strip() if image else ""
        if not text:
            continue
        keys = [entry_key(text), ("title", words(text)), ("title", words(NUMBER.sub("", text)))]
        label = LABEL.match(text)
        if label:
            keys.append(("label", "%s %s" % (label_name(label.group(1)), label.group(2).lower())))
        bucket = headings if block["kind"] == "heading" else others
        if block["kind"] != "heading" and len(text) > 150 and not label:
            continue
        for key in keys:
            bucket.setdefault(key, []).append((block["id"], text, block["kind"]))
    for key, candidates in others.items():
        headings.setdefault(key, []).extend(candidates)
    return headings


CAPTION = re.compile(r"^\s*(Table|Figure|Fig\.|Algorithm|Example)\s*%s\s*(?:[.:–—-]|$)" % LABEL_ID, re.I)


def choose(candidates, entry, position=None, after=-1, following=0):
    """The first candidate that is the same section: its words overlap the entry's title,
    or it is only the bare number or label ("APPENDIX D", "Chapter 9") with the title in the next block.
    For a table or figure, a caption ("Table 3.", "Table 3:", or the table/figure block itself)
    comes before prose that mentions it ("Table 3 provides ...")."""
    wanted = title_words(entry)
    if position is not None:
        # TOC entries come in document order: "A. Introduction" under chapter III is the
        # second "A. Introduction", not the one under chapter I. Only blocks after the TOC
        # (positions below `following`) are ordered; blocks before it stay last.
        def rank(candidate):
            place = position.get(candidate[0], following)
            return 0 if after < place < following else 1 if place < following else 2
        candidates = sorted(candidates, key=rank)
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


BARE_TITLE = re.compile(r"^\s*(figures|tables|algorithms|examples|appendices|appendixes)\s*$", re.I)


def is_toc_title(blocks, index):
    """A title of the printed TOC or of a list of figures/tables. Some were extracted as
    paragraphs, and some documents use a bare "Figures" or "Tables"; a bare title counts
    only when the next line looks like a TOC line."""
    block = blocks[index]
    if block["kind"] not in ("heading", "paragraph", "list_item"):
        return False
    text = plain(block.get("html"))
    if TOC_HEADING.match(text):
        return True
    if BARE_TITLE.match(text) and index + 1 < len(blocks):
        following = plain(blocks[index + 1].get("html"))
        return bool(PAGE.search(following) or LEADER.search(following))
    return False


# where one entry ends and the next begins in a line that holds several entries:
# a dot leader or dash with its page number, then a section number or label
# the page number is taken whole (an atomic group), so "...... 31 Fig. 3-2" never starts an entry "31"
SPLIT = re.compile(r"(?:(?:\s*[.…]){3,}|…+|\s[—–])\s*(?>(?:[A-Z]{1,3}[-–]\d{1,3}|[A-Z]\.\d{1,2}-\d{1,3}|\d{1,4}(?:-\d{0,3})?|[ivxlcdm]{1,7}\b)?)\s+"
                   r"(?=(?:\d{1,2}(?:\.\d{1,3})*\.?|[A-Z]\.\d{1,3}(?:\.\d{1,3})*\.?|Appendix|Annex|Figure|Fig\.|Table)\s|付録|付属書|附属書|図|表|第)", re.I)


def split_entries(text):
    """Several TOC entries extracted as one paragraph, split back into entries."""
    parts, start = [], 0
    for match in SPLIT.finditer(text):
        parts.append(text[start:match.end()].strip())
        start = match.end()
    parts.append(text[start:].strip())
    return [part for part in parts if part]


DOTTED = re.compile(r"(?:[.…]\s*){3,}\s*(?:[A-Z]{1,3}[-–]\d{1,3}|[A-Z]\.\d{1,2}-\d{1,3}|\d{1,4}(?:-\d{0,3})?|[ivxlcdm]{1,7}\b)?\s*$", re.I)


def toc_line(block):
    text = plain(block.get("html"))
    return block["kind"] in ("paragraph", "list_item", "heading", "math") and bool(PAGE.search(text) or DOTTED.search(text))


def solid_line(blocks, index):
    """A line that is surely a TOC entry: a dot leader or a dash before the page number, or a
    page number with another TOC line right after it. The document title repeated under the
    TOC title ("... Standards Publication 204") ends in a number but is followed by other text."""
    text = plain(blocks[index].get("html"))
    if DOTTED.search(text) or re.search(r"[—–]\s*\S+\s*$", text):
        return toc_line(blocks[index])
    return toc_line(blocks[index]) and index + 1 < len(blocks) and toc_line(blocks[index + 1])


def untitled_run(blocks, index, length=4):
    """A TOC whose title was lost or never printed (FIPS 201-3, FIPS 204): four lines in a row
    that end with a page number, at least two of them with dot leaders, the first starting with
    a section number or a table/figure label. It starts at the earliest such line."""
    window = blocks[index:index + length]
    if len(window) < length or (index and toc_line(blocks[index - 1])
                                and (NUMBER.match(plain(blocks[index - 1].get("html")))
                                     or LABEL.match(plain(blocks[index - 1].get("html"))))):
        return False
    first = plain(blocks[index].get("html"))
    if not (NUMBER.match(first) or LABEL.match(first)):
        return False
    return all(toc_line(block) for block in window) and \
        sum(bool(DOTTED.search(plain(block.get("html")))) for block in window) >= 2


# an entry in a list of appendices printed without page numbers ("A FIRMPOC Survey", "B - Vendor List")
APPENDIX_LINE = re.compile(r"^\s*(?:Appendix\s+)?[A-Z](?:\s*[-–—:.]\s*|\s+)[A-Z0-9\"“]")
# an entry that starts with its table/figure number but not the word ("III-1 Target Agency ...", "1. Flowchart")
BARE_LABEL = re.compile(r"^\s*(?:[A-Z]{1,4}(?:\([A-Z]\))?-\d|\d{1,3}(?:[.-]\d{1,3})*\.?\s)")


def list_label(text):
    """"Table", "Figure" or "Appendix" for the title of a list of one kind, else None."""
    match = re.match(r"^\s*(?:list of\s+)?(tables|figures|appendices|appendixes)\s*$", text, re.I)
    if not match:
        return None
    return {"tables": "Table", "figures": "Figure"}.get(match.group(1).lower(), "Appendix")


def printed_toc(blocks):
    """{block id: {"depth", "target", "en", "ja"}} for the lines of the printed TOC.

    `blocks` are the visible blocks in page order (with "html" and "html_ja").
    """
    result = {}
    index = 0
    while index < len(blocks):
        titled = is_toc_title(blocks, index)
        if not titled and not untitled_run(blocks, index):
            index += 1
            continue
        block = blocks[index]
        label = list_label(plain(block.get("html"))) if titled else None

        def appendix_line(position):
            # a list of appendices may print no page numbers at all
            candidate = blocks[position]
            text = plain(candidate.get("html"))
            return label == "Appendix" and candidate["kind"] in ("paragraph", "list_item") \
                and len(text) < 200 and bool(APPENDIX_LINE.match(text))

        # a TOC without a title block starts with its first line
        lines, cursor = [], index + 1 if titled else index
        # a short line between the title and the first entry (the document title repeated,
        # or a column header "Table — Content") is skipped
        if titled and cursor < len(blocks) and not (solid_line(blocks, cursor) or appendix_line(cursor)):
            ahead = blocks[cursor:cursor + 4]
            first = next((offset for offset in range(len(ahead))
                          if solid_line(blocks, cursor + offset) or appendix_line(cursor + offset)), None)
            # a longer subtitle ("VOLUME I: DOE RISK ASSESSMENT ...", IR 4325) is skipped too, but not a table
            if first and all(len(plain(b.get("html"))) <= 100 or (
                    len(plain(b.get("html"))) <= 200 and b["kind"] in ("paragraph", "heading"))
                    for b in ahead[:first]):
                cursor += first
        while cursor < len(blocks):
            candidate = blocks[cursor]
            text = plain(candidate.get("html"))
            if is_toc_title(blocks, cursor):
                break  # the next list ("List of Figures") starts here
            if candidate["kind"] not in ("paragraph", "list_item", "heading", "math") or not (
                    PAGE.search(text) or LEADER.search(text) or len(split_entries(text)) > 1
                    or appendix_line(cursor)):
                break
            # a heading after the TOC can end in a number ("Acknowledgments for Revision 3"):
            # a heading counts as a TOC line only with a dot leader or a dash before its page number
            if candidate["kind"] == "heading" and not (DOTTED.search(text) or re.search(r"[—–]\s*\S+\s*$", text)):
                break
            lines.append(candidate)
            cursor += 1
        toc_ids = {line["id"] for line in lines} | {block["id"]}
        rest = [b for b in blocks[cursor:] + blocks[:index] if b["id"] not in toc_ids]
        targets = find_targets(rest, 0)
        position = {b["id"]: number for number, b in enumerate(rest)}
        following = sum(1 for b in blocks[cursor:] if b["id"] not in toc_ids)
        previous = [-1]

        def entry(text, japanese):
            text = strip_page(text)
            # in a list of tables, figures or appendices the entry may leave out the word
            probe = text
            if label in ("Table", "Figure") and not LABEL.match(text) and BARE_LABEL.match(text):
                probe = "%s %s" % (label, text)
            elif label == "Appendix" and APPENDIX_LINE.match(text) and not re.match(r"\s*Appendix\b", text, re.I):
                probe = "Appendix " + text
            def find(probe):
                key = entry_key(probe)
                target = choose(targets.get(key, []), probe, position, previous[0], following)
                if target is None:
                    target = choose(targets.get(("title", words(NUMBER.sub("", LABEL.sub("", probe)))), []),
                                    probe, position, previous[0], following)
                return key, target

            # the word is added only when the line does not link as printed: a list title can be
            # extracted out of place (SP 800-226), and "4.1. Query Models" is then not "Table 4.1"
            # A lettered line under "List of Appendices" is surely an appendix: that is tried first.
            first, second = (probe, text) if label == "Appendix" else (text, probe)
            key, target = find(first)
            if target is None and probe != text:
                other = find(second)
                if other[1] is not None:
                    key, target = other
            if target is not None and position[target] < following:
                previous[0] = position[target]
            return {"depth": min(depth_of(key), 4), "target": target, "en": text,
                    "ja": strip_page(japanese) if japanese else text, "key": key}

        for line in lines:
            def parts(markup):
                # a list of appendices may keep its lines in one block, separated by <br>
                if label == "Appendix" and re.search(r"<br\s*/?>", markup or ""):
                    return [plain(part) for part in re.split(r"<br\s*/?>", markup) if plain(part)]
                return split_entries(plain(markup))
            english = parts(line["html"])
            japanese = parts(line.get("html_ja")) if line.get("html_ja") else []
            if len(japanese) != len(english):
                # pair by section number when the Japanese split differently; otherwise show the English
                by_key = {entry_key(strip_page(part)): part for part in japanese}
                japanese = [by_key.get(entry_key(strip_page(part)), "") for part in english] \
                    if len(english) > 1 else [plain(line.get("html_ja"))]
            entries = [entry(part, ja) for part, ja in zip(english, japanese or [""] * len(english))]
            # a line that is only a page number ("— 55") or a column header ("PAGE") shows nothing
            entries = [e for e in entries if e["en"].strip(" —–.…") and e["en"].strip().lower() != "page"] or [dict(entries[0], en="", ja="", target=None)]
            first = entries[0]
            result[line["id"]] = dict(first, entries=entries)
        index = cursor
    return result
