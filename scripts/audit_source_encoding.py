"""Scan active JSON source/translations for replacement characters (one process)."""

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nist_translater.source_quality import encoding_issues  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json-only", action="store_true", help="check data before rebuilding HTML")
    args = parser.parse_args()
    documents, issues = 0, []
    for path in sorted((ROOT / "data").glob("*-trans.json")):
        documents += 1
        issues.extend(dict(document=path.name, **issue)
                      for issue in encoding_issues(json.loads(path.read_text())))
    html_issues, html_files = [], 0
    if not args.json_only:
        for path in sorted((ROOT / "html").glob("*.html")):
            html_files += 1
            count = html.unescape(path.read_text()).count("\ufffd")
            if count:
                html_issues.append({"file": path.name, "count": count})
    report = {"documents": documents, "html_files": html_files, "affected_fields": len(issues),
              "replacement_count": sum(i["count"] for i in issues), "issues": issues,
              "html_replacement_count": sum(i["count"] for i in html_issues), "html_issues": html_issues}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("documents", documents, "affected fields", len(issues),
          "replacement characters", report["replacement_count"], "HTML files", html_files,
          "HTML replacement characters", report["html_replacement_count"])
    return bool(issues or html_issues)


if __name__ == "__main__":
    sys.exit(main())
