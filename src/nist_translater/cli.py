import argparse
import hashlib
import io
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .auto_translate import batches, translate_pending
from .documents import DOCUMENTS, document_paths, get_document
from .index_page import build_translation_index
from .parser import parse_document
from .pdf_parser import parse_pdf_document
from .pdf_math import preserve_sp800_22_math, restore_extraction
from .render import build_site
from .storage import read_json, write_json
from .translation import audit_translations, carry_translations, make_queue, merge_translations


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SOURCE = DATA / "sp800-63b.html"  # Backwards-compatible aliases for the original volume.
DOCUMENT = DATA / "sp800-63b-trans.json"


def _compact_table_urls(value):
    def compact_url(match):
        cell = match.group(1)
        if cell.strip().startswith(("http://", "https://")):
            cell = re.sub(r"\s+", "", cell)
        return "<td>%s</td>" % cell

    return re.sub(r"<td>(.*?)</td>", compact_url, value)


def fetch(document_key="63b"):
    spec = get_document(document_key)
    paths = document_paths(ROOT, document_key)
    source = paths["source"]
    request = urllib.request.Request(
        spec["source_url"],
        headers={"User-Agent": "nist-translater/0.1 (bilingual reading copy)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
        if response.status != 200 or not content:
            raise RuntimeError("NIST HTML could not be downloaded")
    if spec.get("source_format") == "pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("Downloaded content does not look like PDF")
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                if not pdf.pages:
                    raise ValueError("Downloaded PDF has no pages")
        except ImportError as error:
            raise RuntimeError("PDF support requires pdfplumber; install requirements.txt") from error
    else:
        if b"<html" not in content[:3000].lower():
            raise ValueError("Downloaded content does not look like HTML")
        # Keep the previous snapshot if the upstream page is incomplete or its structure changes.
        parse_document(content.decode("utf-8"), number=spec["number"], source_url=spec["source_url"])
    DATA.mkdir(parents=True, exist_ok=True)
    temp = source.with_suffix(source.suffix + ".tmp")
    temp.write_bytes(content)
    temp.replace(source)
    print("Fetched", source, "(%d bytes)" % len(content))


def parse(document_key="63b", pages=None):
    spec = get_document(document_key)
    paths = document_paths(ROOT, document_key)
    source, document_path = paths["source"], paths["json"]
    if not source.exists():
        raise FileNotFoundError("Source missing. Run: python3 main.py fetch")
    try:
        if spec.get("source_format") == "pdf":
            document = parse_pdf_document(
                source, number=spec["number"], source_url=spec["source_url"], pages=pages,
                asset_dir=ROOT / "html" / "assets" / spec["slug"],
                asset_prefix="assets/" + spec["slug"],
            )
            for source_text, replacement in spec.get("pdf_text_replacements", {}).items():
                for block in document["contents"]:
                    if source_text not in block["html"]:
                        continue
                    block["html"] = block["html"].replace(source_text, replacement)
                    block["source_hash"] = hashlib.sha256((
                        block["kind"] + "\n" + block["html"] + "\n" +
                        block.get("source_image_hash", "")
                    ).encode("utf-8")).hexdigest()[:16]
            if spec.get("compact_pdf_table_urls"):
                for block in document["contents"]:
                    if block["kind"] != "table":
                        continue
                    normalized = _compact_table_urls(block["html"])
                    if normalized != block["html"]:
                        block["html"] = normalized
                        block["source_hash"] = hashlib.sha256((
                            block["kind"] + "\n" + block["html"] + "\n" +
                            block.get("source_image_hash", "")
                        ).encode("utf-8")).hexdigest()[:16]
                    block["source_hash"] = hashlib.sha256((
                        block["kind"] + "\n" + block["html"] + "\n" +
                        block.get("source_image_hash", "")
                    ).encode("utf-8")).hexdigest()[:16]
        else:
            if pages is not None:
                raise ValueError("--pages is supported only for PDF documents")
            document = parse_document(source.read_text(encoding="utf-8"),
                                      number=spec["number"], source_url=spec["source_url"])
        document["subtitle"] = spec["title"]
        if "title_ja" in spec:
            document["title"]["html_ja"] = spec["title_ja"]
        if "subtitle_ja" in spec:
            document["subtitle_ja"] = spec["subtitle_ja"]
        document["description"] = spec["description"]
        document["pdf_url"] = spec["pdf_url"]
        document["series"] = spec.get("series", "Digital Identity Guidelines · Revision 4")
        if spec.get("catalog_record_url"):
            document["catalog_record_url"] = spec["catalog_record_url"]
        existing = read_json(document_path) if document_path.exists() else None
        document["created_at"] = (existing or {}).get("created_at", datetime.now(timezone.utc).isoformat())
        document["source_fetched_at"] = datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat()
        if existing:
            previous = restore_extraction(existing) if spec.get("preserve_pdf_math") else existing
            document = carry_translations(previous, document)
        elif document_key == "63b" and (DATA / "blocks.json").exists() and (DATA / "ja.json").exists():
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
        if spec.get("compact_pdf_table_urls"):
            for block in document["contents"]:
                if block["kind"] == "table" and block["html_ja"]:
                    block["html_ja"] = _compact_table_urls(block["html_ja"])
        if spec.get("preserve_pdf_math"):
            document = preserve_sp800_22_math(
                document, source, ROOT / "html" / "assets" / spec["slug"],
                "assets/" + spec["slug"], previous_document=existing,
            )
        changed = audit_translations(document)
        write_json(document_path, document)
    except Exception:
        # Keep the temporary download for diagnosis or a retry when parsing fails.
        raise
    else:
        if spec.get("source_format") != "pdf":
            source.unlink()
    print("Parsed %d blocks and %d headings." % (
        len(document["contents"]), sum(block["kind"] == "heading" for block in document["contents"])))
    print("%s translations requiring review: %d changed." % (spec["number"], changed))


def release_date(spec):
    """Publication date as YYYY-MM-DD (or YYYY-MM): the document entry, else the SP 800 catalog."""
    from datetime import datetime
    value = spec.get("release_date")
    if not value:
        number = spec["number"].replace("SP ", "").replace(" (Update 1)", "")
        catalog = read_json(ROOT / "data" / "sp800-final-catalog.json")
        record = next((r for r in catalog["records"] if r.get("number") == number), None)
        value = record.get("release_date", "") if record else ""
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    return value or ""


def build(document_key="63b"):
    spec = get_document(document_key)
    paths = document_paths(ROOT, document_key)
    document_path, output_path = paths["json"], paths["html"]
    if not document_path.exists():
        raise FileNotFoundError("Blocks missing. Run: python3 main.py parse")
    document = read_json(document_path)
    document.setdefault("subtitle", spec["title"])
    document.setdefault("subtitle_ja", spec.get("subtitle_ja", ""))
    document.setdefault("description", spec["description"])
    document.setdefault("pdf_url", spec["pdf_url"])
    document.setdefault("source_format", spec.get("source_format", "html"))
    document.setdefault("series", spec.get("series", "Digital Identity Guidelines · Revision 4"))
    document["home_url"] = spec.get("home_url", "index.html")
    document["release_date"] = release_date(spec)
    # The original: the HTML page that was translated, or the official PDF (DOI)
    document["orig_url"] = spec["source_url"] if spec.get("source_format", "html") != "pdf" else spec["pdf_url"]
    summary_path = document_path.with_name(document_path.name.replace("-trans.json", "-summary.json"))
    document["summary"] = read_json(summary_path)["summary"] if summary_path.exists() else []
    audit_translations(document)
    output = output_path.parent
    output.mkdir(exist_ok=True)
    build_site(document, {"fetched_at": document.get("source_fetched_at")},
               ROOT / "templates" / "page.html", output_path)
    shutil.copyfile(ROOT / "static" / "style.css", output / "style.css")
    shutil.copyfile(ROOT / "static" / "header.css", output / "header.css")
    if (ROOT / "static" / "vendor" / "katex").exists():
        shutil.copytree(ROOT / "static" / "vendor" / "katex", output / "vendor" / "katex", dirs_exist_ok=True)
    print("Built", output_path)
    if spec.get("family") == "fips":
        from .fips_index import build_fips_index
        print("Built", build_fips_index(ROOT))
    else:
        print("Built", build_translation_index(ROOT))


def import_file(path, document_key="63b"):
    document = read_json(document_paths(ROOT, document_key)["json"])
    incoming = read_json(path)
    count = merge_translations(document, incoming)
    audit_translations(document)
    write_json(document_paths(ROOT, document_key)["json"], document)
    print("Imported %d draft translations." % count)


def translate(args):
    if args.limit < 0 or args.batch_size < 1 or args.max_chars < 1 or args.timeout < 1:
        raise ValueError("Translation limits must be positive (limit may be zero for all)")
    document_path = document_paths(ROOT, args.document)["json"]
    document = read_json(document_path)
    if args.dry_run:
        pending = make_queue(document)
        if args.limit:
            pending = pending[:args.limit]
        planned = list(batches(pending, args.batch_size, args.max_chars))
        print("Would translate %d blocks in %d CLI calls (%d English characters)." % (
            len(pending), len(planned), sum(len(item["html"]) for item in pending)))
        return
    count, selected = translate_pending(
        document, document_path, cli=args.cli, model=args.model,
        limit=args.limit, batch_size=args.batch_size, max_chars=args.max_chars,
        timeout=args.timeout, effort=args.effort,
    )
    print("Translated %d of %d selected blocks." % (count, selected))
    build(args.document)


def parse_pages(value):
    if value is None:
        return None
    pages = set()
    for part in value.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:-(\d+))?\s*", part)
        if not match:
            raise ValueError("Invalid PDF page range: " + part)
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start:
            raise ValueError("Invalid PDF page range: " + part)
        pages.update(range(start, end + 1))
    return sorted(pages)


def main():
    cli = argparse.ArgumentParser(description="Build bilingual reading sites for NIST SP 800-63 Revision 4")
    cli.add_argument("command", choices=["fetch", "parse", "build", "update", "import", "translate", "index"])
    cli.add_argument("--document", choices=DOCUMENTS, default="63b",
                     help="volume to process (default: 63b)")
    cli.add_argument("--file", type=Path, help="JSON file for the import command")
    cli.add_argument("--pages", help="PDF page numbers for a preview, e.g. 7-8,15,21")
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
        fetch(args.document)
    if args.command in ("parse", "update"):
        parse(args.document, pages=parse_pages(args.pages))
    if args.command in ("build", "update"):
        build(args.document)
    if args.command == "import":
        if args.file is None:
            cli.error("import requires --file")
        import_file(args.file, args.document)
    if args.command == "translate":
        translate(args)
    if args.command == "index":
        print("Built", build_translation_index(ROOT))
