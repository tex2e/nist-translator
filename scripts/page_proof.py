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
TEXT = {"paragraph", "heading", "list_item", "note", "footnote"}


def _blocks(document):
    return [block for block in document["contents"]
            if block.get("column_reflow") and not block.get("page_furniture") and
            block["kind"] in TEXT and block.get("extraction_status") == "needs_review"]


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


def export(key, folder, per_batch):
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
    numbers = sorted(page for page, blocks in pages.items() if blocks)
    rng = random.Random(key)
    count = 0
    for start in range(0, len(numbers), per_batch):
        count += 1
        batch, key_data = {"document": key, "pages": []}, {"plants": []}
        chunk = numbers[start:start + per_batch]
        candidates = [(page, index) for page in chunk for index, block in enumerate(pages[page])
                      if len(block["html"]) >= 120 and len(block["source_refs"]) == 1 and
                      block["column_reflow"].get("page_proof") is None]
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
                text = html.unescape(block["html"])
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
                block["column_reflow"]["page_proof"] = "page_has_structural_problems"
                counts["on a page with structural problems"] += 1
            elif pages >= {ref["page"] for ref in block["source_refs"]}:
                block["extraction_status"] = "verified"
                block["extraction_check"] = "visual-page"
                block["column_reflow"]["page_proof"] = "matches_original"
                counts["verified"] += 1
            else:
                counts["waiting for its other page"] += 1
        elif text_only and len(found) == 1:
            block["html"] = html.escape(" ".join(found[0]["corrected_text"].split()), quote=False)
            block["source_hash"] = hashlib.sha256(
                (block["kind"] + "\n" + block["html"] + "\n").encode()).hexdigest()[:16]
            block["column_reflow"]["page_proof"] = "text_corrected_by_checker"
            block["column_reflow"]["proof_note"] = note
            counts["text corrected, to be checked again"] += 1
        else:
            block["column_reflow"]["page_proof"] = "structural:" + ",".join(
                sorted({str(p.get("type")) for p in found}))
            block["column_reflow"]["proof_note"] = note
            counts["structural problem"] += 1
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, dict(counts))


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("command", choices=["export", "apply"])
    cli.add_argument("key")
    cli.add_argument("folder", type=Path)
    cli.add_argument("--pages-per-batch", type=int, default=3)
    args = cli.parse_args()
    if args.command == "export":
        export(args.key, args.folder, args.pages_per_batch)
    else:
        apply(args.key, args.folder)


if __name__ == "__main__":
    sys.exit(main())
