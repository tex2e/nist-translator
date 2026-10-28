"""Re-extract every page of a PDF document and check that the canonical data survives.

    python scripts/check_full_reparse.py KEY [--out FILE]

Runs the real extractor on all pages into a temporary directory, carries the
canonical translations and repairs over (carry_translations, as `main.py
update` does) and compares the result with data/<key>-trans.json. The
canonical file is never written. Exit status 1 when any block is missing,
added or changed; the differences are written to --out.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.nist_translater.documents import get_document  # noqa: E402
from src.nist_translater.pdf_parser import parse_pdf_document  # noqa: E402
from src.nist_translater.source_quality import encoding_issues  # noqa: E402
from src.nist_translater.translation import carry_translations  # noqa: E402


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    cli.add_argument("key", help="document key without sp800- (e.g. 47r1)")
    cli.add_argument("--out", type=Path)
    cli.add_argument("--data", type=Path, help="check this JSON instead of data/<key>-trans.json")
    args = cli.parse_args()
    spec = get_document(args.key)
    name = "sp800-" + args.key if not args.key.startswith("fips-") else args.key
    path, pdf = args.data or ROOT / "data" / (name + "-trans.json"), ROOT / "data" / (name + ".pdf")
    before = path.read_bytes()
    document = json.loads(before)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != document["source_sha256"]:
        raise SystemExit("local PDF differs from the canonical source_sha256")
    with tempfile.TemporaryDirectory(prefix="nist-reparse-") as tmp:
        raw = parse_pdf_document(pdf, spec["number"], spec["source_url"], asset_dir=Path(tmp),
                                 asset_prefix="assets/" + spec.get("slug", args.key))
        result = carry_translations(document, raw)
    assert path.read_bytes() == before, "canonical file changed"
    old = {b["id"]: b for b in document["contents"]}
    new = {b["id"]: b for b in result["contents"]}
    missing = [old[k] for k in old if k not in new]
    added = [new[k] for k in new if k not in old]
    changed = [{"previous": old[k], "current": new[k]} for k in old if k in new and old[k] != new[k]]
    order_same = [b["id"] for b in document["contents"]] == [b["id"] for b in result["contents"]]
    def by_page(blocks):
        pages = {}
        for b in blocks:
            pages.setdefault(b["source_page"], []).append(b["id"])
        return pages
    old_pages, new_pages = by_page(document["contents"]), by_page(result["contents"])
    order_pages = sorted(p for p in old_pages if old_pages[p] != new_pages.get(p))
    report = {
        "document": name, "pdf_sha256": digest, "pages": len(raw["included_pages"]),
        "canonical_blocks": len(old), "reparse_blocks": len(new),
        "missing": len(missing), "added": len(added), "changed": len(changed),
        "order_identical": order_same,
        "order_pages": order_pages,
        "exact_match": document["contents"] == result["contents"],
        "encoding_issues": len(encoding_issues(result)),
        "affected_pages": sorted({b["source_page"] for b in missing + added}
                                 | {c["previous"]["source_page"] for c in changed}),
        "changed_fields": dict(Counter(k for c in changed for k in set(c["previous"]) | set(c["current"])
                                       if c["previous"].get(k) != c["current"].get(k))),
    }
    print(json.dumps(report, ensure_ascii=False))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"report": report, "missing": missing, "added": added,
                                        "changed": changed}, ensure_ascii=False, indent=2) + "\n")
    sys.exit(0 if report["exact_match"] else 1)


if __name__ == "__main__":
    main()
