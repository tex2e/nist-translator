"""Have codex check the Japanese document summaries (data/*-summary.json) against the document.

    python scripts/codex_summary_review.py OUT_DIR [--jobs N] [--model M]
    python scripts/codex_summary_review.py OUT_DIR --apply

The first form writes, for every summary not yet checked, OUT_DIR/<stem>.verdict.json:
{"verdict": "ok" | "issue", "note", "summary": [...corrected sentences when "issue"]}.
codex sees the document's opening text (abstract, purpose and scope, table of contents)
and the summary. --apply writes accepted corrections back and records the check in the
summary file ("review": {"reviewer", "verdict", "note"}).
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
HIDDEN = ("page_furniture", "math_duplicate_of", "duplicate_artifact_of", "figure_text_of", "official_mark")

RULES = """You check a short Japanese summary of a NIST publication for a bilingual reading site.
Judge only from the document text given below (its opening part: abstract, purpose and scope, contents).
Check: every statement is supported by the text (no invented facts, numbers, dates or claims);
the first sentence names the document by its number; it is 3-4 sentences in polite です・ます style;
terminology follows the Japanese translation excerpts shown; it does not present the site or the summary
as official NIST material, and does not advise readers. Purely stylistic preferences are not issues.
Answer with ONLY a JSON object: {"verdict": "ok" or "issue", "note": "" or a short Japanese explanation,
"summary": [] for ok, or the complete corrected list of Japanese sentences for issue}.
"""


def opening_text(stem, limit=7000):
    document = json.loads((ROOT / "data" / (stem + "-trans.json")).read_text())
    english, japanese = [], []
    for block in document["contents"]:
        if any(block.get(key) for key in HIDDEN) or block["kind"] in ("figure", "code"):
            continue
        text = re.sub(r"<[^>]+>", " ", html.unescape(block["html"])).strip()
        if text:
            english.append(text)
            japanese.append(re.sub(r"<[^>]+>", " ", html.unescape(block.get("html_ja") or "")).strip())
        if sum(len(t) for t in english) > limit:
            break
    return "\n".join(english), "\n".join(japanese[:60])


def review(path, out_dir, model):
    stem = path.name[:-len("-summary.json")]
    summary = json.loads(path.read_text())
    english, japanese = opening_text(stem)
    prompt = (RULES + "\nDocument: " + summary["number"] + "\n\nDocument text (English, opening):\n" + english +
              "\n\nJapanese translation excerpts:\n" + japanese[:3000] +
              "\n\nSummary to check:\n" + json.dumps(summary["summary"], ensure_ascii=False))
    command = ["node", str(COMPANION), "task"] + (["--model", model] if model else []) + [prompt]
    run = subprocess.run(command, capture_output=True, text=True, timeout=1200)
    text = run.stdout
    try:
        verdict = json.loads(text[text.find("{"):text.rfind("}") + 1])
        assert verdict.get("verdict") in ("ok", "issue")
    except (ValueError, AssertionError):
        (out_dir / (stem + ".error.txt")).write_text(text + "\n---\n" + run.stderr[-3000:])
        return stem, "error"
    (out_dir / (stem + ".verdict.json")).write_text(json.dumps(verdict, ensure_ascii=False, indent=1) + "\n")
    return stem, verdict["verdict"]


def apply(out_dir):
    counts = {"ok": 0, "fixed": 0, "kept": 0}
    for verdict_path in sorted(out_dir.glob("*.verdict.json")):
        stem = verdict_path.name[:-len(".verdict.json")]
        path = ROOT / "data" / (stem + "-summary.json")
        summary, verdict = json.loads(path.read_text()), json.loads(verdict_path.read_text())
        fixed = verdict.get("summary") or []
        if verdict["verdict"] == "issue" and isinstance(fixed, list) and 2 <= len(fixed) <= 5 \
                and all(isinstance(s, str) and s.strip() for s in fixed):
            summary["summary"] = fixed
            counts["fixed"] += 1
        else:
            counts["ok" if verdict["verdict"] == "ok" else "kept"] += 1
        summary["review"] = {"reviewer": "codex", "verdict": verdict["verdict"], "note": verdict.get("note", "")}
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(counts)


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("out_dir", type=Path)
    cli.add_argument("--jobs", type=int, default=4)
    cli.add_argument("--model")
    cli.add_argument("--apply", action="store_true")
    args = cli.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.apply:
        apply(args.out_dir)
        return
    todo = [p for p in sorted((ROOT / "data").glob("*-summary.json"))
            if not (args.out_dir / (p.name[:-len("-summary.json")] + ".verdict.json")).exists()]
    print("summaries to check:", len(todo), flush=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        for stem, result in pool.map(lambda p: review(p, args.out_dir, args.model), todo):
            print(stem, result, flush=True)


if __name__ == "__main__":
    sys.exit(main())
