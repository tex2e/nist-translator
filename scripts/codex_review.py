"""Have Codex review the batches written by ``translation_review.py export``.

    python scripts/codex_review.py BATCH_DIR [--jobs N] [--effort E]

For each ``<key>.<nnn>.batch.json`` without a ``.verdict.json``, Codex (the
codex plugin's companion, read-only, no file writes) reads the batch in the
prompt and answers with the JSON verdict array, which is validated and saved.
Then apply with ``translation_review.py apply BATCH_DIR --reviewer codex``.
Rerunning only handles the batches still without a verdict.
"""

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

COMPANION = max(Path.home().glob(".claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs"))

RULES = """You are an independent reviewer of Japanese translations of NIST publications for an unofficial English-Japanese parallel-text site. A block becomes "reviewed" only if you answer "ok". A wrong "ok" is much worse than a wrong "issue".

Each block has id, kind, source_hash, en (the English source, verified against the original PDF) and ja (the draft translation). Blocks are not necessarily contiguous.

Rules:
- LaTeX formulas in ja must be the same formulas as in en; only \\text{...} contents may be translated. Do not "correct" formulas.
- In a reference-list entry, authors, titles, publication names, identifiers and URLs stay in the original language on purpose; only connective words are translated. Every element must be present and URLs identical.
- A fragment that begins or ends mid-sentence (the original paragraph is split there) must correspond to exactly that English fragment and read naturally when continued.
- For prose: read the Japanese on its own, then compare clause by clause: grammatical roles and direction of relations, negation, conditions, scope of modifiers, requirement strength (shall = しなければならない, shall not = してはならない, should = すべきである, may = してもよい / 場合がある as the sense requires; uppercase keywords SHALL/SHOULD/MAY stay in English the same number of times), omissions and additions, numbers and section references, terminology consistent within the block, same HTML tags, natural plain-register (だ・である) Japanese. Purely stylistic alternatives are not an issue when the draft is accurate and readable.
- In a list item, a trailing "and" / "or" that only joins it to the next item may be left untranslated when the Japanese item ends with 。 (the site's convention). It is an issue only when dropping it loses meaning, e.g. an "or" that makes requirements alternatives rather than cumulative.
- Do not run commands or read other files; judge from the text below.

Answer with ONLY a JSON array (no prose, no code fence), one object per block in the same order:
{"id", "source_hash" (copied), "verdict": "ok" or "issue", "note": "" for ok else a short Japanese explanation, "suggested_ja": "" for ok else a complete corrected translation with exactly the same HTML tags and LaTeX formulas as en}.

Batch:
"""


def review(batch_path, effort):
    verdict_path = batch_path.with_name(batch_path.name.replace(".batch.json", ".verdict.json"))
    batch = json.loads(batch_path.read_text())
    command = ["node", str(COMPANION), "task"]
    if effort:
        command += ["--effort", effort]
    command.append(RULES + json.dumps(batch, ensure_ascii=False, indent=1))
    run = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    text = run.stdout
    start, end = text.find("["), text.rfind("]")
    try:
        answers = json.loads(text[start:end + 1])
        expected = [block["id"] for block in batch["blocks"]]
        if [item["id"] for item in answers] != expected:
            raise ValueError("ids do not match the batch")
        if any(item.get("verdict") not in {"ok", "issue"} for item in answers):
            raise ValueError("bad verdict value")
    except (ValueError, KeyError, TypeError) as error:
        (batch_path.with_suffix(".codex-error.txt")).write_text(text + "\n---\n" + run.stderr[-4000:])
        return batch_path.name, "error: %s" % error
    verdict_path.write_text(json.dumps(answers, ensure_ascii=False, indent=1) + "\n")
    counts = {verdict: sum(item["verdict"] == verdict for item in answers) for verdict in ("ok", "issue")}
    return batch_path.name, counts


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("batch_dir", type=Path)
    cli.add_argument("--jobs", type=int, default=1)
    cli.add_argument("--effort", choices=["low", "medium", "high", "xhigh"])
    args = cli.parse_args()
    todo = [path for path in sorted(args.batch_dir.glob("*.batch.json"))
            if not path.with_name(path.name.replace(".batch.json", ".verdict.json")).exists()]
    print("batches to review:", len(todo), flush=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        for name, result in pool.map(lambda path: review(path, args.effort), todo):
            print(name, result, flush=True)


if __name__ == "__main__":
    main()
