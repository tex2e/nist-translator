"""Correct printed numeric/identifier/code errors in the Japanese column (2026-10-31).

    python scripts/fix_source_errors.py

The English column stays as printed. The Japanese column gets the value that the document
itself fixes uniquely, followed by a translator's note (訳注) with the printed form and the
reason. Each fix checks the text it replaces, so running it twice changes nothing.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NOTE_GX = "［訳注: 原本では末尾の「3」が欠けた 134 桁で印刷されています。同じ項目の 16 進値から求めた 135 桁の値に直しました。］"
NOTE_SEC = "［訳注: 原本では「Section 3.2.2.1」。W-25519 は第3.2.1.6節で規定されている（第3.2.2.1節は Curve25519）。］"
NOTE_D19 = "［訳注: 原本では「D.1.9.4」。D.1.9 の唯一の小節のため D.1.9.1 としました。］"

EBNF_47_FIXES = [
    ("ClassType = ′_INP′ | ′_MEM′ | ′_DAT′ | ...\n", "ClassType = ′_INP′ | ′_MEM′ | ′_DAT′ | ...;\n"),
    ("| ′Calculate′ | ′Evaluate′ ...;", "| ′Calculate′ | ′Evaluate′ | ...;"),
    ("| ′Wrong Object Resolved′ | ′Wrong Function Resolved′ | ...;\n",
     "| ′Wrong Object Resolved′ | ′Wrong Function Resolved′ | ...\n"),
    ("| ′Overbound Pointer′ | ′Underbound Pointer′ | ′Wrong Position Pointer′ | ...\n",
     "| ′Overbound Pointer′ | ′Underbound Pointer′ | ′Wrong Position Pointer′ | ...;\n"),
    ("′Entity Access FinalError′\n", "′Entity Access FinalError′;\n"),
    ("FinalError = ′Query Injection′ | ′Command Injection′ | ′Source Code Injection′ | ...;\n",
     "FinalError = ′Query Injection′ | ′Command Injection′ | ′Source Code Injection′ | ...\n"),
    ("SemicolonSymbol = ′:′;", "SemicolonSymbol = ′;′;"),
    ("RightAngleSymbol = ′⟩′\n", "RightAngleSymbol = ′⟩′;\n"),
    ("ConvergingSymbol = ′⊕′;;", "ConvergingSymbol = ′⊕′;"),
]
NOTE_47 = ("\n\n(* 訳注: 原本の表記の誤りを直しました。ClassType・FinalErrorType・Fault・RightAngleSymbol の終端の「;」を補い、"
           "Fault・FinalError の途中の「;」を除き、Operation の「′Evaluate′ ...」に「|」を補いました。"
           "原本では SemicolonSymbol = ′:′、ConvergingSymbol = ′⊕′;; と印刷されています。 *)")
EBNF_49_FIXES = [("FirstWeakness = ′⟨′, Bug | Fault), ", "FirstWeakness = ′⟨′, (Bug | Fault), ")]
NOTE_49 = "\n\n(* 訳注: 原本では FirstWeakness の右辺の「(」が欠けています（Bug | Fault)）。 *)"


def replace(text, old, new):
    if new in text and old not in text:
        return text
    assert text.count(old) == 1, old
    return text.replace(old, new)


def code_fix(block, fixes, note):
    ja = block["html"]
    for old, new in fixes:
        ja = replace(ja, old, new)
    block["html_ja"] = ja.replace("</code></pre>", note + "</code></pre>")
    block["status"] = "reviewed"


def main():
    changes = {
        "sp800-186": {
            "pdf-p0026-math-091": lambda b: b.update(html_ja=replace(replace(
                b["html_ja"], "534562907 (", "5345629073 ("), "</p>", NOTE_GX + "</p>")),
            "pdf-p0027-r0001": lambda b: b.update(html_ja=replace(
                b["html_ja"], "第3.2.2.1節で規定する曲線 W-25519", "第3.2.1.6節で規定する曲線 W-25519")
                + NOTE_SEC),
        },
        "sp800-82r3": {
            "pdf-p0212-b0007": lambda b: b.update(html_ja=replace(
                b["html_ja"], "D.1.9.4. NERC重要インフラ保護（CIP）基準", "D.1.9.1. NERC重要インフラ保護（CIP）基準")
                + NOTE_D19),
        },
        "sp800-231": {
            "pdf-p0047-b0002": lambda b: code_fix(b, EBNF_47_FIXES, NOTE_47),
            "pdf-p0049-b0011": lambda b: code_fix(b, EBNF_49_FIXES, NOTE_49),
        },
    }
    for stem, fixes in changes.items():
        path = ROOT / "data" / (stem + "-trans.json")
        document = json.loads(path.read_text())
        for block in document["contents"]:
            if block["id"] in fixes:
                if "訳注" not in block["html_ja"]:
                    fixes[block["id"]](block)
                    block["source_error_fix"] = "2026-10-31: 原本の誤記を訳文の欄で直し、訳注を付けた（英文は原本どおり）"
                print(stem, block["id"], "ok")
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
