"""Japanese descriptions of figures, written by looking at the figure image.

    python scripts/figure_descriptions.py export OUT_DIR KEY ...
    python scripts/figure_descriptions.py apply  OUT_DIR KEY ...

``export`` writes ``<key>.figures.json``: every published figure (not a
withheld official mark) without a description, with the absolute path of its
image, its caption and the text around it. A describer answers with
``<key>.figures.result.json``: a list of ``{"id", "source_hash", "alt_ja"}``.

``apply`` stores the description as the ``alt`` of the image in ``html_ja``
(the page shows it beside the figure) and marks the figure ``draft`` until a
reviewer has compared the description with the image.
"""

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _text(block):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", block.get("html", ""))).split())


def export(folder, key):
    document = json.loads((ROOT / "data" / (key + "-trans.json")).read_text())
    contents = document["contents"]
    shown = [block for block in contents if not block.get("page_furniture")]
    items = []
    for index, block in enumerate(shown):
        if block["kind"] != "figure" or block.get("official_mark") or block.get("html_ja"):
            continue
        source = re.search(r'src="([^"]+)"', block["html"]).group(1)
        after = [_text(other) for other in shown[index + 1:index + 3]]
        before = [_text(other) for other in shown[max(0, index - 2):index]]
        caption = next((text for text in after + before if re.match(r"(Figure|Fig\.|Table)\s*\d", text)), "")
        items.append({"id": block["id"], "source_hash": block["source_hash"], "page": block["source_page"],
                      "image": str(ROOT / "html" / source), "caption": caption,
                      "text_before": before[-1:] , "text_after": after[:1]})
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (key + ".figures.json")).write_text(json.dumps(
        {"document": document.get("number", key), "title": document.get("subtitle", ""), "figures": items},
        ensure_ascii=False, indent=1))
    print(key, "figures", len(items))


def apply(folder, key):
    """Store descriptions; a checker's verdicts (<key>.figures.check.json) decide the status."""
    path = ROOT / "data" / (key + "-trans.json")
    document = json.loads(path.read_text())
    blocks = {block["id"]: block for block in document["contents"]}
    result = folder / (key + ".figures.result.json")
    if not result.exists():
        print(key, "no result")
        return
    checks = {}
    if (folder / (key + ".figures.check.json")).exists():
        checks = {item["id"]: item for item in json.loads((folder / (key + ".figures.check.json")).read_text())}
    counts = {"reviewed": 0, "corrected, to be checked again": 0, "unchecked": 0, "crop problem": 0}
    for item in json.loads(result.read_text()):
        block = blocks.get(item.get("id"))
        description = " ".join(str(item.get("alt_ja", "")).split())
        if block is None or block["source_hash"] != item.get("source_hash") or not description:
            print(key, "skipped", item.get("id"))
            continue
        check = checks.get(block["id"], {})
        if check.get("verdict") == "issue" and check.get("suggested_alt_ja"):
            description = " ".join(check["suggested_alt_ja"].split())
            block["status"], block["translation_check"] = "draft", "claude-fix"
            block["review_note"] = check.get("note", "")
            counts["corrected, to be checked again"] += 1
        elif check.get("verdict") == "ok":
            block["status"], block["translation_check"] = "reviewed", "claude-review"
            counts["reviewed"] += 1
        else:
            block["status"] = "draft"
            counts["unchecked"] += 1
        if item.get("crop_problem") or check.get("crop_ok") is False:
            block["crop_problem"] = item.get("crop_problem") or check.get("note", "")
            counts["crop problem"] += 1
        elif check.get("crop_ok"):
            # The checker saw the whole figure in the crop of the original page.
            block["extraction_status"], block["extraction_check"] = "verified", "visual"
        block["html_ja"] = re.sub(r'alt="[^"]*"', 'alt="%s"' % html.escape(description, quote=True),
                                  block["html"], count=1)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(key, counts)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("command", choices=["export", "apply"])
    cli.add_argument("folder", type=Path)
    cli.add_argument("keys", nargs="+")
    args = cli.parse_args()
    for key in args.keys:
        (export if args.command == "export" else apply)(args.folder, key)


if __name__ == "__main__":
    main()
