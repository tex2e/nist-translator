"""Apply the final (Opus) judgments of the summaries codex flagged.

    python scripts/apply_summary_judgments.py JUDGE_DIR REVIEW_DIR

JUDGE_DIR/<stem>.json is {"decision": "keep" | "fix", "summary": [...], "note"}.
REVIEW_DIR/<stem>.verdict.json is codex's check. Summaries codex found ok and
judged summaries both get a "review" record in data/<stem>-summary.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANNED = ("本訳", "本サイト", "このサイト", "<")


def valid(sentences, number):
    return (isinstance(sentences, list) and 2 <= len(sentences) <= 5
            and all(isinstance(s, str) and s.strip() for s in sentences)
            and not any(word in s for s in sentences for word in BANNED)
            and number in sentences[0])


def main(judge_dir, review_dir):
    counts = {"codex_ok": 0, "keep": 0, "fix": 0, "rejected": 0, "missing": 0}
    for verdict_path in sorted(review_dir.glob("*.verdict.json")):
        stem = verdict_path.name[:-len(".verdict.json")]
        path = ROOT / "data" / (stem + "-summary.json")
        summary = json.loads(path.read_text())
        verdict = json.loads(verdict_path.read_text())
        review = {"reviewer": "codex", "verdict": verdict["verdict"], "note": verdict.get("note", "")}
        if verdict["verdict"] == "issue":
            judge_path = judge_dir / (stem + ".json")
            if not judge_path.exists():
                counts["missing"] += 1
                print("no judgment:", stem)
                continue
            judgment = json.loads(judge_path.read_text())
            decision = judgment["decision"]
            if decision == "fix":
                if valid(judgment.get("summary"), summary["number"]):
                    summary["summary"] = judgment["summary"]
                else:
                    counts["rejected"] += 1
                    print("rejected fix:", stem)
                    continue
            counts[decision] += 1
            review["final"] = {"judge": "claude-opus-5-5", "decision": decision,
                               "note": judgment.get("note", "")}
        else:
            counts["codex_ok"] += 1
        summary["review"] = review
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(counts)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
