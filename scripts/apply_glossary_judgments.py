"""Apply judgments on glossary violations reported by check_glossary.py.

    python scripts/apply_glossary_judgments.py RESULT.json [...]

Each result is a JSON array of
``{"document", "id", "rule", "decision": "fix"|"allow", "edits": [{"old", "new"}], "reason"}``.
"fix" replaces each ``old`` (which must occur in the block's html_ja) with ``new``;
"allow" records the block in data/glossary-exceptions.json with the reason, so the check
accepts it. An edit whose ``old`` is not found is reported and skipped.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_glossary import EXCEPTIONS, ROOT  # noqa: E402

ABOUT = ("check_glossary.py が避ける訳語として検出したが、別の英語の訳であるなどの理由で"
         "許容したブロック。{資料: {ブロック ID: {規則: 理由}}}")


def main(paths):
    judgments = [item for path in paths for item in json.loads(Path(path).read_text())]
    exceptions = json.loads(EXCEPTIONS.read_text())["exceptions"] if EXCEPTIONS.exists() else {}
    by_document = {}
    for item in judgments:
        by_document.setdefault(item["document"], []).append(item)
    fixed = allowed = skipped = 0
    for key, items in sorted(by_document.items()):
        path = ROOT / "data" / (key + "-trans.json")
        document = json.loads(path.read_text())
        blocks = {block["id"]: block for block in document["contents"]}
        changed = False
        for item in items:
            block = blocks[item["id"]]
            if item["decision"] == "allow":
                exceptions.setdefault(key, {}).setdefault(item["id"], {})[item["rule"]] = item.get("reason", "")
                allowed += 1
                continue
            for edit in item.get("edits", []):
                if edit["old"] and edit["old"] in block["html_ja"]:
                    block["html_ja"] = block["html_ja"].replace(edit["old"], edit["new"])
                    changed = True
                    fixed += 1
                elif edit["old"] != edit["new"]:
                    print("not found:", key, item["id"], repr(edit["old"]))
                    skipped += 1
        if changed:
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    EXCEPTIONS.write_text(json.dumps({"about": ABOUT, "exceptions": {
        key: dict(sorted(blocks.items())) for key, blocks in sorted(exceptions.items())}},
        ensure_ascii=False, indent=1) + "\n")
    print("edits applied", fixed, "allowed", allowed, "skipped", skipped)


if __name__ == "__main__":
    main(sys.argv[1:])
