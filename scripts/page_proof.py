"""Proofread re-extracted pages against the original, page by page.

    python scripts/page_proof.py export KEY DIR [--pages-per-batch 3]
    python scripts/page_proof.py apply KEY DIR

``export`` writes two overlapping images (top and bottom) of every page and batches listing the page's text
blocks in reading order. A checker compares each listing with the image and
writes ``proof.NNN.result.json``. One block per batch carries a planted
error (recorded in ``proof.NNN.key.json``, which the checker must not read);
a batch whose planted error goes unnoticed does not count.

``apply`` marks the blocks of a clean page as verified (``extraction_check:
"visual-page"``), stores corrected text for blocks reported as misread, and
leaves pages with structural problems as ``needs_review``.
"""

import argparse
import copy
import hashlib
import html
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCALE = 2.5
TEXT = {"paragraph", "heading", "list_item", "note", "footnote", "math", "code"}
# A restorer may lay a page out with display formulas ("math": LaTeX inside \\[ \\])
# and algorithms ("code": pseudocode lines kept as printed).


def _record(block):
    """Where the outcome of the page check is kept on a block."""
    if "column_reflow" in block:
        return block["column_reflow"]
    return block.setdefault("page_check", {})


def _state(block):
    return (block.get("column_reflow") or block.get("page_check") or {}).get("page_proof")


# A document with "page_proof_tables": true (mathematical FIPS, whose tables
# the extractor breaks up) has its tables checked and laid out again too.
WITH_TABLES = False


def _text_block(block):
    kinds = TEXT | {"table"} if WITH_TABLES else TEXT
    return (not block.get("page_furniture") and not block.get("duplicate_artifact_of") and
            block["kind"] in kinds and bool(block.get("source_refs")))


def _blocks(document):
    # Members of a hand-built formula group are shown through the group's TeX.
    grouped = {member for group in document.get("math_groups", []) for member in group.get("members", [])}
    return [block for block in document["contents"]
            if _text_block(block) and block.get("extraction_status") == "needs_review" and
            block["id"] not in grouped]


def _plant(text, rng):
    words = text.split(" ")
    spots = [i for i, word in enumerate(words) if re.fullmatch(r"[a-z]{5,}", word)]
    if len(spots) < 4:
        return None
    kind = rng.choice(["drop", "swap", "replace"])
    i = rng.choice(spots[1:-1])
    if kind == "drop":
        del words[i]
    elif kind == "swap" and i + 1 < len(words):
        words[i], words[i + 1] = words[i + 1], words[i]
    else:
        words[i] = rng.choice(["network", "limited", "between", "several", "annual", "public"])
    planted = " ".join(words)
    return planted if planted != text else None


def export(key, folder, per_batch, only_pages=None):
    import pypdfium2
    document = json.loads((ROOT / "data" / (key + "-trans.json")).read_text())
    folder.mkdir(parents=True, exist_ok=True)
    pdf = pypdfium2.PdfDocument(str(ROOT / "data" / (key + ".pdf")))
    pages = {}
    for block in _blocks(document):
        # A block that runs on to a later page is listed on each of its pages.
        for page in sorted({ref["page"] for ref in block["source_refs"]}, reverse=True):
            if page == block["source_page"]:
                pages.setdefault(page, []).append(block)
            else:
                pages.setdefault(page, []).insert(0, block)
    numbers = sorted(page for page, blocks in pages.items() if blocks and
                     (only_pages is None or page in only_pages))
    rng = random.Random(key)
    count = 0
    for start in range(0, len(numbers), per_batch):
        count += 1
        batch, key_data = {"document": key, "pages": []}, {"plants": []}
        chunk = numbers[start:start + per_batch]
        candidates = [(page, index) for page in chunk for index, block in enumerate(pages[page])
                      if len(block["html"]) >= 120 and len(block["source_refs"]) == 1 and
                      _state(block) is None]
        rng.shuffle(candidates)
        planted = None
        for page in chunk:
            images = [folder / ("p%04d-%s.png" % (page, half)) for half in ("top", "bottom")]
            if not all(image.exists() for image in images):
                picture = pdf[page - 1].render(scale=SCALE).to_pil()
                height = picture.height
                picture.crop((0, 0, picture.width, int(height * 0.54))).save(images[0])
                picture.crop((0, int(height * 0.46), picture.width, height)).save(images[1])
            items = []
            for index, block in enumerate(pages[page]):
                text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", block["html"])).split())
                if planted is None and candidates and (page, index) == candidates[0]:
                    changed = _plant(text, rng)
                    if changed:
                        planted = {"page": page, "n": index + 1, "id": block["id"]}
                        text = changed
                    else:
                        candidates.pop(0)
                item = {"n": index + 1, "kind": block["kind"], "text": text}
                if len({ref["page"] for ref in block["source_refs"]}) > 1:
                    if page == block["source_page"]:
                        item["continues_on_page"] = block["source_refs"][-1]["page"]
                    else:
                        item["continued_from_page"] = block["source_page"]
                items.append(item)
            batch["pages"].append({"page": page, "images": [str(image) for image in images], "blocks": items})
            key_data.setdefault("ids", {})[str(page)] = [block["id"] for block in pages[page]]
            key_data.setdefault("hashes", {})[str(page)] = [block["source_hash"] for block in pages[page]]
        key_data["plants"] = [planted] if planted else []
        (folder / ("proof.%03d.batch.json" % count)).write_text(
            json.dumps(batch, ensure_ascii=False, indent=1))
        (folder / ("proof.%03d.key.json" % count)).write_text(json.dumps(key_data, ensure_ascii=False))
    print(key, "pages", len(numbers), "batches", count)


def apply(key, folder):
    path = ROOT / "data" / (key + "-trans.json")
    document = json.loads(path.read_text())
    by_id = {block["id"]: block for block in document["contents"]}
    counts = Counter()
    problems, held, listed, stale = {}, set(), {}, set()
    on_page = Counter()
    for block in document["contents"]:
        if _text_block(block):
            for number in {ref["page"] for ref in block["source_refs"]}:
                on_page[number] += 1
    for result_path in sorted(folder.glob("proof.*.result.json")):
        key_data = json.loads(result_path.with_name(result_path.name.replace("result", "key")).read_text())
        try:
            result = json.loads(result_path.read_text())
        except ValueError:
            counts["unreadable result"] += 1
            continue
        reported = {(page["page"], problem["n"]) for page in result.get("pages", [])
                    for problem in page.get("problems", [])}
        plants = key_data["plants"]
        if any((plant["page"], plant["n"]) not in reported for plant in plants):
            counts["batches missing the planted error"] += 1
            continue
        counts["batches counted"] += 1
        planted = {(plant["page"], plant["n"]) for plant in plants}
        for page in result.get("pages", []):
            ids = key_data["ids"].get(str(page["page"]))
            hashes = key_data["hashes"].get(str(page["page"]))
            if ids is None:
                continue
            found = [p for p in page.get("problems", []) if (page["page"], p["n"]) not in planted]
            # A listing that leaves out blocks verified earlier makes their text look missing.
            partial = len(ids) < on_page.get(page["page"], 0)
            if partial:
                page["missing_text"] = []
            structural = bool(page.get("missing_text")) or any(
                p.get("type") != "text" or not p.get("corrected_text") for p in found)
            for index, identifier in enumerate(ids, 1):
                block = by_id.get(identifier)
                if block is None or block["source_hash"] != hashes[index - 1]:
                    stale.add(identifier)
                    continue
                listed.setdefault(identifier, set()).add(page["page"])
                if structural:
                    held.add(identifier)
            for problem in found:
                if 1 <= problem["n"] <= len(ids):
                    problems.setdefault(ids[problem["n"] - 1], []).append(problem)
            if page.get("missing_text"):
                document.setdefault("column_reflow", {}).setdefault("missing_text", {})[
                    str(page["page"])] = page["missing_text"]
                counts["pages with missing text"] += 1
    counts["changed since export"] = len(stale)
    for identifier, pages in listed.items():
        block = by_id[identifier]
        if identifier in stale or block.get("extraction_status") != "needs_review":
            continue
        found = problems.get(identifier, [])
        note = "; ".join(str(p.get("note", "")) for p in found)
        text_only = found and all(p.get("type") == "text" and p.get("corrected_text") for p in found)
        if not found:
            if identifier in held:
                _record(block)["page_proof"] = "page_has_structural_problems"
                counts["on a page with structural problems"] += 1
            elif pages >= {ref["page"] for ref in block["source_refs"]}:
                block["extraction_status"] = "verified"
                block["extraction_check"] = "visual-page"
                _record(block)["page_proof"] = "matches_original"
                counts["verified"] += 1
            else:
                counts["waiting for its other page"] += 1
        elif text_only and len(found) == 1 and "<" in block["html"]:
            # Markup would be lost by storing the checker's plain text.
            _record(block)["page_proof"] = "structural:text_in_marked_up_block"
            _record(block)["proof_note"] = note
            counts["text differs in a block with markup"] += 1
        elif text_only and len(found) == 1:
            block["html"] = html.escape(" ".join(found[0]["corrected_text"].split()), quote=False)
            block["source_hash"] = hashlib.sha256(
                (block["kind"] + "\n" + block["html"] + "\n").encode()).hexdigest()[:16]
            _record(block)["page_proof"] = "text_corrected_by_checker"
            _record(block)["proof_note"] = note
            counts["text corrected, to be checked again"] += 1
        else:
            _record(block)["page_proof"] = "structural:" + ",".join(
                sorted({str(p.get("type")) for p in found}))
            _record(block)["proof_note"] = note
            counts["structural problem"] += 1
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, dict(counts))


def _needs_rebuild(block):
    state = _state(block) or ""
    return state.startswith("structural") or state == "page_has_structural_problems"


def rebuild_export(key, folder, proof_folder, per_batch):
    """Pages whose blocks are wrongly divided or ordered, for a restorer to lay out again."""
    document = json.loads((ROOT / "data" / (key + "-trans.json")).read_text())
    folder.mkdir(parents=True, exist_ok=True)
    text = [block for block in document["contents"] if _text_block(block)]
    missing = document.get("column_reflow", {}).get("missing_text", {})
    wanted = sorted({block["source_page"] for block in text if _needs_rebuild(block)} |
                    {int(page) for page in missing})
    count = 0
    pdf = None
    proof_folder.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(wanted), per_batch):
        count += 1
        batch, ids = {"document": key, "pages": []}, {}
        for page in wanted[start:start + per_batch]:
            images = [proof_folder / ("p%04d-%s.png" % (page, half)) for half in ("top", "bottom")]
            if not all(image.exists() for image in images):
                import pypdfium2
                pdf = pdf or pypdfium2.PdfDocument(str(ROOT / "data" / (key + ".pdf")))
                picture = pdf[page - 1].render(scale=SCALE).to_pil()
                height = picture.height
                picture.crop((0, 0, picture.width, int(height * 0.54))).save(images[0])
                picture.crop((0, int(height * 0.46), picture.width, height)).save(images[1])
            on_page = [block for block in text if block["source_page"] == page]
            # Blocks already verified stay as they are; they are shown for orientation only.
            own = [block for block in on_page if block.get("extraction_status") != "verified"]
            done = [block for block in on_page if block.get("extraction_status") == "verified"]
            carried = [block for block in text if block["source_page"] < page and
                       any(ref["page"] == page for ref in block["source_refs"])]
            items = []
            for index, block in enumerate(own, 1):
                item = {"n": index, "kind": block["kind"],
                        "text": " ".join(html.unescape(re.sub(r"<[^>]+>", " ", block["html"])).split())}
                note = _record(block).get("proof_note")
                if note:
                    item["checker_note"] = note
                if len({ref["page"] for ref in block["source_refs"]}) > 1:
                    item["runs_on_to_page"] = block["source_refs"][-1]["page"]
                items.append(item)
            batch["pages"].append({
                "page": page,
                "images": [str(proof_folder / ("p%04d-%s.png" % (page, half))) for half in ("top", "bottom")],
                "already_covered_at_top": [html.unescape(block["html"])[-300:] for block in carried],
                "checker_missing_text": missing.get(str(page), []),
                "already_verified": [html.unescape(re.sub(r"<[^>]+>", " ", block["html"]))[:160]
                                     for block in done],
                "blocks": items})
            ids[str(page)] = [[block["id"], block["source_hash"]] for block in own]
        (folder / ("rebuild.%03d.batch.json" % count)).write_text(
            json.dumps(batch, ensure_ascii=False, indent=1))
        (folder / ("rebuild.%03d.key.json" % count)).write_text(json.dumps(ids))
    print(key, "pages", len(wanted), "batches", count)


def _archive_replaced(document, blocks):
    """Keep the extracted records a rebuilt page replaced.

    Re-extraction (restore_extraction) starts from the raw records, so a
    document that keeps them must not lose the ones a rebuild took over.
    Rebuilt blocks are not raw records; their own sources are kept already.
    """
    archive = document.get("math_preservation")
    if not archive:
        return
    kept = archive.setdefault("rebuilt_blocks", [])
    known = {block["id"] for block in kept}
    for block in blocks:
        if not block.get("column_reflow", {}).get("rebuilt") and block["id"] not in known:
            kept.append(copy.deepcopy(block))
            known.add(block["id"])


def rebuild_apply(key, folder):
    path = ROOT / "data" / (key + "-trans.json")
    document = json.loads(path.read_text())
    contents = document["contents"]
    by_id = {block["id"]: block for block in contents}
    counts = Counter()
    for result_path in sorted(folder.glob("rebuild.*.result.json")):
        ids = json.loads(result_path.with_name(result_path.name.replace("result", "key")).read_text())
        try:
            result = json.loads(result_path.read_text())
        except ValueError:
            counts["unreadable result"] += 1
            continue
        for page in result.get("pages", []):
            listed = ids.get(str(page.get("page")))
            if not listed:
                continue
            old = [by_id.get(identifier) for identifier, _ in listed]
            if any(block is None or block["source_hash"] != digest
                   for block, (_, digest) in zip(old, listed)):
                counts["pages changed since export"] += 1
                continue
            new, bad = [], False
            # Only the last block that takes text from an input block continues
            # where that input block continues (its refs on later pages).
            last_taker = {}
            for index, item in enumerate(page.get("blocks", []), 1):
                for n in item.get("from", []):
                    last_taker[n] = index
            for index, item in enumerate(page.get("blocks", []), 1):
                sources = [old[n - 1] for n in item.get("from", []) if 1 <= n <= len(old)]
                wording = " ".join(str(item.get("text", "")).split())
                if not wording or item.get("kind") not in TEXT | ({"table"} if WITH_TABLES else set()):
                    bad = True
                    break
                boxes = [ref["bbox"] for block in sources for ref in block["source_refs"]
                         if ref["page"] == page["page"]]
                later = [ref for n in item.get("from", []) if 1 <= n <= len(old) and last_taker[n] == index
                         for ref in old[n - 1]["source_refs"] if ref["page"] != page["page"]]
                box = ([min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None)
                source = html.escape(wording, quote=False)
                if item.get("kind") == "math":
                    # KaTeX's auto-render needs the display delimiters in the page.
                    if not source.startswith("\\["):
                        source = "\\[" + source + "\\]"
                    source = '<div class="math-content">' + source + "</div>"
                elif item.get("kind") == "table":
                    # Rows are text lines, cells are separated by " | ";
                    # "header_rows" leading rows are header cells.
                    rows = [line for line in str(item.get("text", "")).split("\n") if line.strip()]
                    heads = int(item.get("header_rows") or 0)
                    source = "<table>" + "".join(
                        "<tr>" + "".join(
                            ("<th>%s</th>" if number < heads else "<td>%s</td>") %
                            html.escape(" ".join(cell.split()), quote=False)
                            for cell in row.split(" | ")) + "</tr>"
                        for number, row in enumerate(rows)) + "</table>"
                elif item.get("kind") == "code":
                    lines = [line.rstrip() for line in str(item.get("text", "")).split("\n")]
                    while lines and not lines[0].strip():
                        lines.pop(0)
                    while lines and not lines[-1].strip():
                        lines.pop()
                    listing = html.escape("\n".join(lines), quote=False)
                    # An algorithm written with inline LaTeX is kept out of <pre>, which
                    # KaTeX's auto-render skips; the class keeps its lines and indentation.
                    source = ('<div class="algorithm">' + listing + "</div>" if "\\(" in listing else
                              '<pre class="algorithm"><code>' + listing + "</code></pre>")
                number = index
                while "pdf-p%04d-r%04d" % (page["page"], number) in by_id or any(
                        other["id"] == "pdf-p%04d-r%04d" % (page["page"], number) for other in new):
                    number += 100
                block = {"id": "pdf-p%04d-r%04d" % (page["page"], number), "kind": item["kind"],
                         "html": source,
                         "source_hash": hashlib.sha256(
                             (item["kind"] + "\n" + source + "\n").encode()).hexdigest()[:16],
                         "html_ja": "", "status": "untranslated", "extraction_status": "needs_review",
                         "source_page": page["page"],
                         "source_refs": ([{"page": page["page"], "bbox": box}] if box else
                                         [{"page": page["page"], "bbox": [0, 0, 612, 792]}]) + later,
                         "column_reflow": {"rebuilt": True,
                                           "from": [block["id"] for block in sources],
                                           "column": None, "gutters": []}}
                if not box:
                    block["column_reflow"]["region_unknown"] = True
                if item.get("kind") == "heading":
                    block["level"] = 2
                if item.get("kind") == "list_item":
                    block.update(ordered=bool(item.get("ordinal")), ordinal=item.get("ordinal"), depth=0)
                if item.get("not_content"):
                    block["page_furniture"] = True
                if item.get("kind") == "code":
                    # Algorithms are shown as printed on both sides, as program listings are.
                    block.update(html_ja=source, status="source_only")
                if item.get("continues_from_previous_page"):
                    block["column_reflow"]["continues_from_previous_page"] = True
                new.append(block)
            if bad or not new:
                counts["pages with an invalid answer"] += 1
                continue
            positions = [contents.index(block) for block in old]
            first = min(positions)
            # Figures and tables between the old blocks keep their place after
            # the rebuilt block that took over the text block before them.
            taken = {}
            for block in new:
                for identifier in block["column_reflow"]["from"]:
                    taken[identifier] = block
            sequence, pending = [], []
            last_new = None
            for block in contents[first:max(positions) + 1]:
                if block in old:
                    target = taken.get(block["id"])
                    if target is not None:
                        last_new = target
                    continue
                pending.append((last_new, block))
            for block in new:
                sequence.append(block)
                sequence.extend(other for anchor, other in pending if anchor is block)
            sequence = [other for anchor, other in pending if anchor is None] + sequence
            contents[first:max(positions) + 1] = sequence
            for block in old:
                by_id.pop(block["id"], None)
            _archive_replaced(document, old)
            for block in new:
                by_id[block["id"]] = block
            counts["pages rebuilt"] += 1
            counts["blocks"] += len(new)
            document.get("column_reflow", {}).get("missing_text", {}).pop(str(page["page"]), None)
    # A paragraph that a rebuilt page continues from the page before.
    index = 1
    while index < len(contents):
        block = contents[index]
        if block.get("column_reflow", {}).get("continues_from_previous_page"):
            previous = next((other for other in reversed(contents[:index])
                             if _text_block(other)), None)
            del block["column_reflow"]["continues_from_previous_page"]
            if (previous is not None and previous["source_refs"][-1]["page"] == block["source_page"] - 1
                    and previous["kind"] in {"paragraph", "list_item", "footnote"}):
                left, right = html.unescape(previous["html"]), html.unescape(block["html"])
                joined = left + right if left.endswith("-") and False else left + " " + right
                previous["html"] = html.escape(joined, quote=False)
                previous["source_hash"] = hashlib.sha256(
                    (previous["kind"] + "\n" + previous["html"] + "\n").encode()).hexdigest()[:16]
                previous["source_refs"] += block["source_refs"]
                previous["extraction_status"] = "needs_review"
                previous.pop("extraction_check", None)
                # Its translation no longer covers the whole text.
                previous["html_ja"], previous["status"] = "", "untranslated"
                previous.pop("translation_check", None)
                previous.pop("translation_fix_rounds", None)
                _record(previous).pop("page_proof", None)
                del contents[index]
                counts["joined across a page break"] += 1
                continue
        index += 1
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, dict(counts))


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("command", choices=["export", "apply", "rebuild-export", "rebuild-apply"])
    cli.add_argument("--proof-dir", type=Path, help="rebuild-export: folder holding the page images")
    cli.add_argument("key")
    cli.add_argument("folder", type=Path)
    cli.add_argument("--pages-per-batch", type=int, default=3)
    cli.add_argument("--pages", help="export: only these pages (comma-separated)")
    args = cli.parse_args()
    global WITH_TABLES
    WITH_TABLES = bool(json.loads((ROOT / "data" / (args.key + "-trans.json")).read_text())
                       .get("page_proof_tables"))
    if args.command == "rebuild-export":
        rebuild_export(args.key, args.folder, args.proof_dir, args.pages_per_batch)
    elif args.command == "rebuild-apply":
        rebuild_apply(args.key, args.folder)
    elif args.command == "export":
        export(args.key, args.folder, args.pages_per_batch,
               {int(page) for page in args.pages.split(",")} if args.pages else None)
    else:
        apply(args.key, args.folder)


if __name__ == "__main__":
    sys.exit(main())
