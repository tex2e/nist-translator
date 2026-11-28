"""Footnotes on the reading page: link references to their notes, and gather the notes.

The data keeps each footnote where the PDF printed it (the foot of the page), so a footnote
can sit between the two halves of a paragraph that runs onto the next page. On the page
(display only; the data is unchanged):

- each reference number <sup>N</sup> in the body links to its footnote, and the footnote
  links back to the row that refers to it;
- the footnotes of a section are shown together at the end of the section, before the next
  heading;
- a block that holds several footnotes ("3For example… 4For example…") is shown as one row
  per footnote, and every footnote opens with its number in the same style, whether the data
  has "15 ", "<sup>15</sup>" or "¹⁵".
"""

import re

from markupsafe import Markup

# "15 A reasonable…", "<sup>3</sup>For example…", "<sup>4</sup> 45 CFR 160", "<p>12 https://…",
# "2: During…", "1 * See…", "2 &lt;PrintedName&gt;…"
HEAD = re.compile(r"\s*(?:<p>)?\s*(?:<sup>(\d{1,3})</sup>\s*(?=\S)|(\d{1,3}):?\s*(?=[A-Za-z(“\"\[‘§&*]|https?:|<(?!/)|\\\(|(?<=\s)\d))")
REFERENCE = re.compile(r"<sup>(\d{1,3})</sup>")
# several references in one superscript: "<sup>36,37</sup>" or "<sup>31 32</sup>" -> "<sup>36</sup>,<sup>37</sup>"
GROUPED = re.compile(r"<sup>(\d{1,3}(?:\s*,\s*\d{1,3}|\s+\d{1,3})+)</sup>")


# a reference in an HTML original that links to the footnote on the NIST site
EXTERNAL = re.compile(r'<sup><a href="[^"]*#fn:[^"]*">(\d{1,3})</a></sup>')


def _ungroup(markup):
    markup = EXTERNAL.sub(r"<sup>\1</sup>", markup)
    return GROUPED.sub(lambda m: ",".join("<sup>%s</sup>" % n for n in re.findall(r"\d+", m.group(1))), markup)
BACK_ARROW = re.compile(r"\s*↩\s*(?=(?:</p>)?\s*$)")
MARK = re.compile(r"\s*(?:<p>)?\s*(?:<sup>)?[*†‡§]")
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
# a footnote is printed on the page of its reference or, when the text runs on, a page or two later
PAGE_REACH = 2


def footnote_numbers(markup):
    """Numbers of the footnotes in one footnote block: "3For example… 4For example…" -> [3, 4]."""
    return [number for number, _ in _starts(markup)]


def _starts(markup):
    """[(number, offset)]: where each footnote of an English footnote block begins."""
    match = HEAD.match(markup or "")
    if not match:
        return []
    starts = [(int(match.group(1) or match.group(2)), 0)]
    position = match.end()
    while True:
        follow = re.compile(r"(?<=[.)\]”\"])\s*(?:</p>\s*<p>)?\s*(?:<sup>%d</sup>|%d\s*(?=[A-Z(“\"\[]|https?:|<a\b))"
                            % ((starts[-1][0] + 1,) * 2)).search(markup, position)
        if not follow:
            return starts
        starts.append((starts[-1][0] + 1, follow.start()))
        position = follow.end()


def _japanese_starts(markup, numbers):
    """Offsets where footnotes numbers[1:] begin in the Japanese, or None when one is not found."""
    offsets, position = [0], 0
    for number in numbers[1:]:
        raised = str(number).translate(SUPERSCRIPT)
        follow = re.compile(r"(?<=[。．.)）\]］」』”])\s*(?:</p>\s*<p>)?\s*(?:<sup>%d</sup>|%d(?![0-9０-９.．])|%s(?![⁰¹²³⁴⁵⁶⁷⁸⁹]))"
                            % (number, number, raised)).search(markup, position)
        if not follow:
            return None
        offsets.append(follow.start())
        position = follow.end()
    return offsets


def _pieces(markup, offsets):
    """Cut markup at offsets; each piece keeps balanced <p> tags."""
    pieces = []
    for start, end in zip(offsets, offsets[1:] + [len(markup)]):
        piece = markup[start:end].strip()
        piece = re.sub(r"^(?:</p>\s*)+|(?:\s*<p>)+$", "", piece)
        opened, closed = piece.count("<p>"), piece.count("</p>")
        if opened > closed:
            piece += "</p>" * (opened - closed)
        elif closed > opened:
            piece = "<p>" * (closed - opened) + piece
        pieces.append(piece)
    return pieces


def _numbered(markup, number):
    """The footnote with its leading number (in any of the data's styles) replaced by one style."""
    raised = str(number).translate(SUPERSCRIPT)
    lead = re.compile(r"^(\s*(?:<p>)?)\s*(?:<sup>%d</sup>|%d(?![0-9０-９])[:：]?|%s(?![⁰¹²³⁴⁵⁶⁷⁸⁹]))\s*" % (number, number, raised))
    body = lead.sub(r"\1", markup, count=1)
    opening = re.match(r"\s*(?:<p>)?", body).end()
    return body[:opening] + '<span class="fn-num">%d</span>' % number + body[opening:]


def split_footnotes(visible):
    """One row per footnote, each opening with its number in one style.

    Footnotes taken from an HTML original (no PDF page) carry no number in the data: the
    original numbers each group of footnotes 1, 2, 3, … and ends each with "↩". Those are
    numbered by their place in the run of consecutive footnotes."""
    result = []
    run = 0
    for item in visible:
        english = str(item.get("english_html", "")) if item.get("kind") == "footnote" else ""
        starts = _starts(english)
        if item.get("kind") != "footnote":
            run = 0
        if not starts and english and not item.get("source_page") and not MARK.match(english):
            run += 1
            piece = dict(item, footnote_numbers=[run])
            piece["english_html"] = Markup(_numbered(BACK_ARROW.sub("", english), run))
            if item.get("html_ja"):
                piece["japanese_html"] = Markup(_numbered(BACK_ARROW.sub("", str(item.get("japanese_html", ""))), run))
            result.append(piece)
            continue
        if not starts:
            result.append(item)
            continue
        numbers = [number for number, _ in starts]
        japanese = str(item.get("japanese_html", "")) if item.get("html_ja") else ""
        japanese_offsets = _japanese_starts(japanese, numbers) if japanese else [0] * len(numbers)
        if len(numbers) == 1 or japanese_offsets is None:
            # one footnote, or several whose Japanese cannot be cut at the same places
            piece = dict(item, footnote_numbers=numbers)
            piece["english_html"] = Markup(_numbered(english, numbers[0]))
            if japanese:
                piece["japanese_html"] = Markup(_numbered(japanese, numbers[0]))
            if len(numbers) > 1:
                piece["footnote_unsplit"] = True
            result.append(piece)
            continue
        english_pieces = _pieces(english, [offset for _, offset in starts])
        japanese_pieces = _pieces(japanese, japanese_offsets) if japanese else [""] * len(numbers)
        for index, number in enumerate(numbers):
            piece = dict(item, footnote_numbers=[number])
            if index:
                piece["id"] = "%s-fn%d" % (item["id"], number)
            piece["english_html"] = Markup(_numbered(english_pieces[index], number))
            if japanese:
                piece["japanese_html"] = Markup(_numbered(japanese_pieces[index], number))
            result.append(piece)
    return result


def _page(item):
    return item.get("source_page") or 0


def _last_page(item):
    """The last page a row is printed on (a table can run over several pages)."""
    pages = [ref.get("page") or 0 for ref in item.get("source_refs") or []]
    return max(pages + [item.get("source_page_end") or 0, _page(item)])


def _target(notes, number, index, page, far=False, span=0):
    """The footnote block for reference `number` in the row at `index`.

    Near (the first pass): the first one after the row within a few pages, else the nearest
    one before it within a few pages (a table that continues on the next page, or a second
    reference to the same footnote).
    Far (the second pass, for endnotes printed far away): the document's one footnote with
    that number, after the reference, that no nearby reference has claimed."""
    candidates = notes.get(number, [])
    if far:
        if len(candidates) == 1 and candidates[0][0] > index and not candidates[0][1].get("footnote_backrefs"):
            return candidates[0][1]
        return None
    after = [(i, item) for i, item in candidates if i > index and 0 <= _page(item) - page <= PAGE_REACH + span]
    if after:
        return after[0][1]
    before = [(i, item) for i, item in candidates if i < index and 0 <= page - _page(item) <= PAGE_REACH]
    return before[-1][1] if before else None


def _link(number, note):
    return ('<sup class="fnref"><a href="#%s" data-fn="%s" aria-label="脚注 %d">%d</a></sup>'
            % (note["id"], note["id"], number, number))


def link_footnotes(visible):
    """Link <sup>N</sup> references to their footnote rows and record back links."""
    notes = {}
    for index, item in enumerate(visible):
        if item.get("kind") == "footnote":
            for number in item.get("footnote_numbers", []):
                notes.setdefault(number, []).append((index, item))
    if not notes:
        return
    _link_rows(visible, notes, far=False)
    _link_rows(visible, notes, far=True)
    for numbered in notes.values():
        for _, note in numbered:
            note.setdefault("footnote_backrefs", []).sort()


UNIT = re.compile(r"(?:\b(?:m|mm|cm|km|ft)|[µμ]m)$")


def _word_before(text):
    """Before a far reference: a word (not a unit such as "m²" or "µm²") or sentence punctuation."""
    return bool(re.search(r"[a-z.,;:\"”’]$", text)) and not UNIT.search(text)


def _link_rows(visible, notes, far):
    for index, item in enumerate(visible):
        # a footnote can refer to another footnote ("… other related information⁵⁵" in note 54)
        if "<sup" not in str(item.get("english_html", "")):
            continue
        page = _page(item)
        linked = {}

        def english(match):
            number = int(match.group(1))
            if ((far or item.get("kind") == "footnote")
                    and not _word_before(re.sub(r"<[^>]*>", "", match.string[max(0, match.start() - 80):match.start()]))):
                return match.group(0)
            note = _target(notes, number, index, page, far, _last_page(item) - page)
            if not note:
                return match.group(0)
            linked[number] = note
            return _link(number, note)

        item["english_html"] = Markup(REFERENCE.sub(english, _ungroup(str(item["english_html"]))))
        if not linked:
            continue
        japanese = _ungroup(str(item.get("japanese_html", "")))
        if japanese:
            japanese = REFERENCE.sub(lambda m: _link(int(m.group(1)), linked[int(m.group(1))])
                                     if int(m.group(1)) in linked else m.group(0), japanese)
            for number, note in linked.items():
                # a Unicode superscript ("長官³") used in place of <sup>3</sup>, once in the row
                raised = str(number).translate(SUPERSCRIPT)
                if japanese.count(raised) == 1 and not re.search(
                        "[⁰¹²³⁴⁵⁶⁷⁸⁹]%s|%s[⁰¹²³⁴⁵⁶⁷⁸⁹]" % (raised, raised), japanese):
                    japanese = japanese.replace(raised, _link(number, note))
            item["japanese_html"] = Markup(japanese)
        for number, note in linked.items():
            backrefs = note.setdefault("footnote_backrefs", [])
            if number not in [n for n, _ in backrefs]:
                backrefs.append((number, item["id"]))


def gather_footnotes(visible):
    """Move footnote rows to the end of the section that refers to them (just before the next
    heading after the first reference; a footnote nobody links to uses its own position).

    Only rows that open with a footnote number or mark move: some captions, running headers
    and images were extracted as footnotes, and those stay where the PDF printed them."""
    position = {item["id"]: index for index, item in enumerate(visible)}
    headings = [index for index, item in enumerate(visible) if item.get("kind") == "heading"]
    moving = {}
    for index, item in enumerate(visible):
        english = str(item.get("english_html", ""))
        if item.get("kind") != "footnote" or not (item.get("footnote_numbers") or MARK.match(english)):
            continue
        refs = [position[ref] for _, ref in item.get("footnote_backrefs", []) if ref in position]
        anchor = min(refs) if refs else index
        end = next((h for h in headings if h > anchor), len(visible))
        moving.setdefault(end, []).append(index)
    moved = {index for indexes in moving.values() for index in indexes}
    result = []
    for index, item in enumerate(visible):
        result.extend(visible[i] for i in moving.get(index, []))
        if index not in moved:
            result.append(item)
    return result + [visible[i] for i in moving.get(len(visible), [])]
