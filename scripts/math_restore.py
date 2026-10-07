"""Restore mathematics in extracted PDF blocks as structural LaTeX.

The stored format is the one used for SP 800-22r1: a ``kind: math`` block
whose ``html`` and ``html_ja`` carry KaTeX LaTeX in ``\\(...\\)`` / ``\\[...\\]``,
with the replaced extraction blocks kept in ``math_preservation``. Rules for
the LaTeX itself are in skills/nist-document-extraction/SKILL.md.

    python scripts/math_restore.py export  KEY WORK_DIR --pdf-dir DIR [--pages 9-18] [--every-block]
    python scripts/math_restore.py apply   KEY WORK_DIR
    python scripts/math_restore.py render  KEY WORK_DIR --pdf-dir DIR
    python scripts/math_restore.py check   KEY WORK_DIR
    python scripts/math_restore.py revise-export KEY WORK_DIR --pdf-dir DIR
    python scripts/math_restore.py revise-apply  KEY WORK_DIR
    python scripts/math_restore.py figures-export KEY WORK_DIR --pdf-dir DIR
    python scripts/math_restore.py figures-apply  KEY WORK_DIR --pdf-dir DIR

``export`` writes ``restore.NNN.batch.json`` and a 300 dpi crop of each
candidate block: blocks with raised, lowered or mixed-size glyphs, mathematical
symbols, italic fonts or a lone capital letter, and the blocks right next to
them. ``--every-block`` offers every text block instead. A restorer answers each batch with ``restore.NNN.result.json``: a
list of ``{"id", "is_math", "html", "html_ja", "notes", "merged_into"}``. A
block whose text belongs to a formula restored in another block of the same
batch names that block in ``merged_into`` and is removed.

``apply`` validates the answers and replaces the blocks (``needs_review``).

``render`` screenshots each restored block as KaTeX displays it and writes
``check.NNN.batch.json``; a reviewer compares it with the original crop and
answers with ``check.NNN.result.json``: a list of
``{"id", "verdict", "observations"}``. Each batch also carries a few copies
with a deliberate error. Blocks in a check batch have opaque ids; which block
each one is, and which are the planted copies, is in ``check.NNN.key.json``,
which the reviewer is not given.

``check`` marks blocks whose display matches the original as ``verified``. It
accepts a batch's ``ok`` verdicts only if the reviewer reported every planted
error in that batch.

``revise-export`` writes ``revise.batch.json`` with the restored blocks whose
display was found to differ from the original, together with the reviewer's
observation. A restorer answers with ``revise.result.json``: a list of
``{"id", "html", "html_ja", "notes"}``. ``revise-apply`` stores the corrected
blocks as unchecked drafts, so they go through ``render`` and ``check`` again.

``figures-export`` finds regions of drawn graphics that enclose extracted text
(diagram labels end up as stray paragraphs) and writes ``figures.batch.json``
with a crop of each. A reviewer answers with ``figures.result.json``: a list of
``{"id", "is_figure", "label_ja"}``. ``figures-apply`` replaces the blocks
inside each confirmed figure with one ``source_excerpt`` block that shows the
original image, as SP 800-22r1 does.
"""

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nist_translater.pdf_equations import inline_katex_html  # noqa: E402
from nist_translater.storage import read_json, write_json  # noqa: E402
from nist_translater.translation import (  # noqa: E402
    NORMATIVE, assert_same_html_structure, audit_translations, source_text)

VERSION = 1
DPI = 300
BATCH = 40
CHECK_BATCH = 20
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
KATEX = ROOT / "static" / "vendor" / "katex"
FORMULA = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.S)
TAGLESS = re.compile(r"<[^>]+>")
MATH_REASONS = {"math_symbol", "raised_or_lowered_text", "mixed_size", "bad_character"}
ITALIC = re.compile(r"Ital|Obli")
# A capital letter standing alone ("the function, W, for") is usually a variable.
LONE_CAPITAL = re.compile(r"(?<![A-Za-z0-9.'’-])[B-HJ-Z](?![A-Za-z0-9.'’-])")
NEAR = 14  # points: fragments of a formula sit right next to it


def _path(key):
    return ROOT / "data" / (key + "-trans.json")


def _source_hash(kind, source_html):
    return hashlib.sha256((kind + "\n" + source_html + "\n").encode("utf-8")).hexdigest()[:16]


def _page_set(value):
    pages = set()
    for part in (value or "").split(","):
        if part.strip():
            first, _, last = part.partition("-")
            pages.update(range(int(first), int(last or first) + 1))
    return pages


def _write_batches(work, stem, header, items, size):
    for path in work.glob(stem + ".*.batch.json"):
        path.unlink()
    for index in range(0, len(items), size):
        write_json(work / ("%s.%03d.batch.json" % (stem, index // size + 1)),
                   dict(header, blocks=items[index:index + size]))
    return (len(items) + size - 1) // size


def _results(work, stem):
    """Answers of every batch that has a result file covering it exactly."""
    answers, skipped = [], []
    for batch_path in sorted(work.glob(stem + ".*.batch.json")):
        path = batch_path.with_name(batch_path.name.replace(".batch.json", ".result.json"))
        expected = [item["id"] for item in read_json(batch_path)["blocks"]]
        try:
            result = read_json(path)
            if sorted(item["id"] for item in result) != sorted(expected):
                raise ValueError("ids differ from the batch")
        except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
            skipped.append("%s: %s" % (batch_path.name, error))
            continue
        answers.append((batch_path, result))
    return answers, skipped


def _span(block):
    """The box around every part of a block on its page."""
    boxes = [ref["bbox"] for ref in block["source_refs"] if ref["page"] == block["source_page"]]
    return [min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes)]


def _recon(block):
    """Where a rebuilt block keeps the record of its comparison with the original."""
    return block.get("math_reconstruction") or block.get("paragraph_merge")


TERMINAL = re.compile(r"[.:;?!)\]”\"]$")
STARTS_ITEM = re.compile(r"^(\d+\.|[a-z]\.|\(|•|–|-\s|[A-Z][a-z]+:)")


def fragment_groups(document):
    """Runs of consecutive blocks that look like the lines of one paragraph.

    A line that fills the column and does not end a sentence, followed closely
    by text at the same left edge, is taken to continue; so is the last block
    of a page followed by a lower-case start on the next page. A restorer looks
    at the original before anything is merged.
    """
    blocks = [block for block in document["contents"]
              if not block.get("duplicate_artifact_of") and not block.get("math_duplicate_of")]
    text = lambda block: html.unescape(TAGLESS.sub("", block["html"])).strip()
    groups, current = [], []
    for first, second in zip(blocks, blocks[1:]):
        joined = False
        if (first["kind"] in {"paragraph", "list_item", "footnote", "math"} and
                second["kind"] in {"paragraph", "footnote", "math"} and
                first.get("source_refs") and second.get("source_refs")):
            end, start = first["source_refs"][-1], second["source_refs"][0]
            a, b = text(first), text(second)
            wide = end["bbox"][2] - end["bbox"][0] > 200
            if a and b and wide and not TERMINAL.search(a) and not STARTS_ITEM.match(b):
                if end["page"] == start["page"]:
                    gap = start["bbox"][1] - end["bbox"][3]
                    joined = -3 <= gap <= 5 and abs(start["bbox"][0] - end["bbox"][0]) < 40
                elif start["page"] == end["page"] + 1:
                    joined = (b[0].islower() and end["bbox"][3] > 600 and
                              start["bbox"][1] < 140)
        if joined:
            if not current:
                current = [first]
            current.append(second)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def candidates(document, pdf, page_filter=(), every_block=False, only_ids=()):
    """Blocks that may contain mathematics, with the page data used to find them.

    Glyph geometry finds raised and lowered text, italic fonts find variables
    set on the baseline, and anything right next to such a block is included
    because formulas are often extracted as several fragments.
    """
    import pypdfium2.raw as pdfium_c
    import verify_extraction as verifier

    pages, eligible, chosen = {}, [], set()
    for block in document["contents"]:
        if (block["kind"] in {"figure", "math", "source_excerpt", "code"} or
                block.get("duplicate_artifact_of") or
                # A block assembled from several pieces is offered only when
                # asked for by id, and only if it lies on one page.
                (len(block["source_refs"]) != 1 and not (
                    only_ids and len({ref["page"] for ref in block["source_refs"]}) == 1))):
            continue
        number = block["source_page"]
        if page_filter and number not in page_filter:
            continue
        if only_ids and block["id"] not in only_ids:
            continue
        if number not in pages:
            pages[number] = verifier.PageData(pdf[number - 1], pdfium_c)
        page = pages[number]
        x0, top, x1, bottom = _span(block)
        text = verifier._block_text(block)
        reasons, _ = verifier._layout_reasons(block, page, text)
        inside = [char for char in page.chars
                  if x0 - 1 <= (char["x0"] + char["x1"]) / 2 <= x1 + 1 and
                  top - 1 <= (char["top"] + char["bottom"]) / 2 <= bottom + 1]
        eligible.append(block)
        if (every_block or only_ids or MATH_REASONS & set(reasons) or
                LONE_CAPITAL.search(text) or
                any(ITALIC.search(char["font"]) or
                    (("Symbol" in char["font"] or "Math" in char["font"]) and
                     char["text"] not in "•·") for char in inside)):
            chosen.add(block["id"])
    boxes = {}
    for block in eligible:
        if block["id"] in chosen:
            boxes.setdefault(block["source_page"], []).append(_span(block))
    for block in eligible:
        box = _span(block)
        if any(box[1] - NEAR <= other[3] and other[1] - NEAR <= box[3]
               for other in boxes.get(block["source_page"], [])):
            chosen.add(block["id"])
    return [block for block in eligible if block["id"] in chosen], pages


def export(key, work, pdf_dir, page_filter=(), every_block=False, only_ids=(), fragments=False):
    import pypdfium2

    document = read_json(_path(key))
    pdf_path = Path(pdf_dir) / (key + ".pdf")
    if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != document["source_sha256"]:
        raise ValueError("Local PDF does not match source_sha256")
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    work.mkdir(parents=True, exist_ok=True)
    groups = []
    if fragments:
        groups = [group for group in fragment_groups(document)
                  if all(len({ref["page"] for ref in block["source_refs"]}) == 1 or
                         block is group[-1] or block is group[0] for block in group)]
        import pypdfium2.raw as pdfium_c
        import verify_extraction as verifier
        blocks = [block for group in groups for block in group]
        pages = {}
        for block in blocks:
            if block["source_page"] not in pages:
                pages[block["source_page"]] = verifier.PageData(
                    pdf[block["source_page"] - 1], pdfium_c)
    else:
        blocks, pages = candidates(document, pdf, page_filter, every_block, only_ids)
    group_of = {block["id"]: index + 1 for index, group in enumerate(groups) for block in group}
    images, items = {}, []
    scale = DPI / 72
    for block in blocks:
        number = block["source_page"]
        _, top, _, bottom = _span(block)
        if number not in images:
            images[number] = pages[number].page.render(scale=scale).to_pil().convert("RGB")
        image = images[number]
        # Keep the full text width and a little context above and below.
        crop = image.crop((0, max(0, (top - 10) * scale),
                           image.width, min(image.height, (bottom + 10) * scale)))
        name = block["id"] + ".png"
        crop.save(work / name)
        items.append({"id": block["id"], "kind": block["kind"], "page": number,
                      "ordinal": block.get("ordinal"), "en": block["html"],
                      "ja": block.get("html_ja", ""), "image": str(work / name)})
        if fragments:
            items[-1]["group"] = group_of[block["id"]]
    header = {"document": document["number"], "title": document.get("subtitle", ""), "dpi": DPI}
    if fragments:
        # A paragraph must not be split between two batches.
        for path in work.glob("restore.*.batch.json"):
            path.unlink()
        chunks, chunk = [], []
        for group in groups:
            members = [item for item in items if item["group"] == group_of[group[0]["id"]]]
            if chunk and len(chunk) + len(members) > BATCH:
                chunks.append(chunk)
                chunk = []
            chunk += members
        if chunk:
            chunks.append(chunk)
        for index, chunk in enumerate(chunks):
            write_json(work / ("restore.%03d.batch.json" % (index + 1)),
                       dict(header, mode="paragraphs", blocks=chunk))
        count = len(chunks)
    else:
        count = _write_batches(work, "restore", header, items, BATCH)
    print("Exported %d candidate blocks on %d pages in %d batches to %s" % (
        len(items), len(images), count, work))


def _katex_errors(formulas):
    """Check every formula with the bundled KaTeX; return {index: message}."""
    script = (
        "const katex=require(process.argv[1]);let d='';process.stdin.on('data',c=>d+=c);"
        "process.stdin.on('end',()=>{const out={};JSON.parse(d).forEach((f,i)=>{try{"
        "katex.renderToString(f.tex,{displayMode:f.display,throwOnError:true,trust:false,"
        "strict:'error'})}catch(e){out[i]=String(e.message)}});console.log(JSON.stringify(out))})")
    payload = [{"tex": formula[2:-2], "display": formula.startswith("\\[")}
               for formula in formulas]
    result = subprocess.run(["node", "-e", script, str(KATEX / "katex.min.js")],
                            input=json.dumps(payload), capture_output=True, text=True, check=True)
    return {int(index): message for index, message in json.loads(result.stdout).items()}


def _problem(block, answer):
    """Why a restoration cannot be stored, or None."""
    english, japanese = answer.get("html", ""), answer.get("html_ja", "")
    if not english.strip() or not japanese.strip():
        return "empty html or html_ja"
    formulas = FORMULA.findall(html.unescape(english))
    if not formulas:
        return "no LaTeX formula in html"
    try:
        inline_katex_html(english)
        inline_katex_html(japanese)
        assert_same_html_structure(english, japanese, preserve_math=True)
    except ValueError as error:
        return str(error)
    probe = dict(block, html=english)
    if Counter(NORMATIVE.findall(japanese)) != Counter(NORMATIVE.findall(source_text(probe))):
        return "requirement keywords differ between html and html_ja"
    errors = _katex_errors(formulas + FORMULA.findall(html.unescape(japanese)))
    if errors:
        return "KaTeX: " + "; ".join(sorted(set(errors.values())))[:200]
    return None


def _paragraph_problem(block, answer):
    """Why a merged paragraph without mathematics cannot be stored, or None."""
    english, japanese = answer.get("html", ""), answer.get("html_ja", "")
    if not english.strip() or not japanese.strip():
        return "empty html or html_ja"
    if FORMULA.search(html.unescape(english)):
        return "a paragraph with a formula must be answered with is_math"
    try:
        assert_same_html_structure(english, japanese)
    except ValueError as error:
        return str(error)
    probe = dict(block, html=english)
    if Counter(NORMATIVE.findall(japanese)) != Counter(NORMATIVE.findall(source_text(probe))):
        return "requirement keywords differ between html and html_ja"
    return None


def _inner(value):
    """A paragraph block stores its text without the enclosing <p>."""
    match = re.fullmatch(r"\s*<p>(.*)</p>\s*", value, re.S)
    return match.group(1) if match and "<p>" not in match.group(1) else value


def apply(key, work):
    document = read_json(_path(key))
    batches, skipped = _results(work, "restore")
    answers = {answer["id"]: answer for _, result in batches for answer in result}
    by_id = {block["id"]: block for block in document["contents"]}
    # A table whose duplicate fragments are hidden must stay a table, and the
    # hidden fragments stay as they are.
    pinned = {block["id"] for block in document["contents"] if block.get("duplicate_artifact_of")}
    pinned |= {block["duplicate_artifact_of"] for block in document["contents"]
               if block.get("duplicate_artifact_of")}
    # Blocks already shown through a KaTeX group keep that representation.
    pinned |= {member for group in document.get("math_groups", [])
               for member in group.get("members", [])}
    answers = {identifier: answer for identifier, answer in answers.items()
               if identifier not in pinned and answer.get("merged_into") not in pinned}
    merged = {}
    for answer in answers.values():
        target = answer.get("merged_into")
        if target:
            if target not in answers or not (answers[target].get("is_math") or
                                             answers[target].get("is_paragraph")):
                raise ValueError("%s merges into %s, which is not a restored block" % (
                    answer["id"], target))
            merged.setdefault(target, []).append(answer["id"])
    preservation = document.get("math_preservation") or {
        "version": VERSION, "source_sha256": document["source_sha256"],
        "storage_format": "semantic_inline_katex", "coordinate_layout_region_count": 0,
        "mode": "katex_inline", "resolution_dpi": DPI, "crop_count": 0,
        "original_record_count": len(document["contents"]),
        "regions": [], "equation_regions": [], "empty_artifact_ids": [], "original_blocks": []}
    used = [int(match.group(1)) for block in document["contents"]
            if (match := re.search(r"-math-(\d+)$", block["id"]))]
    counter = max(used, default=0)
    paragraph_counter = max((int(match.group(1)) for block in document["contents"]
                             if (match := re.search(r"-para-(\d+)$", block["id"]))), default=0)
    rejected = []
    for identifier, answer in answers.items():
        if answer.get("is_math") and identifier in by_id:
            problem = _problem(by_id[identifier], answer)
            if problem:
                rejected.append((identifier, problem))
        elif answer.get("is_paragraph") and identifier in by_id and merged.get(identifier):
            problem = _paragraph_problem(by_id[identifier], answer)
            if problem:
                rejected.append((identifier, problem))
    refused = {identifier for identifier, _ in rejected}
    counts, contents = Counter(), []
    for block in document["contents"]:
        answer = answers.get(block["id"])
        if answer is None:
            counts["untouched"] += 1
            contents.append(block)
            continue
        target = answer.get("merged_into")
        if target and target not in refused:
            preservation["original_blocks"].append(block)
            counts["merged"] += 1
            continue
        # A refused restoration keeps its own block and the blocks merged into it.
        if target or block["id"] in refused:
            counts["rejected"] += 1
            contents.append(block)
            continue
        if answer.get("is_paragraph") and not answer.get("is_math") and merged.get(block["id"]):
            # Lines of one paragraph without mathematics: one ordinary block.
            paragraph_counter += 1
            members = [block] + [by_id[other] for other in merged[block["id"]]]
            joined = dict(block)
            for field in ("translation_check", "translation_fix_rounds", "extraction_check"):
                joined.pop(field, None)
            joined.update({
                "id": "pdf-p%04d-para-%03d" % (block["source_page"], paragraph_counter),
                "html": _inner(answer["html"]), "html_ja": _inner(answer["html_ja"]),
                "status": "draft", "extraction_status": "needs_review",
                "source_refs": [ref for member in members for ref in member["source_refs"]],
                "replaces": [member["id"] for member in members],
                "merged_source_hashes": {member["id"]: member["source_hash"] for member in members},
                "paragraph_merge": {"method": "lines_of_one_paragraph"},
            })
            joined["source_hash"] = _source_hash(joined["kind"], joined["html"])
            if answer.get("notes"):
                joined["paragraph_merge"]["restorer_notes"] = answer["notes"]
            preservation["original_blocks"] += members
            contents.append(joined)
            counts["paragraphs_merged"] += 1
            continue
        if not answer.get("is_math"):
            counts["not_math"] += 1
            contents.append(block)
            continue
        counter += 1
        members = [block] + [by_id[other] for other in merged.get(block["id"], [])]
        restored = {
            "id": "pdf-p%04d-math-%03d" % (block["source_page"], counter),
            "kind": "math",
            "html": answer["html"],
            "html_ja": answer["html_ja"],
            "status": "draft",
            # The display has not been compared with the original yet.
            "extraction_status": "needs_review",
            "source_page": block["source_page"],
            "source_refs": [ref for member in members for ref in member["source_refs"]],
            "source_hash": _source_hash("math", answer["html"]),
            "math_mode": "latex",
            "math_translation_pending": False,
            "math_source_hashes": {member["id"]: member["source_hash"] for member in members},
            "replaces": [member["id"] for member in members],
            "math_reconstruction": {"method": "editorial_structure",
                                    "replaced_kind": block["kind"]},
        }
        if answer.get("notes"):
            restored["math_reconstruction"]["restorer_notes"] = answer["notes"]
        preservation["original_blocks"].append(block)
        preservation["equation_regions"].append({
            "id": restored["id"], "page": block["source_page"],
            "bbox": block["source_refs"][0]["bbox"], "mode": "latex",
            "replaces": restored["replaces"]})
        contents.append(restored)
        counts["restored"] += 1
    document["contents"] = contents
    if preservation["original_blocks"]:
        preservation["equation_region_count"] = len(preservation["equation_regions"])
        preservation["replaced_block_count"] = len(preservation["original_blocks"])
        document["math_preservation"] = preservation
    audit_translations(document)
    write_json(_path(key), document)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())))
    for identifier, problem in rejected:
        print("REJECTED", identifier, problem)
    for line in skipped:
        print("SKIPPED", line)


def _screenshot(page_path, image_path, height):
    """Headless Chrome writes the image but may not exit; stop it once it has."""
    profile = page_path.parent / "chrome-profile"
    process = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--user-data-dir=" + str(profile), "--window-size=760,%d" % height,
         "--screenshot=" + str(image_path), page_path.as_uri()],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 40
    while time.time() < deadline and not (image_path.exists() and image_path.stat().st_size):
        time.sleep(0.3)
    time.sleep(0.5)
    process.kill()
    process.wait()
    if not image_path.exists():
        raise RuntimeError("Chrome did not write " + str(image_path))


# (pattern, replacement) pairs tried in order; a None replacement shifts the
# captured letter or digit to a different one.
PLANTS = [
    (r"_\{i-1\}", "_{i+1}"), (r"_\{n-1\}", "_{n+1}"), (r"\\oplus", "\\parallel"),
    (r"\\le\b", "\\ge"), (r"\\ge\b", "\\le"), (r"\\lceil", "\\lfloor"),
    (r"\^\{?([a-zA-Z])\}?", None), (r"_\{?([a-zA-Z0-9])\}?", None), (r"(\d)", None),
    # Last resort for formulas with no index or digit: a lone variable letter.
    (r"(?<![\\a-zA-Z])([a-zA-Z])(?![a-zA-Z])", None),
]


PROSE_PLANTS = [
    (r" is not ", " is "), (r" are not ", " are "), (r" cannot ", " can "),
    (r" before ", " after "), (r" after ", " before "), (r" private ", " public "),
    (r" public ", " private "), (r" either ", " both "), (r" all ", " some "),
    (r" at least ", " at most "), (r" more than ", " less than "), (r" static ", " ephemeral "),
    (r" ephemeral ", " static "), (r" and ", " or "), (r" or ", " and "),
    (r" required ", " permitted "), (r" first ", " second "), (r" the ", " each "),
]


def _planted(source_html):
    """A copy of the block with one wrong symbol, or None if nothing suits."""
    formulas = list(FORMULA.finditer(source_html))
    for pattern, replacement in PLANTS:
        for formula in formulas:
            text = formula.group(0)
            match = re.search(pattern, text)
            if not match:
                continue
            if replacement is None:
                old = match.group(1)
                new = (str((int(old) + 3) % 10) if old.isdigit()
                       else chr((ord(old.lower()) - 97 + 1) % 26 + 97))
                changed = text[:match.start(1)] + new + text[match.end(1):]
            else:
                changed = text[:match.start()] + replacement + text[match.end():]
            return source_html[:formula.start()] + changed + source_html[formula.end():]
    # Prose without a formula: change one word so that the sentence still reads
    # naturally but no longer says what the original says.
    for pattern, replacement in PROSE_PLANTS:
        for match in re.finditer(pattern, source_html):
            inside_formula = any(f.start() <= match.start() < f.end() for f in formulas)
            inside_tag = source_html.rfind("<", 0, match.start()) > source_html.rfind(">", 0, match.start())
            if match.start() > 25 and not inside_formula and not inside_tag:
                return source_html[:match.start()] + replacement + source_html[match.end():]
    return None


PAGE = """<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="{css}">
<body style="font:17px serif;width:700px;padding:10px 14px;margin:0">
<div class="en">{en}</div><hr><div class="ja">{ja}</div>
<script src="{js}"></script><script src="{auto}"></script><script>
renderMathInElement(document.body, {{delimiters: [
  {{left: "\\\\(", right: "\\\\)", display: false}},
  {{left: "\\\\[", right: "\\\\]", display: true}}], throwOnError: false, trust: false}});
</script>"""


def render(key, work, pdf_dir):
    document = read_json(_path(key))
    originals = {block["id"]: block for block in
                 document.get("math_preservation", {}).get("original_blocks", [])}
    work.mkdir(parents=True, exist_ok=True)
    page_images = {}

    def original_crop(source):
        """The crop written by export, rebuilt from the PDF if it is gone."""
        path = work / (source + ".png")
        if not path.exists() and source in originals:
            import pypdfium2

            block = originals[source]
            number = block["source_page"]
            if number not in page_images:
                pdf = pypdfium2.PdfDocument(str(Path(pdf_dir) / (key + ".pdf")))
                page_images[number] = pdf[number - 1].render(
                    scale=DPI / 72).to_pil().convert("RGB")
            image, scale = page_images[number], DPI / 72
            _, top, _, bottom = _span(block)
            image.crop((0, max(0, (top - 10) * scale), image.width,
                        min(image.height, (bottom + 10) * scale))).save(path)
        return str(path)

    def shoot(name, english, japanese):
        page_path = work / (name + ".html")
        image_path = work / (name + ".render.png")
        page_path.write_text(PAGE.format(
            css=(KATEX / "katex.min.css").as_uri(), js=(KATEX / "katex.min.js").as_uri(),
            auto=(KATEX / "auto-render.min.js").as_uri(), en=english, ja=japanese),
            encoding="utf-8")
        image_path.unlink(missing_ok=True)
        length = len(TAGLESS.sub("", english)) + len(TAGLESS.sub("", japanese))
        _screenshot(page_path, image_path, min(2400, 220 + length // 2))
        return str(image_path)

    items = []
    for block in document["contents"]:
        checked = (_recon(block) or {}).get("source_check", {})
        if (not (block["kind"] == "math" or block.get("paragraph_merge")) or
                checked.get("rendered_source_hash") == block["source_hash"]):
            continue
        items.append({
            "block": block["id"], "page": block["source_page"],
            "source_hash": block["source_hash"], "html": block["html"],
            "html_ja": block["html_ja"],
            "original": [original_crop(source) for source in block["replaces"]],
            "extracted_before": [originals[source]["html"] for source in block["replaces"]
                                 if source in originals]})
    # Verdicts from an earlier render would otherwise be matched to the new
    # batches, which reuse the same file names and ids.
    for pattern in ("check.*.batch.json", "check.*.key.json", "check.*.result.json"):
        for path in work.glob(pattern):
            path.unlink()
    planted_total = batch_count = 0
    for index in range(0, len(items), CHECK_BATCH):
        group = items[index:index + CHECK_BATCH]
        # Every batch gets planted errors so that a reviewer who waves
        # everything through is detected.
        planted = []
        for item in group[::max(1, len(group) // 4)]:
            wrong = _planted(item["html"])
            # The translation of a plain paragraph has nothing to plant in; the
            # changed English then also disagrees with the Japanese.
            wrong_ja = _planted(item["html_ja"]) or (
                item["html_ja"] if not FORMULA.search(item["html"]) else None)
            if wrong and wrong_ja and len(planted) < 4:
                planted.append(dict(item, html=wrong, html_ja=wrong_ja, planted=True))
        # Nothing the reviewer sees may tell a planted copy from a real block,
        # so order, ids and file names are all independent of which is which.
        mixed = sorted(group + planted, key=lambda item: hashlib.sha256(
            (item["block"] + item["html"]).encode("utf-8")).hexdigest())
        batch_count += 1
        stem = "check.%03d" % batch_count
        key_map, blocks = {}, []
        for number, item in enumerate(mixed, 1):
            identifier = "c%02d" % number
            key_map[identifier] = {"block": item["block"], "planted": bool(item.get("planted")),
                                   "source_hash": item["source_hash"]}
            blocks.append({
                "id": identifier, "page": item["page"], "html": item["html"],
                "html_ja": item["html_ja"], "original": item["original"],
                "extracted_before": item["extracted_before"],
                "render": shoot("%s.%s" % (stem, identifier), item["html"], item["html_ja"])})
        planted_total += len(planted)
        write_json(work / (stem + ".batch.json"), {
            "document": document["number"], "dpi": DPI, "blocks": blocks})
        write_json(work / (stem + ".key.json"), key_map)
    print("Rendered %d restored blocks in %d batches (%d planted errors)" % (
        len(items), batch_count, planted_total))


def check(key, work):
    document = read_json(_path(key))
    blocks = {block["id"]: block for block in document["contents"]}
    batches, skipped = _results(work, "check")
    counts = Counter()
    for batch_path, answers in batches:
        key_map = read_json(batch_path.with_name(
            batch_path.name.replace(".batch.json", ".key.json")))
        verdicts = {answer["id"]: answer for answer in answers}
        planted = [identifier for identifier, entry in key_map.items() if entry["planted"]]
        missed = [identifier for identifier in planted
                  if verdicts[identifier]["verdict"] == "ok"]
        counts["planted"] += len(planted)
        counts["planted_missed"] += len(missed)
        for identifier, answer in verdicts.items():
            entry = key_map[identifier]
            if entry["planted"]:
                continue
            block = blocks.get(entry["block"])
            if block is None or entry["source_hash"] != block["source_hash"]:
                counts["changed_since_render"] += 1
                continue
            passed = answer["verdict"] == "ok"
            if passed and missed:
                # This reviewer let a planted error through; do not rely on its "ok".
                counts["ok_from_unreliable_batch"] += 1
                continue
            _recon(block)["source_check"] = {
                "method": "original_pdf_browser_comparison", "page": block["source_page"],
                "dpi": DPI, "browser_status": "passed" if passed else "failed",
                "rendered_source_hash": block["source_hash"],
                "observations": answer.get("observations", "")}
            block["extraction_status"] = "verified" if passed else "needs_review"
            if block.get("paragraph_merge") and passed:
                block["extraction_check"] = "visual"
            counts["verified" if passed else "failed"] += 1
    audit_translations(document)
    write_json(_path(key), document)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())))
    for line in skipped:
        print("SKIPPED", line)


def revise_export(key, work, pdf_dir):
    import pypdfium2

    document = read_json(_path(key))
    originals = {block["id"]: block for block in
                 document.get("math_preservation", {}).get("original_blocks", [])}
    work.mkdir(parents=True, exist_ok=True)
    pdf, page_images, items = None, {}, []
    scale = DPI / 72
    for block in document["contents"]:
        checked = block.get("math_reconstruction", {}).get("source_check", {})
        if block["kind"] != "math" or checked.get("browser_status") != "failed":
            continue
        images = []
        for source in block["replaces"]:
            path = work / (source + ".png")
            if not path.exists() and source in originals:
                if pdf is None:
                    pdf = pypdfium2.PdfDocument(str(Path(pdf_dir) / (key + ".pdf")))
                number = originals[source]["source_page"]
                if number not in page_images:
                    page_images[number] = pdf[number - 1].render(
                        scale=scale).to_pil().convert("RGB")
                image = page_images[number]
                _, top, _, bottom = _span(originals[source])
                image.crop((0, max(0, (top - 10) * scale), image.width,
                            min(image.height, (bottom + 10) * scale))).save(path)
            images.append(str(path))
        items.append({"id": block["id"], "page": block["source_page"],
                      "html": block["html"], "html_ja": block["html_ja"],
                      "images": images, "difference_found": checked.get("observations", "")})
    write_json(work / "revise.batch.json", {"document": document["number"], "blocks": items})
    print("Exported %d blocks to revise" % len(items))


def revise_apply(key, work):
    document = read_json(_path(key))
    batch = {item["id"] for item in read_json(work / "revise.batch.json")["blocks"]}
    answers = {answer["id"]: answer for answer in read_json(work / "revise.result.json")}
    if set(answers) != batch:
        raise ValueError("Answers do not cover the batch exactly")
    counts = Counter()
    for block in document["contents"]:
        answer = answers.get(block["id"])
        if answer is None:
            continue
        problem = _problem(block, answer)
        if problem:
            counts["rejected"] += 1
            print("REJECTED", block["id"], problem)
            continue
        if answer["html"] == block["html"] and answer["html_ja"] == block["html_ja"]:
            counts["unchanged"] += 1
            continue
        block["html"], block["html_ja"] = answer["html"], answer["html_ja"]
        block["source_hash"] = _source_hash("math", answer["html"])
        # A corrected block is unchecked and its translation unreviewed again.
        block["extraction_status"], block["status"] = "needs_review", "draft"
        block.pop("translation_check", None)
        block.pop("translation_fix_rounds", None)
        reconstruction = block["math_reconstruction"]
        reconstruction["revised_after"] = reconstruction.pop("source_check")["observations"]
        if answer.get("notes"):
            reconstruction["restorer_notes"] = answer["notes"]
        counts["revised"] += 1
    audit_translations(document)
    write_json(_path(key), document)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())) or "nothing applied")


FIGURE_DPI = 216
CAPTION = re.compile(r"(Figure|Fig\.?|Table)\s*[A-Z]?\.?\d+", re.I)


def _figure_regions(document, pdf):
    """Clusters of drawn objects that enclose at least two extracted blocks."""
    import pypdfium2.raw as pdfium_c
    import verify_extraction as verifier

    by_page = {}
    for block in document["contents"]:
        if block["kind"] not in {"source_excerpt", "footnote"} and len(block["source_refs"]) == 1:
            by_page.setdefault(block["source_page"], []).append(block)
    regions = []
    for number in sorted(by_page):
        if number <= 3:
            continue  # cover and title pages carry logos and ornaments, not figures
        page = verifier.PageData(pdf[number - 1], pdfium_c)
        boxes = [[g["x0"], g["top"], g["x1"], g["bottom"]] for g in page.graphics
                 # Skip rules in the page margins and hairlines across the page.
                 if g["top"] > 60 and g["bottom"] < page.height - 50 and
                 g["x0"] > 40 and g["x1"] < page.width - 40 and
                 not (g["height"] < 3 and g["width"] > page.width * 0.6) and
                 not (g["width"] < 3 and g["height"] > page.height * 0.5)]
        def near(a, b):
            if (a[0] - 14 <= b[2] and b[0] - 14 <= a[2] and
                    a[1] - 14 <= b[3] and b[1] - 14 <= a[3]):
                return True
            # Columns of one diagram stand side by side with a wider gap.
            overlap = min(a[3], b[3]) - max(a[1], b[1])
            gap = max(a[0], b[0]) - min(a[2], b[2])
            return overlap >= 0.5 * min(a[3] - a[1], b[3] - b[1]) > 15 and gap <= 90

        clusters = [box + [1] for box in boxes]
        changed = True
        while changed:
            changed = False
            for first in clusters:
                for second in clusters:
                    if first is not second and near(first, second):
                        clusters.remove(first)
                        clusters.remove(second)
                        clusters.append([min(first[0], second[0]), min(first[1], second[1]),
                                         max(first[2], second[2]), max(first[3], second[3]),
                                         first[4] + second[4]])
                        changed = True
                        break
                if changed:
                    break
        for x0, top, x1, bottom, objects in clusters:
            if objects < 4 or bottom - top < 45 or x1 - x0 < 90:
                continue
            if bottom - top > page.height * 0.75 and x1 - x0 > page.width * 0.7:
                continue  # a frame around the page, not a figure
            members = [block for block in by_page[number]
                       if x0 - 4 <= (block["source_refs"][0]["bbox"][0] +
                                     block["source_refs"][0]["bbox"][2]) / 2 <= x1 + 4 and
                       top - 4 <= (block["source_refs"][0]["bbox"][1] +
                                   block["source_refs"][0]["bbox"][3]) / 2 <= bottom + 4]
            # A caption or a body paragraph that the drawing's frame happens to
            # enclose stays a text block; only short labels belong to the figure.
            members = [block for block in members
                       if block["kind"] != "heading" and
                       len(TAGLESS.sub("", block["html"])) <= 150 and
                       not CAPTION.match(TAGLESS.sub("", block["html"]).strip())]
            if len(members) < 2:
                continue
            # Grow to the text that belongs to the drawing (labels may overhang).
            for block in members:
                bx0, btop, bx1, bbottom = block["source_refs"][0]["bbox"]
                x0, top, x1, bottom = min(x0, bx0), min(top, btop), max(x1, bx1), max(bottom, bbottom)
            # Rotated labels beside the drawing are neither blocks nor graphics.
            for char in page.chars:
                if (not char["upright"] and top <= (char["top"] + char["bottom"]) / 2 <= bottom
                        and x0 - 40 <= (char["x0"] + char["x1"]) / 2 <= x1 + 40):
                    x0, x1 = min(x0, char["x0"]), max(x1, char["x1"])
            regions.append({"page": number, "members": members,
                            "bbox": [round(max(0, x0 - 4), 1), round(max(0, top - 4), 1),
                                     round(min(page.width, x1 + 4), 1),
                                     round(min(page.height, bottom + 4), 1)]})
    return regions


def figures_export(key, work, pdf_dir):
    import pypdfium2

    document = read_json(_path(key))
    pdf = pypdfium2.PdfDocument(str(Path(pdf_dir) / (key + ".pdf")))
    work.mkdir(parents=True, exist_ok=True)
    items = []
    for index, region in enumerate(_figure_regions(document, pdf), 1):
        scale = 150 / 72
        image = pdf[region["page"] - 1].render(scale=scale).to_pil().convert("RGB")
        x0, top, x1, bottom = region["bbox"]
        # Show some surroundings so that a caption above or below is visible.
        crop = image.crop((0, max(0, (top - 40) * scale), image.width,
                           min(image.height, (bottom + 40) * scale)))
        name = "figure.%03d.png" % index
        crop.save(work / name)
        items.append({"id": "f%03d" % index, "page": region["page"], "bbox": region["bbox"],
                      "image": str(work / name),
                      "blocks": [{"id": block["id"], "kind": block["kind"],
                                  "text": TAGLESS.sub(" ", block["html"])[:160]}
                                 for block in region["members"]]})
    write_json(work / "figures.batch.json", {"document": document["number"], "regions": items})
    print("Exported %d candidate figure regions (%d blocks)" % (
        len(items), sum(len(item["blocks"]) for item in items)))


def figures_apply(key, work, pdf_dir):
    import pypdfium2

    document = read_json(_path(key))
    slug = key[len("sp800-"):]
    asset_dir, prefix = ROOT / "html" / "assets" / slug, "assets/" + slug
    pdf = pypdfium2.PdfDocument(str(Path(pdf_dir) / (key + ".pdf")))
    batch = {item["id"]: item for item in read_json(work / "figures.batch.json")["regions"]}
    answers = {answer["id"]: answer for answer in read_json(work / "figures.result.json")}
    if set(answers) != set(batch):
        raise ValueError("Answers do not cover the regions exactly")
    preservation = document.get("math_preservation") or {
        "version": VERSION, "source_sha256": document["source_sha256"],
        "storage_format": "semantic_inline_katex", "coordinate_layout_region_count": 0,
        "mode": "katex_inline", "resolution_dpi": FIGURE_DPI, "crop_count": 0,
        "original_record_count": len(document["contents"]),
        "regions": [], "equation_regions": [], "empty_artifact_ids": [], "original_blocks": []}
    used = [int(match.group(1)) for block in document["contents"]
            if (match := re.search(r"-preserved-(\d+)$", block["id"]))]
    counter = max(used, default=0)
    present = {block["id"] for block in document["contents"]}
    replaced, inserts, counts = {}, {}, Counter()
    for identifier, item in batch.items():
        answer = answers[identifier]
        members = [entry["id"] for entry in item["blocks"]]
        if not answer.get("is_figure"):
            counts["not_figure"] += 1
            continue
        if not all(member in present for member in members):
            counts["changed_since_export"] += 1
            continue
        counter += 1
        number = item["page"]
        x0, top, x1, bottom = item["bbox"]
        scale = FIGURE_DPI / 72
        image = pdf[number - 1].render(scale=scale).to_pil().convert("RGB").crop(
            (x0 * scale, top * scale, x1 * scale, bottom * scale))
        name = "p%04d-preserved-%03d.png" % (number, counter)
        asset_dir.mkdir(parents=True, exist_ok=True)
        image.save(asset_dir / name)
        image_hash = hashlib.sha256((asset_dir / name).read_bytes()).hexdigest()
        label = answer.get("label_ja") or "図"
        source_html = '<img src="%s/%s" alt="%s" width="%d" height="%d" loading="lazy">' % (
            prefix, name, html.escape("PDF p.%d：%s（原本画像）" % (number, label), quote=True),
            round((x1 - x0) * 96 / 72), round((bottom - top) * 96 / 72))
        block_id = "pdf-p%04d-preserved-%03d" % (number, counter)
        inserts[members[0]] = {
            "id": block_id, "kind": "source_excerpt", "html": source_html, "html_ja": "",
            "status": "source_only", "extraction_status": "verified", "source_page": number,
            "source_refs": [{"page": number, "bbox": item["bbox"]}],
            "source_hash": hashlib.sha256(("source_excerpt\n" + source_html + "\n" + image_hash)
                                          .encode("utf-8")).hexdigest()[:16],
            "source_image_hash": image_hash, "source_excerpt_type": "figure",
            "source_label": label, "source_image": "%s/%s" % (prefix, name), "replaces": members}
        for member in members:
            replaced[member] = block_id
        preservation["regions"].append({
            "id": block_id, "page": number, "bbox": item["bbox"], "type": "figure",
            "label": label, "asset": "%s/%s" % (prefix, name), "replaces": members})
        counts["figures"] += 1
    contents = []
    for block in document["contents"]:
        if block["id"] in inserts:
            contents.append(inserts[block["id"]])
        if block["id"] in replaced:
            preservation["original_blocks"].append(block)
            counts["blocks_replaced"] += 1
        else:
            contents.append(block)
    document["contents"] = contents
    if preservation["original_blocks"]:
        preservation["crop_count"] = len(preservation["regions"])
        preservation["equation_region_count"] = len(preservation["equation_regions"])
        preservation["replaced_block_count"] = len(preservation["original_blocks"])
        document["math_preservation"] = preservation
    audit_translations(document)
    write_json(_path(key), document)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())) or "nothing applied")


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("command", choices=["export", "apply", "render", "check",
                                         "revise-export", "revise-apply",
                                         "figures-export", "figures-apply"])
    cli.add_argument("key", help="document key such as sp800-38b")
    cli.add_argument("work", type=Path, help="working directory for batches and images")
    cli.add_argument("--pdf-dir", type=Path, default=ROOT / "data")
    cli.add_argument("--pages", help="export: only these pages, e.g. 9-18,25")
    cli.add_argument("--ids", type=Path,
                     help="export: only the block ids in this JSON list (for retries)")
    cli.add_argument("--fragments", action="store_true",
                     help="export: the runs of blocks that look like lines of one paragraph")
    cli.add_argument("--every-block", action="store_true",
                     help="export: offer every text block, not only likely mathematics")
    args = cli.parse_args()
    if args.command == "export":
        export(args.key, args.work, args.pdf_dir, _page_set(args.pages), args.every_block,
               set(read_json(args.ids)) if args.ids else (), args.fragments)
    elif args.command == "revise-export":
        revise_export(args.key, args.work, args.pdf_dir)
    elif args.command == "revise-apply":
        revise_apply(args.key, args.work)
    elif args.command == "figures-export":
        figures_export(args.key, args.work, args.pdf_dir)
    elif args.command == "figures-apply":
        figures_apply(args.key, args.work, args.pdf_dir)
    else:
        if args.command == "render":
            render(args.key, args.work, args.pdf_dir)
        else:
            {"apply": apply, "check": check}[args.command](args.key, args.work)


if __name__ == "__main__":
    main()
