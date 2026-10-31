"""Have codex check the sentences that an LLM reworded into です・ます調 (2026-10-31).

    python scripts/codex_desu_masu_review.py RESULT.json [...] --out OUT_DIR [--jobs N] [--model M] [--base REV]

For each reworded item, the sentence before (at --base, the commit before the style change)
and after (in data/ now) is sent with the English block, in chunks of 60. codex answers only
the items it flags: {"i", "problem", "fix"}. The flags go to OUT_DIR/chunk-NNN.json for Opus to
judge; nothing is applied here.
"""

import argparse
import html
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANION = max(Path.home().glob(".claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs"))

RULES = """You review Japanese translations of NIST publications for a bilingual reading site.
The sentence endings were changed from plain style (である調) to polite style (です・ます調).
Adjective endings were reworded to avoid "〜いです" (e.g. 望ましい→望まれます, 多い→多くあります,
難しい→困難です, 〜しやすい→〜しやすい傾向があります). For each item you get the English block,
the Japanese sentence before, and after. Flag an item ONLY when the "after" sentence:
- changes the meaning, certainty or strength compared with "before" and the English (added hedging such as
  でしょう/と考えられます, added evaluation or recommendation, a state change such as 高い→高くなります,
  a weakened or strengthened requirement: shall=しなければなりません, should=すべきです, may=してもよいです/場合があります),
- is ungrammatical or clearly unnatural Japanese, or
- is still in plain style at the end of the sentence.
Do not flag purely stylistic preferences, and do not flag what was already the same in "before".
Answer with ONLY a JSON array of flagged items: [{"i": <item number>, "problem": "<short Japanese>",
"fix": "<the corrected full Japanese 'after' sentence>"}]. Answer [] when nothing is wrong.
"""

SENTENCE = re.compile(r"[^。]*。?")


def plain(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", markup or ""))).strip()


def load_base(rev, doc, cache={}):
    if doc not in cache:
        raw = subprocess.run(["git", "show", "%s:data/%s-trans.json" % (rev, doc)], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        cache[doc] = {b["id"]: b for b in json.loads(raw)["contents"]}
    return cache[doc]


def build_items(paths, base):
    current = {}
    items = []
    for path in paths:
        for item in json.loads(path.read_text()):
            if item.get("skip") or not item.get("old"):
                continue
            doc = item["doc"]
            if doc not in current:
                current[doc] = {b["id"]: b for b in json.loads((ROOT / "data" / (doc + "-trans.json")).read_text())["contents"]}
            block, old_block = current[doc].get(item["id"]), load_base(base, doc).get(item["id"])
            if not block or not old_block:
                continue
            # sentences keep their count (only endings change), so the same index is the same sentence
            old_sentences = SENTENCE.findall(plain(old_block["html_ja"]))
            new_sentences = SENTENCE.findall(plain(block["html_ja"]))
            hits = [k for k, s in enumerate(old_sentences) if plain(item["old"]).rstrip("。") in s]
            if len(hits) != 1 or len(old_sentences) != len(new_sentences):
                continue
            before, after = old_sentences[hits[0]].strip(), new_sentences[hits[0]].strip()
            if before and after and before != after:
                items.append({"doc": doc, "id": item["id"], "english": plain(block["html"])[:1500],
                              "before": before, "after": after})
    return items


def review(index, chunk, out_dir, model):
    target = out_dir / ("chunk-%03d.json" % index)
    if target.exists():
        return index, "cached"
    body = "\n\n".join("Item %d\nEnglish: %s\nBefore: %s\nAfter: %s" % (i, it["english"], it["before"], it["after"])
                       for i, it in enumerate(chunk))
    command = ["node", str(COMPANION), "task"] + (["--model", model] if model else []) + [RULES + "\n" + body]
    run = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    text = run.stdout
    try:
        flags = json.loads(text[text.find("["):text.rfind("]") + 1])
        assert isinstance(flags, list)
    except (ValueError, AssertionError):
        (out_dir / ("chunk-%03d.error.txt" % index)).write_text(text + "\n---\n" + run.stderr[-3000:])
        return index, "error"
    for flag in flags:
        if isinstance(flag, dict) and isinstance(flag.get("i"), int) and 0 <= flag["i"] < len(chunk):
            flag.update({k: chunk[flag["i"]][k] for k in ("doc", "id", "english", "before", "after")})
    target.write_text(json.dumps(flags, ensure_ascii=False, indent=1) + "\n")
    return index, len(flags)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("results", nargs="+", type=Path)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--jobs", type=int, default=6)
    cli.add_argument("--model")
    cli.add_argument("--base", default="82aa5a55")
    cli.add_argument("--size", type=int, default=60)
    args = cli.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    items = build_items(args.results, args.base)
    (args.out / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n")
    chunks = [items[i:i + args.size] for i in range(0, len(items), args.size)]
    print("items", len(items), "chunks", len(chunks), flush=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        for index, result in pool.map(lambda pair: review(pair[0], pair[1], args.out, args.model), enumerate(chunks)):
            print(index, result, flush=True)


if __name__ == "__main__":
    sys.exit(main())
