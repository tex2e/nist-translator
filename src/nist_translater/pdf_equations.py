"""Recover mathematical runs from the font and geometry of the pinned PDF.

A PDF carries no equation tree. This module uses glyph geometry as evidence
for conventional semantic LaTeX; editorial review resolves ambiguous runs.
The PDF coordinates and recovered TeX remain available for review.
"""

import html
import re
from collections import Counter
from statistics import median

BODY_FONTS = {
    "HIOWEK+TimesNewRomanPSMT",
    "BVNBEP+ArialMT",
    "PIGLFI+Arial-BoldMT",
    "NPPUBB+TimesNewRomanPS-BoldMT",
    "ZBPGSR+TimesNewRomanPS-BoldItalicMT",
}
ITALIC = "RTISPV+TimesNewRomanPS-ItalicMT"
SYMBOLS = {
    "#": r"\#",
    "{": r"\{",
    "}": r"\}",
    "½": r"\frac12",
    "µ": r"\mu ",
    "´": r"\prime ",
    "•": r"\bullet ",
    "−": "-",
    "∑": r"\sum ",
    "∫": r"\int ",
    "√": r"\sqrt ",
    "∞": r"\infty ",
    "≤": r"\le ",
    "≥": r"\ge ",
    "≠": r"\ne ",
    "≈": r"\approx ",
    "×": r"\times ",
    "⋅": r"\cdot ",
    "…": r"\ldots ",
    "∏": r"\prod ",
    "∈": r"\in ",
    "∉": r"\notin ",
    "∪": r"\cup ",
    "∩": r"\cap ",
    "→": r"\to ",
    "↔": r"\leftrightarrow ",
    "±": r"\pm ",
    "∂": r"\partial ",
    "∅": r"\emptyset ",
    "\uf06c": r"\cdots ",
    "\uf04c": r"\ldots ",
    "\uf024": r"\exists ",
}
# Extensible Symbol-font delimiters are several glyphs at one x coordinate.
PIECES = {
    "\uf8eb": "(",
    "\uf8ec": "(",
    "\uf8ed": "(",
    "\uf8f6": ")",
    "\uf8f7": ")",
    "\uf8f8": ")",
    "\uf8ee": "[",
    "\uf8ef": "[",
    "\uf8f0": "[",
    "\uf8f9": "]",
    "\uf8fa": "]",
    "\uf8fb": "]",
    "\uf8f1": r"\{",
    "\uf8f2": r"\{",
    "\uf8f3": r"\{",
    "\uf8fc": r"\}",
    "\uf8fd": r"\}",
    "\uf8fe": r"\}",
    "\uf8f4": "|",
}


def _token(c, value=None):
    return {
        "x0": c["x0"],
        "x1": c["x1"],
        "top": c["top"],
        "bottom": c["bottom"],
        "size": c["size"],
        "tex": value if value is not None else SYMBOLS.get(c["text"], c["text"]),
        "raw": c["text"],
        "baseline": 792 - c["matrix"][5],
    }


def _baseline(tokens):
    ordinary = [c for c in tokens if c["raw"] not in PIECES and c["raw"] not in "∑∫√"]
    if not ordinary:
        return median(c["bottom"] for c in tokens), median(c["size"] for c in tokens)
    # The dominant full-size row defines the baseline; smaller rows are limits.
    size = Counter(round(c["size"]) for c in ordinary).most_common(1)[0][0]
    if max(c["size"] for c in ordinary) > size * 1.35:
        size = max(c["size"] for c in ordinary)
    candidates = [c for c in ordinary if abs(c["size"] - size) < 1.5]
    bottom = Counter(
        round(c.get("baseline", c["bottom"])) for c in candidates
    ).most_common(1)[0][0]
    return bottom, size


def recover_region(page, box, graphic_boxes=()):
    """Return readable prose with inline/display TeX, plus an equation ledger."""
    if abs(page.height - 792) > 1:
        raise ValueError("Unexpected SP 800-22 page geometry")
    chars = [
        c
        for c in page.chars
        if c["text"].strip()
        and c["text"] != "€"
        and box[0] - 0.5 <= (c["x0"] + c["x1"]) / 2 <= box[2] + 0.5
        and box[1] - 0.5 <= (c["top"] + c["bottom"]) / 2 <= box[3] + 0.5
        and not any(
            g[0] <= (c["x0"] + c["x1"]) / 2 <= g[2]
            and g[1] <= (c["top"] + c["bottom"]) / 2 <= g[3]
            for g in graphic_boxes
        )
    ]
    if not chars:
        return "", []
    for rule in page.lines:
        if (
            abs(rule["bottom"] - rule["top"]) > 0.5
            or not box[1] <= rule["top"] <= box[3]
        ):
            continue
        if any(
            g[0] <= rule["x0"] <= g[2] and g[1] <= rule["top"] <= g[3]
            for g in graphic_boxes
        ):
            continue
        stems = [
            c
            for c in page.curves
            if abs(c["x1"] - rule["x0"]) < 1
            and abs(c["top"] - rule["top"]) < 1
            and c["bottom"] - c["top"] > 4
        ]
        if stems:
            stem = stems[0]
            chars.append(
                dict(
                    text="√",
                    fontname="Vector+Symbol",
                    size=12,
                    x0=stem["x0"] - 4,
                    x1=rule["x1"],
                    top=rule["top"],
                    bottom=stem["bottom"],
                    matrix=(1, 0, 0, 1, stem["x0"], 792 - stem["bottom"]),
                )
            )

    math_indices = {
        i
        for i, c in enumerate(chars)
        if c["fontname"] not in BODY_FONTS | {ITALIC}
        and (
            "Times" in c["fontname"]
            or "Symbol" in c["fontname"]
            or "MT-Extra" in c["fontname"]
        )
    }
    # Italic single variables, numerical examples, and short indexed names.
    math_indices.update(
        i for i, c in enumerate(chars) if c["size"] < 8.5 and "Times" in c["fontname"]
    )
    italic = [i for i, c in enumerate(chars) if c["fontname"] == ITALIC]
    words = []
    for i in italic:
        if (
            words
            and abs(chars[i]["matrix"][5] - chars[words[-1][-1]]["matrix"][5]) < 1
            and i == words[-1][-1] + 1
            and chars[i]["x0"] - chars[words[-1][-1]]["x1"] < 1.8
        ):
            words[-1].append(i)
        else:
            words.append([i])
    for word in words:
        text = "".join(chars[i]["text"] for i in word)
        if not re.fullmatch(r"[A-Za-z]{3,}", text) or text in {
            "obs",
            "max",
            "min",
            "log",
            "exp",
            "sin",
            "cos",
        }:
            math_indices.update(word)
    # Adjacent regular-font punctuation/digits also belong to mathematical runs.
    for _ in range(3):
        for i, c in enumerate(chars):
            if i in math_indices or not re.fullmatch(
                r"[0-9=+\-−<>≤≥.,()/|]+", c["text"]
            ):
                continue
            if any(
                abs(c["bottom"] - chars[j]["bottom"]) < 3
                and min(abs(c["x0"] - chars[j]["x1"]), abs(c["x1"] - chars[j]["x0"]))
                < 2
                for j in math_indices
            ):
                math_indices.add(i)
    indices = sorted(math_indices)
    parent = {i: i for i in indices}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for pos, i in enumerate(indices):
        a = chars[i]
        for j in indices[pos + 1 :]:
            b = chars[j]
            horizontal = max(0, max(a["x0"], b["x0"]) - min(a["x1"], b["x1"]))
            vertical = max(0, max(a["top"], b["top"]) - min(a["bottom"], b["bottom"]))
            baseline_gap = abs(a["matrix"][5] - b["matrix"][5])
            same_row = baseline_gap < 2 or (
                abs(a["size"] - b["size"]) > 2 and baseline_gap < 12
            )
            extensible = (
                a["text"] in PIECES
                or b["text"] in PIECES
                or a["text"] in "∑∫"
                or b["text"] in "∑∫"
            )
            if horizontal <= 4.5 and vertical <= 3.5 and (same_row or extensible):
                parent[find(j)] = find(i)
    components = {}
    for i in indices:
        components.setdefault(find(i), []).append(i)
    # Fraction rules connect operands that otherwise are separate tiny runs.
    rules = [
        r
        for r in page.lines
        if (abs(r["bottom"] - r["top"]) < 0.5 or abs(r["x1"] - r["x0"]) < 0.5)
        and box[0] <= r["x0"]
        and r["x1"] <= box[2]
        and box[1] <= r["top"] <= box[3]
        and not any(
            g[0] <= r["x0"] <= g[2] and g[1] <= r["top"] <= g[3] for g in graphic_boxes
        )
    ]
    for r in rules:
        if not 2 < r["x1"] - r["x0"] < 170:
            continue
        touching = [
            i
            for i in indices
            if r["x0"] - 0.5 <= (chars[i]["x0"] + chars[i]["x1"]) / 2 <= r["x1"] + 0.5
            and r["top"] - 18 < chars[i]["top"] < r["top"] + 16
        ]
        for i in touching[1:]:
            parent[find(i)] = find(touching[0])
    components = {}
    for i in indices:
        components.setdefault(find(i), []).append(i)
    items = [
        dict(
            _token(c),
            bottom=792 - c["matrix"][5],
            text=html.escape(c["text"]),
            math=False,
        )
        for i, c in enumerate(chars)
        if i not in math_indices
    ]
    ledger = []
    for members in components.values():
        cs = [chars[i] for i in members]
        tokens = [_token(c) for c in cs]
        x0 = min(c["x0"] for c in cs)
        x1 = max(c["x1"] for c in cs)
        top = min(c["top"] for c in cs)
        bottom = max(c["bottom"] for c in cs)
        local_rules = [
            r
            for r in rules
            if x0 - 5 <= r["x0"] and r["x1"] <= x1 + 5 and top <= r["top"] <= bottom
        ]
        glyph_text = "".join(
            t["tex"] for t in sorted(tokens, key=lambda t: (t["baseline"], t["x0"]))
        )
        baseline, size = _baseline(tokens)
        # The surrounding prose row anchors inline fractions and scripts.
        nearby = [
            792 - c["matrix"][5]
            for i, c in enumerate(chars)
            if i not in math_indices and top - 2 <= 792 - c["matrix"][5] <= bottom + 5
        ]
        if nearby:
            baseline = min(
                nearby, key=lambda y: abs(y - (top + bottom) / 2 - size * 0.25)
            )
        record = dict(
            source_glyph_text=glyph_text, bbox=[x0, top, x1, bottom], baseline=baseline
        )
        ledger.append(record)
        from .semantic_math import semantic_math

        markup = semantic_math(cs, local_rules, baseline)
        items.append(
            dict(
                x0=x0,
                x1=x1,
                top=baseline - size,
                bottom=baseline,
                size=size,
                text=markup,
                math=True,
            )
        )
    rows = []
    for item in sorted(items, key=lambda t: (t["bottom"], t["x0"])):
        matching = [r for r in rows if abs(r["bottom"] - item["bottom"]) < 3]
        if matching:
            matching[-1]["items"].append(item)
        else:
            rows.append(dict(bottom=item["bottom"], items=[item]))
    output = []
    previous = None
    for row in rows:
        parts = sorted(row["items"], key=lambda t: t["x0"])
        content = ""
        last = None
        for item in parts:
            if last and item["x0"] - last["x1"] > 1.5:
                content += " "
            content += item["text"]
            last = item
        if not content.strip():
            continue
        if all(i["math"] for i in parts):
            content = '<div class="math-content">' + content + "</div>"
            output.append(content)
        else:
            if (
                previous is not None
                and row["bottom"] - previous < 18
                and output
                and output[-1].endswith("</p>")
            ):
                output[-1] = output[-1][:-4] + " " + content + "</p>"
            else:
                output.append("<p>" + content + "</p>")
        previous = row["bottom"]
    return "\n".join(output), sorted(ledger, key=lambda r: (r["bbox"][1], r["bbox"][0]))


FORBIDDEN_MATH_COMMANDS = re.compile(
    r"\\(?:htmlStyle|mathrlap|mathllap|mathclap|raisebox|kern|rule|vphantom|phantom|hphantom)\b"
)


def inline_katex_html(source_html):
    """Accept structural TeX only; coordinate-layout math must be reviewed."""
    if FORBIDDEN_MATH_COMMANDS.search(source_html) or any(
        marker in source_html
        for marker in ("pdf-math-layout", "pdf-math-glyph", "data-tex=")
    ):
        raise ValueError(
            "Coordinate-layout mathematics must be reconstructed as semantic LaTeX"
        )
    return source_html


def pending_math_translation(source_html):
    """Retain the same formulas/tags while leaving prose translation pending."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(source_html, "html.parser")
    seen = set()
    for node in list(soup.find_all(string=True)):
        if (
            node.find_parent("span", class_="pdf-math-source")
            or node.find_parent("code")
            or not node.strip()
            or re.fullmatch(r"[\s\d.,+−\-–%()]+", str(node))
        ):
            continue
        parent = node.find_parent(["p", "div"]) or node.parent
        key = id(parent)
        parts = re.split(r"(\\\[.*?\\\]|\\\(.*?\\\))", str(node), flags=re.S)
        for index in range(0, len(parts), 2):
            if parts[index].strip():
                parts[index] = "説明文の訳は再確認中です。 " if key not in seen else " "
                seen.add(key)
        node.replace_with("".join(parts))
    return str(soup)
