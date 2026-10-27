"""Split blocks that hold several paragraphs, headings or list items of the original.

    python scripts/split_merged_blocks.py KEY AUDIT_JSON EVIDENCE_DIR [--exclude ID ...] [--dry-run]

AUDIT_JSON is the output of ``structure_audit.py``. Each ``merged`` finding is
a point where a new paragraph of the PDF starts inside a block. The block's
English HTML is cut there (tags kept; a cut never falls inside a tag), and
each piece becomes a block of its own:

- a piece starting with a section number (e.g. "B.3.14.3 Shared Secrets")
  that the PDF sets as a heading line becomes a heading, its level taken from
  the number;
- a piece starting with a list marker ("b.", "3.", "•") becomes a list item
  (the marker is removed, as in the other list items);
- anything else is a paragraph.

The pieces need checking against the page image and a new translation, so
they are ``needs_review`` and untranslated; the former Japanese of the whole
block is kept in ``split_from_ja`` for the translator. The original block is
archived in ``source_repairs.original_blocks`` and its pages are pinned.
Blocks whose HTML has ``<p>`` structure or unbalanced pieces are skipped and
reported.
"""

import argparse
import copy
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = re.compile(r"(?:^|\s)((?:\d+|[a-z])\.|•|\((?:\d+|[a-z])\))\s*$")
LEADING = re.compile(r"^((?:\d+|[a-z])\.|•|\((?:\d+|[a-z])\))\s+")
LEADING_HTML = re.compile(r"^((?:\d+|[a-z])\.|•|\((?:\d+|[a-z])\))\s+")
SECTION = re.compile(r"^(?:Appendix\s+)?([A-Z]|\d+)((?:\.\d+)*)\.?\s")


def _index_map(source):
    """For every letter/digit of the visible text, its position in the HTML."""
    positions, index = [], 0
    while index < len(source):
        if source[index] == "<":
            index = source.index(">", index) + 1
            continue
        if source[index] == "&":
            end = source.find(";", index)
            if 0 < end - index < 10:
                if re.match(r"[A-Za-z0-9]", html.unescape(source[index:end + 1])):
                    positions.append(index)
                index = end + 1
                continue
        if re.match(r"[A-Za-z0-9]", source[index]):
            positions.append(index)
        index += 1
    return positions


def _balanced(piece):
    tags = re.findall(r"<(/?)([a-zA-Z0-9]+)[^>]*>", piece)
    stack = []
    for closing, name in tags:
        if name in {"br", "img"}:
            continue
        if not closing:
            stack.append(name)
        elif not stack or stack.pop() != name:
            return False
    return not stack


def _rehash(block):
    block["source_hash"] = hashlib.sha256(
        (block["kind"] + "\n" + block["html"] + "\n").encode()).hexdigest()[:16]


def split(block, findings):
    source = block["html"]
    positions = _index_map(source)
    cuts = []
    for finding in sorted(findings, key=lambda item: item["offset"]):
        if finding["offset"] >= len(positions):
            return None, "offset beyond text"
        cut = positions[finding["offset"]]
        # Step back over whitespace, a list marker and opening tags before it.
        while cut and source[cut - 1].isspace():
            cut -= 1
        marker = MARKER.search(source[:cut])
        ordinal = None
        if marker and finding.get("text", "").startswith(marker.group(1)):
            ordinal = marker.group(1).strip("().")
            cut = marker.start(1)
        while True:
            opening = re.search(r"<[a-zA-Z][^>]*>\s*$", source[:cut])
            if not opening:
                break
            cut = opening.start()
        cuts.append((cut, finding, ordinal))
    pieces, start = [], 0
    first = {"heading": False}
    for cut, finding, ordinal in [(0, first, None)] + cuts:
        if pieces:
            pieces[-1]["html"] = source[start:cut].strip()
        pieces.append({"finding": finding, "ordinal": ordinal})
        start = cut
    pieces[-1]["html"] = source[start:].strip()
    for piece in pieces:
        if not piece["html"] or not _balanced(piece["html"]):
            return None, "unbalanced or empty piece"
    return pieces, None


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("key")
    cli.add_argument("audit", type=Path)
    cli.add_argument("evidence", help="evidence directory recorded in source_repairs")
    cli.add_argument("--exclude", nargs="*", default=[])
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args()
    path = ROOT / "data" / (args.key + "-trans.json")
    document = json.loads(path.read_text())
    contents = document["contents"]
    by_id = {block["id"]: block for block in contents}
    wanted = {}
    for finding in json.loads(args.audit.read_text()):
        if finding["type"] != "merged" or finding.get("kind") == "table" or finding["id"] in args.exclude:
            continue
        block = by_id.get(finding["id"])
        if block is None or block["kind"] in {"table", "figure", "math", "code"}:
            continue
        wanted.setdefault(finding["id"], {})[finding["offset"]] = finding
    repair = document.get("source_repairs")
    if repair is None:
        raise SystemExit("no source_repairs record; start one before splitting")
    report = {"split": [], "skipped": []}
    pages = set()
    for identifier, findings in wanted.items():
        block = by_id[identifier]
        if "<p>" in block["html"]:
            report["skipped"].append({"id": identifier, "reason": "<p> structure"})
            continue
        pieces, problem = split(block, list(findings.values()))
        if problem:
            report["skipped"].append({"id": identifier, "reason": problem})
            continue
        new = []
        for number, piece in enumerate(pieces, 1):
            text = html.unescape(re.sub(r"<[^>]+>", "", piece["html"]))
            item = {"id": "%s-s%02d" % (identifier, number), "kind": "paragraph", "html": piece["html"],
                    "html_ja": "", "status": "untranslated", "extraction_status": "needs_review",
                    "source_page": block["source_page"],
                    "source_refs": copy.deepcopy(block["source_refs"]),
                    "split_from": identifier}
            finding = piece["finding"]
            if finding is not None and finding.get("bbox"):
                page = finding.get("page", block["source_page"])
                item["source_page"] = page
                item["source_refs"] = [{"page": page, "bbox": finding["bbox"]}]
            section = SECTION.match(text)
            if section and len(text) < 120 and (finding.get("heading") or number == 1) \
                    and not text.rstrip().endswith("."):
                item["kind"] = "heading"
                item["level"] = 2 + section.group(2).count(".") if not text.startswith("Appendix") else 2
            elif piece["ordinal"] or (number == 1 and LEADING.match(text)):
                ordinal = piece["ordinal"] or LEADING.match(text).group(1).strip("().")
                # A lettered item sits under a numbered one in these documents.
                item.update(kind="list_item", ordered=ordinal != "•",
                            ordinal=int(ordinal) if ordinal.isdigit() else ordinal,
                            depth=1 if ordinal.isalpha() and len(ordinal) == 1 else 0)
                item["html"] = LEADING_HTML.sub("", item["html"], count=1)
            elif number == 1 and block["kind"] == "list_item":
                for field in ("kind", "ordered", "ordinal", "depth"):
                    if field in block:
                        item[field] = block[field]
            if number == 1:
                item["split_from_ja"] = block.get("html_ja", "")
            _rehash(item)
            new.append(item)
        # The last piece carries the original's continuation onto later pages.
        later = [ref for ref in block["source_refs"] if ref["page"] > new[-1]["source_page"]]
        if later and new[-1]["source_refs"] != block["source_refs"]:
            new[-1]["source_refs"] += later
        for item in new[1:]:
            item["split_from_ja"] = "(see %s)" % new[0]["id"]
        position = contents.index(block)
        contents[position:position + 1] = new
        repair["original_blocks"].append(copy.deepcopy(block))
        pages.update(ref["page"] for ref in block["source_refs"])
        report["split"].append({"id": identifier, "pieces": [(item["id"], item["kind"], item["html"][:70])
                                                            for item in new]})
    if pages:
        repair["history"].append({key: copy.deepcopy(repair[key]) for key in
                                  ("source_sha256", "pages", "evidence_directory", "reason",
                                   "retired_math_regions") if key in repair})
        repair["pages"] = sorted(set(repair["pages"]) | pages)
        repair["evidence_directory"] = args.evidence
        repair["reason"] = ("Split blocks holding several original paragraphs, headings or list items "
                            "(structure_audit findings); originals archived, pieces to be proofed and translated.")
    out = ROOT / args.evidence / "split-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print("split", len(report["split"]), "skipped", len(report["skipped"]), "pages", sorted(pages))
    if not args.dry_run:
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
