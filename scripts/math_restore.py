"""Restore mathematics in extracted PDF blocks as structural LaTeX.

The stored format is the one used for SP 800-22r1: a ``kind: math`` block
whose ``html`` and ``html_ja`` carry KaTeX LaTeX in ``\\(...\\)`` / ``\\[...\\]``,
with the replaced extraction blocks kept in ``math_preservation``. Rules for
the LaTeX itself are in skills/nist-document-extraction/SKILL.md.

    python scripts/math_restore.py export  KEY WORK_DIR --pdf-dir DIR [--pages 9-18]
    python scripts/math_restore.py apply   KEY WORK_DIR
    python scripts/math_restore.py render  KEY WORK_DIR
    python scripts/math_restore.py check   KEY WORK_DIR

``export`` writes ``restore.batch.json`` and a 300 dpi crop of each candidate
block: blocks with raised, lowered or mixed-size glyphs or mathematical symbols,
or, with ``--pages``, every remaining text block on those pages (variables set
in italics on the baseline are not detectable from glyph geometry). A restorer answers with ``restore.result.json``: a list of
``{"id", "is_math", "html", "html_ja", "notes"}``.
``apply`` validates the answers and replaces the blocks (``needs_review``).
``render`` screenshots each restored block as KaTeX displays it and writes
``check.batch.json``; a reviewer compares it with the original crop and answers
with ``check.result.json``: a list of ``{"id", "verdict", "observations"}``.
``check`` marks blocks whose display matches the original as ``verified``.
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
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
KATEX = ROOT / "static" / "vendor" / "katex"
FORMULA = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.S)
MATH_REASONS = {"math_symbol", "raised_or_lowered_text", "mixed_size", "bad_character"}


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


def export(key, work, pdf_dir, all_pages=()):
    import pypdfium2
    import pypdfium2.raw as pdfium_c
    import verify_extraction as verifier

    document = read_json(_path(key))
    pdf_path = Path(pdf_dir) / (key + ".pdf")
    if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != document["source_sha256"]:
        raise ValueError("Local PDF does not match source_sha256")
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    work.mkdir(parents=True, exist_ok=True)
    pages, images, items = {}, {}, []
    for block in document["contents"]:
        if (block["kind"] in {"figure", "math", "source_excerpt", "code"} or
                len(block["source_refs"]) != 1 or block.get("duplicate_artifact_of")):
            continue
        number = block["source_page"]
        if number not in pages:
            pages[number] = verifier.PageData(pdf[number - 1], pdfium_c)
        page = pages[number]
        x0, top, x1, bottom = block["source_refs"][0]["bbox"]
        text = verifier._block_text(block)
        reasons, _ = verifier._layout_reasons(block, page, text)
        symbol_font = any(
            ("Symbol" in char["font"] or "Math" in char["font"]) and char["text"] not in "•·"
            for char in page.chars
            if x0 - 1 <= (char["x0"] + char["x1"]) / 2 <= x1 + 1 and
            top - 1 <= (char["top"] + char["bottom"]) / 2 <= bottom + 1)
        if not (MATH_REASONS & set(reasons) or symbol_font or number in all_pages):
            continue
        if number not in images:
            images[number] = page.page.render(scale=DPI / 72).to_pil().convert("RGB")
        scale = DPI / 72
        image = images[number]
        # Keep the full text width and a little context above and below.
        crop = image.crop((0, max(0, (top - 10) * scale),
                           image.width, min(image.height, (bottom + 10) * scale)))
        name = block["id"] + ".png"
        crop.save(work / name)
        items.append({"id": block["id"], "kind": block["kind"], "page": number,
                      "ordinal": block.get("ordinal"), "en": block["html"],
                      "ja": block.get("html_ja", ""), "image": str(work / name)})
    write_json(work / "restore.batch.json", {
        "document": document["number"], "title": document.get("subtitle", ""),
        "dpi": DPI, "blocks": items})
    print("Exported %d candidate blocks on %d pages to %s" % (len(items), len(images), work))


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


def apply(key, work):
    document = read_json(_path(key))
    answers = {answer["id"]: answer for answer in read_json(work / "restore.result.json")}
    expected = {item["id"] for item in read_json(work / "restore.batch.json")["blocks"]}
    if set(answers) != expected:
        raise ValueError("Answers do not cover the batch exactly")
    preservation = document.get("math_preservation") or {
        "version": VERSION, "source_sha256": document["source_sha256"],
        "storage_format": "semantic_inline_katex", "coordinate_layout_region_count": 0,
        "mode": "katex_inline", "resolution_dpi": DPI, "crop_count": 0,
        "original_record_count": len(document["contents"]),
        "regions": [], "equation_regions": [], "empty_artifact_ids": [], "original_blocks": []}
    used = [int(match.group(1)) for block in document["contents"]
            if (match := re.search(r"-math-(\d+)$", block["id"]))]
    counter = max(used, default=0)
    counts, rejected, contents = Counter(), [], []
    for block in document["contents"]:
        answer = answers.get(block["id"])
        if answer is None or not answer.get("is_math"):
            counts["not_math" if answer else "untouched"] += 1
            contents.append(block)
            continue
        problem = _problem(block, answer)
        if problem:
            rejected.append((block["id"], problem))
            contents.append(block)
            continue
        counter += 1
        restored = {
            "id": "pdf-p%04d-math-%03d" % (block["source_page"], counter),
            "kind": "math",
            "html": answer["html"],
            "html_ja": answer["html_ja"],
            "status": "draft",
            # The display has not been compared with the original yet.
            "extraction_status": "needs_review",
            "source_page": block["source_page"],
            "source_refs": block["source_refs"],
            "source_hash": _source_hash("math", answer["html"]),
            "math_mode": "latex",
            "math_translation_pending": False,
            "math_source_hashes": {block["id"]: block["source_hash"]},
            "replaces": [block["id"]],
            "math_reconstruction": {"method": "editorial_structure",
                                    "replaced_kind": block["kind"]},
        }
        if answer.get("notes"):
            restored["math_reconstruction"]["restorer_notes"] = answer["notes"]
        preservation["original_blocks"].append(block)
        preservation["equation_regions"].append({
            "id": restored["id"], "page": block["source_page"],
            "bbox": block["source_refs"][0]["bbox"], "mode": "latex",
            "replaces": [block["id"]]})
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


def render(key, work):
    document = read_json(_path(key))
    originals = {block["id"]: block for block in
                 document.get("math_preservation", {}).get("original_blocks", [])}
    template = (
        '<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="%(css)s">'
        '<body style="font:17px serif;width:700px;padding:10px 14px;margin:0">'
        '<div class="en">%(en)s</div><hr><div class="ja">%(ja)s</div>'
        '<script src="%(js)s"></script><script src="%(auto)s"></script><script>'
        'renderMathInElement(document.body,{delimiters:[{left:"\\\\(",right:"\\\\)",display:false},'
        '{left:"\\\\[",right:"\\\\]",display:true}],throwOnError:true,trust:false});</script>')
    items = []
    for block in document["contents"]:
        check = block.get("math_reconstruction", {}).get("source_check", {})
        if (block["kind"] != "math" or
                check.get("rendered_source_hash") == block["source_hash"]):
            continue
        page_path = work / (block["id"] + ".html")
        image_path = work / (block["id"] + ".render.png")
        page_path.write_text(template % {
            "css": (KATEX / "katex.min.css").as_uri(), "js": (KATEX / "katex.min.js").as_uri(),
            "auto": (KATEX / "auto-render.min.js").as_uri(),
            "en": block["html"], "ja": block["html_ja"]}, encoding="utf-8")
        image_path.unlink(missing_ok=True)
        length = len(TAGLESS.sub("", block["html"])) + len(TAGLESS.sub("", block["html_ja"]))
        _screenshot(page_path, image_path, min(2400, 220 + length // 2))
        items.append({"id": block["id"], "page": block["source_page"],
                      "source_hash": block["source_hash"], "html": block["html"],
                      "html_ja": block["html_ja"], "render": str(image_path),
                      "original": [str(work / (source + ".png")) for source in block["replaces"]],
                      "extracted_before": [originals[source]["html"] for source in block["replaces"]
                                           if source in originals]})
    write_json(work / "check.batch.json", {
        "document": document["number"], "dpi": DPI, "blocks": items})
    print("Rendered %d restored blocks" % len(items))


TAGLESS = re.compile(r"<[^>]+>")


def check(key, work):
    document = read_json(_path(key))
    batch = {item["id"]: item for item in read_json(work / "check.batch.json")["blocks"]}
    answers = read_json(work / "check.result.json")
    if {answer["id"] for answer in answers} != set(batch):
        raise ValueError("Verdicts do not cover the batch exactly")
    blocks = {block["id"]: block for block in document["contents"]}
    counts = Counter()
    for answer in answers:
        block = blocks[answer["id"]]
        if batch[answer["id"]]["source_hash"] != block["source_hash"]:
            counts["changed_since_render"] += 1
            continue
        passed = answer["verdict"] == "ok"
        block["math_reconstruction"]["source_check"] = {
            "method": "original_pdf_browser_comparison", "page": block["source_page"],
            "dpi": DPI, "browser_status": "passed" if passed else "failed",
            "rendered_source_hash": block["source_hash"],
            "observations": answer.get("observations", "")}
        block["extraction_status"] = "verified" if passed else "needs_review"
        counts["verified" if passed else "failed"] += 1
    audit_translations(document)
    write_json(_path(key), document)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())))


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("command", choices=["export", "apply", "render", "check"])
    cli.add_argument("key", help="document key such as sp800-38b")
    cli.add_argument("work", type=Path, help="working directory for batches and images")
    cli.add_argument("--pdf-dir", type=Path, default=ROOT / "data")
    cli.add_argument("--pages", help="export: also offer every text block on these pages")
    args = cli.parse_args()
    if args.command == "export":
        export(args.key, args.work, args.pdf_dir, _page_set(args.pages))
    else:
        {"apply": apply, "render": render, "check": check}[args.command](args.key, args.work)


if __name__ == "__main__":
    main()
