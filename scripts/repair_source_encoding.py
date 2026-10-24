"""Repair existing loss markers using paired extraction from pinned PDFs.

Dry run by default. --apply archives changed records and invalidates their
review status. Structural reconstruction of 47r1 and mathematics is separate.
"""

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nist_translater.pdf_source_repairs import PROFILES, repair_font_maps  # noqa: E402


def repair_text(text, pairs):
    """Resolve each damaged word from actual font-corrected source words.

    Cropped tables may contain only a suffix of a PDF word. Offset maps keep
    those suffixes aligned without guessing whether a missing glyph is ti,
    tti, ft or Th. Ambiguous candidates fail instead of choosing a letter.
    """
    def resolve(match):
        token = match.group()
        if "\ufffd" not in token:
            return token
        candidates = set()
        for before, after in pairs:
            pattern = "".join("(.+?)" if c == "\ufffd" else re.escape(c) for c in before)
            decoded = re.fullmatch(pattern, after)
            if not decoded:
                continue
            pieces, groups = [], iter(decoded.groups())
            for char in before:
                pieces.append(next(groups) if char == "\ufffd" else char)
            start = before.find(token)
            while start >= 0:
                candidates.add("".join(pieces[start:start + len(token)]))
                start = before.find(token, start + 1)
        if len(candidates) != 1:
            raise ValueError("Unresolved or ambiguous damaged word: " + token + " " + repr(candidates))
        return candidates.pop()
    return re.sub(r"[A-Za-z0-9_\ufffd]+", resolve, text)


def invalidate(block):
    if block.get("status") == "reviewed" or block.get("extraction_status") == "verified":
        block["encoding_previous_review"] = {
            k: deepcopy(block[k]) for k in ("status", "extraction_status", "extraction_check",
                                            "translation_check", "translation_review") if k in block}
    block["extraction_status"] = "needs_review"
    if block.get("status") == "reviewed":
        block["status"] = "draft"
    for key in ("extraction_check", "translation_check", "translation_review", "translation_fix_rounds"):
        block.pop(key, None)


def repair(key, apply=False):
    import pdfplumber
    path = ROOT / "data" / ("sp800-" + key + "-trans.json")
    pdf_path = path.with_name("sp800-" + key + ".pdf")
    document = json.loads(path.read_text())
    source_sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if document.get("source_sha256", source_sha) != source_sha:
        raise ValueError("Stored extraction and source PDF versions differ")
    if source_sha not in PROFILES:
        raise ValueError("Unreviewed PDF; do not infer replacement characters")
    changed = [b for b in document["contents"] if "\ufffd" in b.get("html", "")
               or "\ufffd" in b.get("html_ja", "")]
    if not changed:
        print(key, "nothing to repair")
        return
    pages = sorted({r["page"] for b in changed for r in b["source_refs"]})
    pairs = []
    with pdfplumber.open(pdf_path) as original, pdfplumber.open(pdf_path) as corrected:
        mappings = repair_font_maps(corrected, source_sha)
        if not mappings:
            raise ValueError("Expected bad font maps were not found")
        for page in pages:
            old = original.pages[page - 1].extract_words()
            new = corrected.pages[page - 1].extract_words()
            assert len(old) == len(new), (key, page, "word boundaries changed")
            for a, b in zip(old, new):
                assert a["x0"] == b["x0"] and a["top"] == b["top"]
                if "\ufffd" in a["text"]:
                    assert "\ufffd" not in b["text"], (key, page, a["text"])
                    pairs.append((a["text"], b["text"]))
    archive = document.setdefault("source_repairs", {
        "source_sha256": source_sha, "pages": [], "block_ids": [], "original_blocks": []})
    count = 0
    for block in changed:
        previous = deepcopy(block)
        for field in ("html", "html_ja"):
            block[field] = repair_text(block.get(field, ""), pairs)
            assert "\ufffd" not in block[field]
        count += previous["html"].count("\ufffd") + previous.get("html_ja", "").count("\ufffd")
        block["source_hash"] = hashlib.sha256((block["kind"] + "\n" + block["html"] + "\n" +
                                               block.get("source_image_hash", "")).encode()).hexdigest()[:16]
        invalidate(block)
        block["encoding_repair"] = {"method": "pdf-font-cmap-word-alignment", "source_sha256": source_sha,
                                     "mappings": mappings, "date": "2026-10-24",
                                     "source_hash": block["source_hash"],
                                     "note": "文字変換を修正。全文・訳文の再照合は未完了。"}
        archive["original_blocks"].append(previous)
        archive["block_ids"].append(block["id"])
    if apply:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, "blocks", len(changed), "replacements", count, "applied" if apply else "dry run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keys", nargs="+", choices=["177r1", "189", "53ar5"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for key in args.keys:
        repair(key, args.apply)
