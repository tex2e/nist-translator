"""Hand untranslated, verified blocks to translators in batches and import the results.

    python scripts/translate_batches.py export OUT_DIR KEY [--chars N]
    python scripts/translate_batches.py apply OUT_DIR KEY

``export`` writes ``<key>.<nnn>.batch.json`` with consecutive untranslated
blocks whose English source is verified, in document order, so a translator
sees the surrounding text. A translator answers each with
``<key>.<nnn>.result.json``: a JSON array of ``{"id", "source_hash", "html_ja"}``.
``apply`` imports each answer on its own; a translation whose tags or
requirement keywords differ from the source is rejected and stays untranslated.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.translation import make_queue, merge_translations  # noqa: E402


def _document(key):
    path = ROOT / "data" / (key + "-trans.json")
    return path, json.loads(path.read_text())


def export(folder, key, chars):
    _, document = _document(key)
    verified = {block["id"] for block in document["contents"]
                if block.get("extraction_status") == "verified" or document.get("source_format") != "pdf"}
    kinds = {block["id"]: block["kind"] for block in document["contents"]}
    queue = [item for item in make_queue(document) if item["id"] in verified and kinds[item["id"]] != "figure"]
    folder.mkdir(parents=True, exist_ok=True)
    batches, batch, size = [], [], 0
    for item in queue:
        if batch and size + len(item["html"]) > chars:
            batches.append(batch)
            batch, size = [], 0
        batch.append({"id": item["id"], "kind": kinds[item["id"]],
                      "source_hash": item["source_hash"], "en": item["html"]})
        size += len(item["html"])
    if batch:
        batches.append(batch)
    for index, batch in enumerate(batches, 1):
        (folder / ("%s.%03d.batch.json" % (key, index))).write_text(json.dumps(
            {"document": document.get("number", key), "title": document.get("subtitle", ""),
             "blocks": batch}, ensure_ascii=False, indent=1))
    print(key, "blocks", len(queue), "batches", len(batches))


def apply(folder, key):
    path, document = _document(key)
    counts = Counter()
    for result in sorted(folder.glob(key + ".*.result.json")):
        try:
            items = json.loads(result.read_text())
        except ValueError:
            counts["unreadable result"] += 1
            continue
        for item in items if isinstance(items, list) else []:
            try:
                counts["imported"] += merge_translations(document, [item])
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                counts["rejected: " + str(error).split(":")[0][:40]] += 1
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, dict(counts))


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("command", choices=["export", "apply"])
    cli.add_argument("folder", type=Path)
    cli.add_argument("key")
    cli.add_argument("--chars", type=int, default=9000)
    args = cli.parse_args()
    if args.command == "export":
        export(args.folder, args.key, args.chars)
    else:
        apply(args.folder, args.key)


if __name__ == "__main__":
    main()
