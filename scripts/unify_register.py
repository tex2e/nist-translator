"""Rewrite polite-register (desu/masu) translations in the plain register.

The site's translations are mostly in the plain (da/dearu) register; this
converts the rest without touching their content.

    python scripts/unify_register.py export [--size N] OUT_DIR [KEY ...]
    python scripts/unify_register.py apply  OUT_DIR

``export`` writes ``<key>.<nnn>.batch.json`` with the polite translations; a
rewriter answers each with ``<key>.<nnn>.result.json``: a JSON array of
``{"id", "ja"}``. ``apply`` stores a rewrite only if nothing but the wording of
sentence endings can have changed: same HTML tags, same LaTeX, same numbers and
Latin-script tokens in the same order, and nearly the same text otherwise. The
translation status is left as it is.
"""

import argparse
import difflib
import html
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nist_translater.storage import read_json, write_json  # noqa: E402
from nist_translater.translation import (  # noqa: E402
    NORMATIVE, assert_same_html_structure, audit_translations)

TAG = re.compile(r"<[^>]+>")
POLITE = re.compile(
    r"(です|ます|ません|でした|ました|ください|でしょう|ましょう)(?=[。）)」、]|$|（|\s*\()")
FORMULA = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.S)
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/%+\-]*")
MAX_BATCH_CHARS = 30000


def _plain_text(value):
    return html.unescape(TAG.sub("", value))


def is_polite(japanese):
    return bool(POLITE.search(_plain_text(japanese)))


def _keys(names):
    return names or sorted(path.name[:-len("-trans.json")]
                           for path in (ROOT / "data").glob("*-trans.json"))


def export(out_dir, size, names):
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = blocks = 0
    for key in _keys(names):
        document = read_json(ROOT / "data" / (key + "-trans.json"))
        items = [{"id": block["id"], "ja": block["html_ja"]}
                 for block in document["contents"]
                 if block.get("status") in {"draft", "reviewed"} and
                 is_polite(block.get("html_ja") or "")]
        groups, chars = [[]], 0
        for item in items:
            if groups[-1] and (len(groups[-1]) >= size or
                               chars + len(item["ja"]) > MAX_BATCH_CHARS):
                groups.append([])
                chars = 0
            groups[-1].append(item)
            chars += len(item["ja"])
        for index, group in enumerate(group for group in groups if group):
            write_json(out_dir / ("%s.%03d.batch.json" % (key, index + 1)), {"blocks": group})
            batches += 1
        blocks += len(items)
    print("Exported %d blocks in %d batches to %s" % (blocks, batches, out_dir))


def _problem(block, old, new):
    """Why a rewrite may have changed more than the register, or None."""
    if not isinstance(new, str) or not new.strip():
        return "empty"
    try:
        assert_same_html_structure(old, new)
        assert_same_html_structure(block["html"], new, preserve_math=block["kind"] == "math")
    except ValueError as error:
        return str(error)
    if FORMULA.findall(html.unescape(old)) != FORMULA.findall(html.unescape(new)):
        return "LaTeX changed"
    if Counter(NORMATIVE.findall(old)) != Counter(NORMATIVE.findall(new)):
        return "requirement keywords changed"
    without_math_old = FORMULA.sub(" ", _plain_text(old))
    without_math_new = FORMULA.sub(" ", _plain_text(new))
    if TOKEN.findall(without_math_old) != TOKEN.findall(without_math_new):
        return "numbers or Latin-script tokens changed"
    if len(without_math_old) < 40:
        # In a short fragment the sentence ending is most of the text, so a
        # similarity ratio says nothing; bound the change in length instead.
        if abs(len(without_math_new) - len(without_math_old)) > 6:
            return "short text changed too much"
        return None
    ratio = difflib.SequenceMatcher(None, without_math_old, without_math_new,
                                    autojunk=False).ratio()
    if ratio < 0.8 or not 0.8 <= len(without_math_new) / max(1, len(without_math_old)) <= 1.2:
        return "text changed too much (similarity %.2f)" % ratio
    return None


def apply(out_dir):
    counts, rejected, answers = Counter(), [], {}
    for batch_path in sorted(out_dir.glob("*.batch.json")):
        path = batch_path.with_name(batch_path.name.replace(".batch.json", ".result.json"))
        if not path.exists():
            counts["batches_without_result"] += 1
            continue
        try:
            result = {item["id"]: item["ja"] for item in read_json(path)}
            batch = {item["id"]: item["ja"] for item in read_json(batch_path)["blocks"]}
        except (ValueError, KeyError, TypeError) as error:
            rejected.append("%s: %s" % (path.name, error))
            continue
        key = batch_path.name.split(".")[0]
        for identifier, old in batch.items():
            answers.setdefault(key, {})[identifier] = (old, result.get(identifier))
    for key, items in sorted(answers.items()):
        path = ROOT / "data" / (key + "-trans.json")
        document = read_json(path)
        blocks = {block["id"]: block for block in document["contents"]}
        for identifier, (old, new) in items.items():
            block = blocks.get(identifier)
            # The translation may have been edited since the export.
            if block is None or block.get("html_ja") != old:
                counts["changed_since_export"] += 1
                continue
            problem = "no answer" if new is None else _problem(block, old, new)
            if problem:
                counts["rejected"] += 1
                rejected.append("%s %s: %s" % (key, identifier, problem))
                continue
            if new == old:
                counts["unchanged"] += 1
                continue
            block["html_ja"] = new
            counts["still_polite" if is_polite(new) else "converted"] += 1
        audit_translations(document)
        write_json(path, document)
    print(" ".join("%s=%d" % item for item in sorted(counts.items())) or "nothing applied")
    for line in rejected[:40]:
        print("REJECTED", line)
    if len(rejected) > 40:
        print("... and %d more rejected" % (len(rejected) - 40))


def main():
    cli = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = cli.add_subparsers(dest="command", required=True)
    exporter = commands.add_parser("export")
    exporter.add_argument("--size", type=int, default=60, help="blocks per batch")
    exporter.add_argument("out_dir", type=Path)
    exporter.add_argument("keys", nargs="*")
    applier = commands.add_parser("apply")
    applier.add_argument("out_dir", type=Path)
    args = cli.parse_args()
    if args.command == "export":
        export(args.out_dir, args.size, args.keys)
    else:
        apply(args.out_dir)


if __name__ == "__main__":
    main()
