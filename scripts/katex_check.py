"""Check every formula of a document with the bundled KaTeX.

    python scripts/katex_check.py KEY ...

Formulas are the \\( \\) / \\[ \\] spans of the English and Japanese text of
blocks that are shown (page furniture is skipped). Prints each formula that
KaTeX cannot render, with the block id.
"""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import math_restore  # noqa: E402


def formulas(document):
    for block in document["contents"]:
        if block.get("page_furniture"):
            continue
        for field in ("html", "html_ja"):
            text = html.unescape(re.sub(r"<[^>]+>", " ", block.get(field, "")))
            for formula in re.findall(r"\\\((.*?)\\\)|\\\[(.*?)\\\]", text, re.S):
                inline, display = formula
                yield block["id"], field, ("\\(" + inline + "\\)") if inline else ("\\[" + display + "\\]")


def main():
    failed = 0
    for key in sys.argv[1:]:
        document = json.loads((ROOT / "data" / (key + "-trans.json")).read_text())
        found = list(formulas(document))
        errors = math_restore._katex_errors([formula for _, _, formula in found]) if found else {}
        print(key, "formulas", len(found), "errors", len(errors))
        for index, message in sorted(errors.items()):
            identifier, field, formula = found[index]
            print("  ", identifier, field, message[:140], "|", formula[:160])
        failed += len(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
