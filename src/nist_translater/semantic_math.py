import re, html
from collections import Counter
from statistics import median
from src.nist_translater.pdf_equations import SYMBOLS, PIECES, _token, _baseline


def semantic_math(chars, rules, baseline):
    """Infer fraction/script/root structure; output conventional LaTeX only.

    Geometry is recognition evidence, never a rendering instruction. Candidates
    remain needs_review until source/definitions/examples have been checked.
    """
    tokens = []
    handled = set()
    _, size = _baseline([_token(c) for c in chars])
    for i, c in enumerate(chars):
        if i in handled:
            continue
        raw = c["text"]
        tex = SYMBOLS.get(raw, raw)
        if raw in PIECES:
            group = [
                (j, d)
                for j, d in enumerate(chars)
                if d["text"] in PIECES
                and PIECES[d["text"]] == PIECES[raw]
                and abs(d["x0"] - c["x0"]) < 1
            ]
            handled.update(j for j, d in group)
            t = _token(c, PIECES[raw])
            t.update(
                top=min(d["top"] for j, d in group),
                bottom=max(d["bottom"] for j, d in group),
                baseline=baseline,
                size=size,
            )
        else:
            if "\ue000" <= raw <= "\uf8ff" and raw not in SYMBOLS:
                raise ValueError("Unknown glyph " + repr(raw))
            if raw in "{}%&#_":
                tex = {
                    "{": r"\{",
                    "}": r"\}",
                    "%": r"\%",
                    "&": r"\&",
                    "#": r"\#",
                    "_": r"\_",
                }[raw]
            t = _token(c, tex)
        tokens.append(t)
    bars = [
        dict(r)
        for r in rules
        if r["x1"] - r["x0"] > 2 and abs(r["bottom"] - r["top"]) < 0.5
    ]
    return (
        '<span class="pdf-math-source">'
        + html.escape(r"\(" + parse(tokens, bars, baseline, size) + r"\)")
        + "</span>"
    )


def atom(tex, group, base, size):
    return dict(
        tex=tex,
        raw="",
        x0=min(t["x0"] for t in group),
        x1=max(t["x1"] for t in group),
        top=min(t["top"] for t in group),
        bottom=max(t["bottom"] for t in group),
        baseline=base,
        size=size,
        composite=True,
    )


def parse(tokens, bars, base=None, size=None, level=0):
    if not tokens:
        return ""
    if level > 15:
        raise ValueError("Deep math")
    tokens = [dict(t) for t in tokens]
    bars = [dict(r) for r in bars]
    if size is None:
        base, size = _baseline(tokens)
    # Vector radicals include the complete horizontal root bar in their box.
    for root in sorted(
        [t for t in tokens if t["raw"] == "√"], key=lambda t: t["x1"] - t["x0"]
    ):
        if root not in tokens:
            continue
        group = [
            t
            for t in tokens
            if t is not root
            and root["x0"] + 2 <= t["x0"]
            and t["x1"] <= root["x1"] + 1
            and root["top"] - 1 <= t["baseline"] <= root["bottom"] + 2
        ]
        if not group:
            root["tex"] = r"\sqrt{}"
            continue
        rb = [
            r
            for r in bars
            if root["x0"] <= r["x0"]
            and r["x1"] <= root["x1"] + 1
            and r["top"] > root["top"] + 1
        ]
        content = parse(group, rb, base, size, level + 1)
        result = atom(
            r"\sqrt{" + content + "}",
            [root] + group,
            (
                max(t["baseline"] for t in group if t["size"] >= size * 0.8)
                if any(t["size"] >= size * 0.8 for t in group)
                else base
            ),
            size,
        )
        tokens = [t for t in tokens if t not in group and t is not root] + [result]
        bars = [
            r for r in bars if not (root["x0"] <= r["x0"] and r["x1"] <= root["x1"] + 1)
        ]
    # Wide outer fraction bars first; their subtrees recursively consume inner bars.
    for bar in sorted(bars, key=lambda r: r["x1"] - r["x0"], reverse=True):
        if bar not in bars:
            continue
        y = bar["top"]
        group = [
            t
            for t in tokens
            if bar["x0"] - 0.8 <= (t["x0"] + t["x1"]) / 2 <= bar["x1"] + 0.8
            and t["top"] < y + 22
            and t["bottom"] > y - 35
        ]
        above = [t for t in group if t["baseline"] < y + 1]
        below = [t for t in group if t["baseline"] >= y + 1]
        if not above or not below:
            continue
        inner = [
            r
            for r in bars
            if r != bar
            and bar["x0"] - 0.5 <= r["x0"]
            and r["x1"] <= bar["x1"] + 0.5
            and abs(r["top"] - y) < 35
        ]
        ab = [r for r in inner if r["top"] < y]
        bb = [r for r in inner if r["top"] > y]
        a = parse(above, ab, None, None, level + 1)
        b = parse(below, bb, None, None, level + 1)
        result = atom(r"\frac{" + a + "}{" + b + "}", group, y + size * 0.25, size)
        tokens = [t for t in tokens if t not in group] + [result]
        bars = [r for r in bars if r != bar and r not in inner]
    # Read main row, then bind raised/lowered small glyphs as script groups.
    if base is None:
        base, size = _baseline(tokens)
    main = [
        t
        for t in tokens
        if abs(t["baseline"] - base) < 2.3
        and t["size"] >= size * 0.82
        or t.get("composite")
        and abs(t["baseline"] - base) < 4
        or t["raw"] in ("∑", "∫", "∏")
    ]
    if not main:
        largest = max(tokens, key=lambda t: t["size"])
        base = largest["baseline"]
        size = largest["size"]
        main = [t for t in tokens if abs(t["baseline"] - base) < 2.3]
    extras = [t for t in tokens if t not in main]
    for t in sorted(main, key=lambda t: 0 if t["raw"] in ("∑", "∫", "∏") else 1):
        if t["raw"] in ("∑", "∫", "∏"):
            nearby = [
                e
                for e in extras
                if t["x0"] - 7 <= e["x0"] <= t["x1"] + 6
                and abs(e["baseline"] - base) < 30
            ]
        else:
            nexts = [a for a in main if a["x0"] > t["x0"] + 0.5]
            stop = min((a["x0"] for a in nexts), default=t["x1"] + 24)
            nearby = [
                e
                for e in extras
                if t["x0"] - 0.7 <= e["x0"] < stop + 0.2
                and e["x0"] <= t["x1"] + 18
                and abs(e["baseline"] - base) < 24
            ]
        low = [e for e in nearby if e["baseline"] > base + 0.3]
        high = [e for e in nearby if e["baseline"] < base - 0.3]
        if low:
            t["tex"] += "_{" + parse(low, [], None, None, level + 1) + "}"
        if high:
            t["tex"] += "^{" + parse(high, [], None, None, level + 1) + "}"
        extras = [e for e in extras if e not in low + high]
    # Unattached elements remain readable; annotate review outside this function.
    allmain = sorted(main + extras, key=lambda t: (t["x0"], t["baseline"]))
    result = " ".join(t["tex"] for t in allmain)
    result = re.sub(r"(?<=[A-Za-z0-9]) (?=[A-Za-z0-9])", "", result)
    result = re.sub(r"(?<=[0-9]) \. (?=[0-9])", ".", result)
    for name in ["obs", "erfc", "igamc", "log", "exp", "sin", "cos", "min", "max"]:
        result = re.sub(
            r"(?<![A-Za-z])" + name + r"(?![A-Za-z])",
            lambda m: (
                r"\mathrm{obs}" if name == "obs" else r"\operatorname{" + name + "}"
            ),
            result,
        )
    result = re.sub(r"P\s*-\s*value", r"P\\text{-value}", result)
    return result
