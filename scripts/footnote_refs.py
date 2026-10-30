"""Turn footnote reference numbers that extraction glued to the text into superscripts.

    python scripts/footnote_refs.py [--apply] [--report PATH] [--decisions PATH]

A number counts as a footnote reference only when it follows a lowercase letter, a closing
bracket or quote, or sentence punctuation after such a character ("policies.7 As",
"clients3 can", "(risk8 at"), and a footnote with that number is printed on one of the
block's pages. The English gets <sup>N</sup> at that place. The Japanese gets it where the
same number stands alone and nothing else in the block can be that number (or where a
Unicode superscript such as ¹¹ is used). Other cases are written to the report for
a reviewer; --decisions applies the reviewer's Japanese for them:
[{"doc", "id", "n", "html_ja"}] (html_ja with the <sup>N</sup> placed).
"""

import argparse
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"paragraph", "list_item", "note", "heading"}
HIDDEN = ("page_furniture", "math_duplicate_of", "duplicate_artifact_of", "figure_text_of",
          "official_mark", "third_party_excerpt")
SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
# text outside tags; <a>, <code>, <sup> and math are skipped
PROTECTED = re.compile(r"<(a|code|sup|pre)\b.*?</\1>|<[^>]+>|\\\(.*?\\\)|\\\[.*?\\\]", re.S)


def segments(html):
    """(start, end) spans of plain text that may hold a reference."""
    position = 0
    for match in PROTECTED.finditer(html):
        yield position, match.start()
        position = match.end()
    yield position, len(html)


def english_refs(html, numbers):
    found = []
    for start, end in segments(html):
        for match in re.finditer(r"(?<=[a-z\)\]”’\"])([.,;:]?)(\d{1,3})(?=[\s.,;:)\]]|$)", html[start:end]):
            punct, digits = match.group(1), match.group(2)
            before = html[start:end][:match.start()]
            if punct and (not before or not re.search(r"[a-z\)\]”’\"]$", before)):
                continue
            # "&#x27;" (a character reference) and version numbers ("IPv6", "IKEv2", "v1") are not references
            if re.search(r"&#x?[0-9a-fA-F]*$", before) or re.search(r"(?:\b|[A-Z])v$", before):
                continue
            if int(digits) in numbers:
                found.append((start + match.start(2), start + match.end(2), int(digits)))
    return found


def standalone(text, n):
    plain = [m.span() for m in re.finditer(r"(?<![0-9０-９.,])%d(?![0-9０-９])" % n, text)]
    sup = [m.span() for m in re.finditer(re.escape(str(n).translate(SUPERSCRIPT)), text)]
    return plain, sup


def plain_text_spans(html, spans):
    allowed = list(segments(html))
    return [s for s in spans if any(a <= s[0] and s[1] <= b for a, b in allowed)]


def place_ja(html_ja, english_without_ref, n):
    plain, sup = standalone(html_ja, n)
    plain, sup = plain_text_spans(html_ja, plain), plain_text_spans(html_ja, sup)
    others = len(plain_text_spans(english_without_ref, standalone(english_without_ref, n)[0]))
    if len(sup) == 1:
        span = sup[0]
    elif len(plain) == 1 and others == 0:
        span = plain[0]
    else:
        return None
    start, end = span
    # "である。 4 また" -> "である。<sup>4</sup>また"
    if start > 0 and html_ja[start - 1] == " " and (start < 2 or ord(html_ja[start - 2]) > 0x2fff):
        start -= 1
    if end < len(html_ja) and html_ja[end] == " " and (end + 1 >= len(html_ja) or ord(html_ja[end + 1]) > 0x2fff):
        end += 1
    return html_ja[:start] + "<sup>%d</sup>" % n + html_ja[end:]


def footnotes(document):
    """{number: {page: footnote block id}}. Besides footnote blocks, a paragraph in the lower
    part of a page that starts with "N text" counts (some PDFs were extracted that way)."""
    numbers = {}
    for block in document["contents"]:
        if any(block.get(k) for k in HIDDEN) or not block.get("source_page"):
            continue
        if block["kind"] == "footnote":
            match = re.match(r"\s*(?:<sup>)?(\d{1,3})\b", block["html"])
        elif block["kind"] == "paragraph" and block.get("source_refs") and block["source_refs"][0]["bbox"][1] > 480:
            match = re.match(r"\s*(\d{1,3})\s+(?=[A-Z(“\"]|https?:|<a\b)", block["html"])
        else:
            match = None
        if match:
            numbers.setdefault(int(match.group(1)), {})[block["source_page"]] = block["id"]
    return numbers


def pages(block):
    return {ref["page"] for ref in block.get("source_refs", [])} | {block["source_page"]}


def process(path, apply, decisions, report, skip=frozenset()):
    document = json.loads(path.read_text())
    doc = path.name[:-len("-trans.json")]
    numbers = footnotes(document)
    notes = {block_id for on in numbers.values() for block_id in on.values()}
    by_id = {block["id"]: block for block in document["contents"]}
    already = {int(n) for b in document["contents"] for n in re.findall(r"<sup>(\d{1,3})</sup>", b["html"])}
    counts = {"auto": 0, "review": 0, "decided": 0}
    used = set()
    changed = False
    for block in document["contents"]:
        if (block["kind"] not in KINDS or any(block.get(k) for k in HIDDEN) or not block["html"]
                or block["id"] in notes or not block.get("source_page")):
            continue
        # the footnote is printed on the block's page, or on the next page when the text runs on
        near = pages(block) | {max(pages(block)) + 1}
        here = {n for n, on in numbers.items() if set(on) & near and n not in already}
        refs = [r for r in english_refs(block["html"], here)
                if r[2] not in used and (doc, block["id"], r[2]) not in skip]
        for start, end, n in sorted(refs, reverse=True):
            used.add(n)
            english = block["html"][:start] + "<sup>%d</sup>" % n + block["html"][end:]
            without = block["html"][:start] + block["html"][end:]
            japanese = None
            key = (doc, block["id"], n)
            if key in decisions:
                japanese = decisions[key]
                counts["decided"] += 1
            elif block.get("html_ja") and block["status"] in {"draft", "reviewed"}:
                japanese = place_ja(block["html_ja"], without, n)
                if japanese is not None:
                    counts["auto"] += 1
            else:
                japanese = block.get("html_ja", "")
                counts["auto"] += 1
            if japanese is None:
                counts["review"] += 1
                report.append({"doc": doc, "id": block["id"], "n": n, "page": block["source_page"],
                               "html": english, "html_ja": block["html_ja"],
                               "footnote": next((b["html"] for b in document["contents"]
                                                 if b["id"] in numbers[n].values()), "")})
                continue
            if apply:
                block["html"], block["html_ja"] = english, japanese
                block["footnote_ref_fix"] = "2026-10-31"
                for page in sorted(set(numbers[n]) & near):
                    note = by_id[numbers[n][page]]
                    if note["kind"] == "paragraph":
                        note["kind"] = "footnote"  # extracted as body text; it is the footnote
                        note["kind_fix"] = "2026-10-31: footnote"
                changed = True
    if apply and changed:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return counts


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--report", type=Path)
    cli.add_argument("--decisions", type=Path)
    cli.add_argument("--skip", type=Path, help="[{doc, id, n}] that are not footnote references")
    cli.add_argument("docs", nargs="*")
    args = cli.parse_args()
    decisions = {}
    if args.decisions:
        for item in json.loads(args.decisions.read_text()):
            decisions[(item["doc"], item["id"], item["n"])] = item["html_ja"]
    skip = set()
    if args.skip:
        skip = {(item["doc"], item["id"], item["n"]) for item in json.loads(args.skip.read_text())}
    report, total = [], {"auto": 0, "review": 0, "decided": 0}
    paths = [ROOT / "data" / (d + "-trans.json") for d in args.docs] or \
        [Path(p) for p in sorted(glob.glob(str(ROOT / "data" / "*-trans.json")))]
    for path in paths:
        counts = process(path, args.apply, decisions, report, skip)
        for key in total:
            total[key] += counts[key]
    print(total, "documents:", len({r["doc"] for r in report}), "with items to review")
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
