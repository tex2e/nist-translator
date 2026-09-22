import argparse
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .auto_translate import batches, translate_pending
from .parser import SOURCE_URL, parse_document
from .render import build_site
from .storage import read_json, write_json
from .translation import audit_translations, carry_translations, make_queue, merge_translations


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SOURCE = DATA / "sp800-63b.html"
DOCUMENT = DATA / "sp800-63b-trans.json"


def fetch():
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "nist-translater/0.1 (bilingual reading copy)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
        if response.status != 200 or not content:
            raise RuntimeError("NIST HTML could not be downloaded")
    if b"<html" not in content[:3000].lower():
        raise ValueError("Downloaded content does not look like HTML")
    # Keep the previous snapshot if the upstream page is incomplete or its structure changes.
    parse_document(content.decode("utf-8"))
    DATA.mkdir(parents=True, exist_ok=True)
    temp = SOURCE.with_suffix(".html.tmp")
    temp.write_bytes(content)
    temp.replace(SOURCE)
    print("Fetched", SOURCE, "(%d bytes)" % len(content))


def parse():
    if not SOURCE.exists():
        raise FileNotFoundError("Source missing. Run: python3 main.py fetch")
    try:
        document = parse_document(SOURCE.read_text(encoding="utf-8"))
        existing = read_json(DOCUMENT) if DOCUMENT.exists() else None
        document["created_at"] = (existing or {}).get("created_at", datetime.now(timezone.utc).isoformat())
        document["source_fetched_at"] = datetime.fromtimestamp(SOURCE.stat().st_mtime, timezone.utc).isoformat()
        if existing:
            document = carry_translations(existing, document)
        elif (DATA / "blocks.json").exists() and (DATA / "ja.json").exists():
            # One-time migration from the previous split data files.
            old_blocks = read_json(DATA / "blocks.json")
            old_translations = read_json(DATA / "ja.json")
            old_blocks["contents"] = old_blocks.pop("blocks")
            old_blocks.pop("headings", None)
            old_blocks["title"] = {"text": old_blocks.get("title", "NIST SP 800-63B-4"), "html_ja": ""}
            old_blocks["number"] = "SP 800-63B-4"
            old_blocks["updated_by"] = ""
            for block in old_blocks["contents"]:
                entry = old_translations.get(block["id"], {})
                block["html_ja"] = entry.get("ja", "")
                block["status"] = entry.get("status", "untranslated" if block["kind"] != "table" else "source_only")
            document = carry_translations(old_blocks, document)
        changed = audit_translations(document)
        write_json(DOCUMENT, document)
    except Exception:
        # Keep the temporary download for diagnosis or a retry when parsing fails.
        raise
    else:
        SOURCE.unlink()
    print("Parsed %d blocks and %d headings." % (
        len(document["contents"]), sum(block["kind"] == "heading" for block in document["contents"])))
    print("Translations requiring review: %d changed." % changed)


def build():
    if not DOCUMENT.exists():
        raise FileNotFoundError("Blocks missing. Run: python3 main.py parse")
    document = read_json(DOCUMENT)
    audit_translations(document)
    output = ROOT / "site"
    output.mkdir(exist_ok=True)
    build_site(document, {"fetched_at": document.get("source_fetched_at")},
               ROOT / "templates" / "page.html", output / "sp800-63b.html")
    shutil.copyfile(ROOT / "static" / "style.css", output / "style.css")
    print("Built", output / "sp800-63b.html")


def import_file(path):
    document = read_json(DOCUMENT)
    incoming = read_json(path)
    count = merge_translations(document, incoming)
    audit_translations(document)
    write_json(DOCUMENT, document)
    print("Imported %d draft translations." % count)


def translate(args):
    if args.limit < 0 or args.batch_size < 1 or args.max_chars < 1 or args.timeout < 1:
        raise ValueError("Translation limits must be positive (limit may be zero for all)")
    document = read_json(DOCUMENT)
    if args.dry_run:
        pending = make_queue(document)
        if args.limit:
            pending = pending[:args.limit]
        planned = list(batches(pending, args.batch_size, args.max_chars))
        print("Would translate %d blocks in %d CLI calls (%d English characters)." % (
            len(pending), len(planned), sum(len(item["html"]) for item in pending)))
        return
    count, selected = translate_pending(
        document, DOCUMENT, cli=args.cli, model=args.model,
        limit=args.limit, batch_size=args.batch_size, max_chars=args.max_chars,
        timeout=args.timeout, effort=args.effort,
    )
    print("Translated %d of %d selected blocks." % (count, selected))
    build()


def main():
    cli = argparse.ArgumentParser(description="Build a bilingual NIST SP 800-63B reading site")
    cli.add_argument("command", choices=["fetch", "parse", "build", "update", "import", "translate"])
    cli.add_argument("--file", type=Path, help="JSON file for the import command")
    cli.add_argument("--cli", choices=["agy", "gemini"], default="agy", help="translation CLI (default: agy)")
    cli.add_argument("--model", help="model passed to the translation CLI")
    cli.add_argument("--effort", choices=["low", "medium", "high"],
                     help="agy reasoning effort (lower is faster)")
    cli.add_argument("--limit", type=int, default=10, help="maximum blocks per run; 0 means all")
    cli.add_argument("--batch-size", type=int, default=8, help="maximum blocks per CLI call")
    cli.add_argument("--max-chars", type=int, default=5000, help="maximum English characters per CLI call")
    cli.add_argument("--timeout", type=int, default=180, help="seconds per CLI call")
    cli.add_argument("--dry-run", action="store_true", help="show planned calls without using the CLI")
    args = cli.parse_args()
    if args.command in ("fetch", "update"):
        fetch()
    if args.command in ("parse", "update"):
        parse()
    if args.command in ("build", "update"):
        build()
    if args.command == "import":
        if args.file is None:
            cli.error("import requires --file")
        import_file(args.file)
    if args.command == "translate":
        translate(args)
