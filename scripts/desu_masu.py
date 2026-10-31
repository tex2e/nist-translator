"""Turn the Japanese translations from the plain style (である調) into です・ます調.

    .venv/bin/python scripts/desu_masu.py [--apply] [--report FILE] [DOC ...]

Only the predicate at the end of a sentence (a sentence ends with "。") is changed, using a
morphological analyzer (fugashi + unidic-lite), so the rest of the sentence stays exactly as
it was. Fragments without "。" (list items, table cells, headings) are left as they are.

Endings that cannot be conjugated mechanically are reported instead of changed:
an i-adjective ("よい", "多い": "多いです" reads badly, so these need rewording), a
predicate inside an HTML tag, or a form the rules below do not cover.
The requirement keywords after a predicate ("（SHALL）") are kept as they are.
"""

import argparse
import glob
import json
import re
from pathlib import Path

import fugashi
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parent.parent
HIDDEN = ("page_furniture", "duplicate_artifact_of", "math_duplicate_of", "figure_text_of",
          "official_mark", "third_party_excerpt")
TAGGER = fugashi.Tagger()

# the ending after the predicate: requirement keywords, closing brackets, then "。"
TAIL = re.compile(r"(\s*(?:\[[^\]\n。]{1,60}\])*\s*(?:[（(][A-Za-z][A-Za-z ]{1,14}[）)])?(?:\[[^\]\n。]{1,60}\])*[」』）)]*。)")
# masu-stem of a godan verb from its dictionary-form ending
GODAN = {"う": "い", "く": "き", "ぐ": "ぎ", "す": "し", "つ": "ち", "ぬ": "に", "ぶ": "び", "む": "み", "る": "り"}


def masu_stem(surface, ctype):
    """The 連用形 used before ます, from a verb's 終止形 surface."""
    if ctype.startswith("サ行変格"):
        if surface.endswith("する"):
            return surface[:-2] + "し"
        if surface.endswith("ずる"):
            return surface[:-2] + "じ"
        return None
    if ctype.startswith("カ行変格"):
        return surface[:-2] + "き" if surface.endswith("くる") else surface[:-2] + "来"
    if ctype.startswith(("上一段", "下一段")):
        return surface[:-1] if surface.endswith("る") else None
    if ctype.startswith("五段"):
        last = surface[-1]
        return surface[:-1] + GODAN[last] if last in GODAN else None
    return None


A_TO_I = {"わ": "い", "か": "き", "が": "ぎ", "さ": "し", "た": "ち", "な": "に", "ば": "び", "ま": "み", "ら": "り"}


def stem_of(word):
    """The ます-stem of a verb token in its 連用形 or 未然形, keeping the text's own spelling
    ("義務づけ" stays "義務づけ"; "招い" → "招き"; "含ま" → "含み"; "行っ" → "行い")."""
    surface, ctype, cform = word.surface, word.feature.cType or "", word.feature.cForm or ""
    base = word.feature.orthBase or word.feature.lemma or ""
    if surface == "行っ":
        return "行い"   # the analyzer reads 行った as 行く (go); in these documents it is 行う (do)
    if ctype.startswith("サ行変格"):
        return surface[:-1] + "し" if surface[-1:] in ("し", "さ", "せ") else None
    if ctype.startswith("カ行変格"):
        return surface[:-1] + "き" if surface[-1:] in ("き", "こ") else surface[:-1] + "来"
    if ctype.startswith(("上一段", "下一段")):
        return surface
    if ctype.startswith("五段"):
        if cform.startswith("連用形-一般"):
            return surface
        if cform.startswith("未然形"):
            return surface[:-1] + A_TO_I[surface[-1]] if surface[-1:] in A_TO_I else None
        if "音便" in cform and base[-1:] in GODAN:
            return surface[:-1] + GODAN[base[-1]]
    return None


def convert_predicate(text):
    """Return the text with its final predicate in です・ます調, or None when not covered."""
    words = list(TAGGER(text))
    if not words:
        return None
    w = words
    last = w[-1]
    pos, ctype, cform = last.feature.pos1, last.feature.cType or "", last.feature.cForm or ""
    lemma = last.feature.lemma or ""
    head = text[:len(text) - len(last.surface)]
    prev = w[-2] if len(w) > 1 else None
    prev2 = w[-3] if len(w) > 2 else None
    if not cform.startswith("終止形"):
        return None
    # である → です、ではない → ではありません、であった handled below
    if pos == "動詞" and lemma == "有る" and prev is not None and prev.surface == "で":
        return text[:len(text) - len("である")] + "です"
    if pos == "助動詞" and ctype.startswith("助動詞-ダ"):          # だ
        return head + "です"
    if pos == "助動詞" and ctype.startswith("助動詞-タ"):          # past: した → しました, であった → でした
        if prev is None:
            return None
        if prev.surface == "あっ" and prev2 is not None and prev2.surface == "で":
            return text[:len(text) - len("であった")] + "でした"
        if prev.surface == "なかっ":
            stem = text[:len(text) - len("なかった")]
            if prev2 is not None and prev2.feature.pos1 == "動詞":
                return stem + "ませんでした"
            if stem.endswith("では"):
                return stem + "ありませんでした"
            return None
        if prev.feature.pos1 == "動詞":
            stem = stem_of(prev)
            if stem is None:
                return None
            start = len(text) - len(last.surface) - len(prev.surface)
            return text[:start] + stem + "ました"
        if prev.feature.pos1 == "助動詞" and prev.surface in ("れ", "られ", "せ", "させ"):
            start = len(text) - len(last.surface)
            return text[:start] + "ました"
        return None
    if pos == "助動詞" and ctype.startswith("助動詞-ナイ"):        # できない → できません、ならない → なりません
        if prev is None or prev.feature.pos1 not in ("動詞", "助動詞"):
            return None
        if prev.feature.pos1 == "動詞":
            stem = stem_of(prev)
            if stem is None:
                return None
            start = len(text) - len(last.surface) - len(prev.surface)
            return text[:start] + stem + "ません"
        if prev.surface in ("れ", "られ", "せ", "させ"):
            return head + "ません"
        return None
    if pos == "形容詞" and lemma == "無い":                        # ではない / 必要はない → ではありません / 必要はありません
        return head + "ありません"
    if pos == "助動詞" and ctype.startswith(("助動詞-レル", "助動詞-ラレル", "助動詞-セル", "助動詞-サセル")):
        return text[:-1] + "ます" if text.endswith("る") else None
    if pos == "動詞":
        stem = masu_stem(last.surface, ctype)
        return head + stem + "ます" if stem else None
    return None


def verb_dictionary_form(word):
    """終止形 of a verb token that may be in a 音便 form (行っ → 行う)."""
    lemma_form = word.feature.orthBase or word.feature.lemma
    if not lemma_form:
        return None
    # keep the kanji the text used: replace the token with its 終止形 by the shared prefix
    surface = word.surface
    common = 0
    while common < min(len(surface), len(lemma_form)) and surface[common] == lemma_form[common]:
        common += 1
    return surface[:common] + lemma_form[common:] if common else lemma_form


SENTENCE = re.compile(r"[^。]*?" + TAIL.pattern)


def sentence_edits(text, stats):
    """(start, end, replacement) for each sentence ending in the text that can be converted."""
    edits = []
    for match in SENTENCE.finditer(text):
        tail = match.group(1)
        body_end = match.end() - len(tail)
        body = text[match.start():body_end]
        stripped = body.rstrip()
        body_end -= len(body) - len(stripped)
        body = stripped
        stats["sentences"] += 1
        if re.search(r"(です|ます|でした|ました|ません|でしょう)$", body) or not body.strip():
            continue
        converted = convert_predicate(body)
        if converted is None and body.endswith("か") and len(body) > 1:
            # a question ("…しているか。" in assessment procedures) → "…していますか。"
            inner = convert_predicate(body[:-1])
            converted = inner + "か" if inner else None
        if converted is None and re.search(r"を参照$", body):
            converted = body + "してください"
        if converted is None and re.search(r"[てで]もよい$", body):
            # MAY: "してもよい" → "してもよいです" (decided by the requester, 2026-10-31)
            converted = body + "です"
        if converted is None:
            stats["left"] += 1
            stats.setdefault("examples", []).append(body[-25:])
            continue
        common = 0
        while common < min(len(body), len(converted)) and body[common] == converted[common]:
            common += 1
        edits.append((match.start() + common, body_end, converted[common:]))
        stats["converted"] += 1
    return edits


def convert_text(text, stats):
    """Convert every sentence ending in a plain string (used for tests)."""
    for start, end, replacement in reversed(sentence_edits(text, stats)):
        text = text[:start] + replacement + text[end:]
    return text


SKIP_TAGS = ("code", "pre", "script", "math", "style")


def convert_html(markup, stats):
    """Convert sentence endings in a block's html_ja.

    The text of the whole block is read across tags, since a sentence often ends with
    "（<strong>SHALL</strong>）。" or a citation link before "。". The original markup is
    edited in place (no re-serialization), and only inside the text piece that holds the
    changed predicate; tags, entities, links and formulas stay exactly as they were.
    """
    if "。" not in markup:
        return markup
    parts = re.split(r"(<[^>]+>)", markup)
    texts, starts, owners, depth, position = [], [], [], 0, 0
    for index, part in enumerate(parts):
        if index % 2:  # a tag
            name = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            if name and name.group(1).lower() in SKIP_TAGS and not part.endswith("/>"):
                depth += -1 if part.startswith("</") else 1
            continue
        text = part if depth <= 0 else " " * len(part)   # formulas/code: blank, so never edited
        texts.append(text)
        starts.append(position)
        owners.append(index)
        position += len(text)
    full = "".join(texts)
    per_part = {}
    for start, end, replacement in sentence_edits(full, stats):
        slot = max(i for i, s in enumerate(starts) if s <= start)
        if end > starts[slot] + len(texts[slot]):
            stats["converted"] -= 1   # the predicate spans a tag: leave it
            stats["left"] += 1
            stats.setdefault("examples", []).append("[tag] " + full[max(0, end - 20):end])
            continue
        per_part.setdefault(owners[slot], []).append((start - starts[slot], end - starts[slot], replacement))
    if not per_part:
        return markup
    for index, edits in per_part.items():
        part = parts[index]
        for start, end, replacement in sorted(edits, reverse=True):
            part = part[:start] + replacement + part[end:]
        parts[index] = part
    return "".join(parts)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--report", type=Path)
    cli.add_argument("docs", nargs="*")
    args = cli.parse_args()
    paths = [ROOT / "data" / (d + "-trans.json") for d in args.docs] or \
        [Path(p) for p in sorted(glob.glob(str(ROOT / "data" / "*-trans.json")))]
    total = {"sentences": 0, "converted": 0, "left": 0}
    report = {}
    for path in paths:
        document = json.loads(path.read_text())
        stats = {"sentences": 0, "converted": 0, "left": 0}
        for block in document["contents"]:
            if any(block.get(k) for k in HIDDEN) or block.get("kind") in ("heading", "code", "math") \
                    or block.get("status") not in ("draft", "reviewed") or not block.get("html_ja"):
                continue
            new = convert_html(block["html_ja"], stats)
            if args.apply and new != block["html_ja"]:
                block["html_ja"] = new
        if args.apply:
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        for key in total:
            total[key] += stats[key]
        report[path.name[:-len("-trans.json")]] = stats
    print(total, "converted %.1f%%" % (100 * total["converted"] / max(total["sentences"], 1)))
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
