"""Retain registered editorial reconstruction of an unchanged PDF extraction."""

import hashlib
import json
from collections import defaultdict
from copy import deepcopy


def source_fingerprint(block):
    """Bind text, structure and location, independently of translation approval."""
    fields = ("id", "kind", "html", "source_hash", "source_page", "source_refs",
              "source_page_end", "level", "depth", "ordered", "ordinal",
              "source_image_hash")
    source = {key: block[key] for key in fields if key in block}
    value = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def preserve_pdf_reconstruction(previous, current):
    """Validate all selected groups before replacing their raw page records.

    Registration records a previously accepted editorial layout and a raw
    extraction baseline; it does not certify the text or change review states.
    Both sides are fingerprinted so a new extractor result cannot be hidden
    behind an old layout. Partial requests never add unrequested pages.
    """
    registry = previous.get("source_reconstructions")
    if not registry or current.get("source_format") != "pdf":
        return current
    pdf_hash = registry.get("source_sha256")
    if (not pdf_hash or previous.get("source_sha256") != pdf_hash
            or current.get("source_sha256") != pdf_hash):
        raise ValueError("PDF changed or hash missing; reconstruction requires a new comparison")
    included = set(current.get("included_pages", []))
    repairs = previous.get("source_repairs", {})
    explicitly_repaired = (set(repairs.get("pages", []))
                           if repairs.get("source_sha256") == pdf_hash else set())
    raw_pages, old_pages = defaultdict(list), defaultdict(list)
    for block in current["contents"]:
        raw_pages[block["source_page"]].append(block)
    for block in previous["contents"]:
        old_pages[block["source_page"]].append(block)
    replacements, seen = {}, set()
    for group in registry.get("pages", []):
        page = group["page"]
        if page in seen:
            raise ValueError("Overlapping PDF reconstruction page: " + str(page))
        seen.add(page)
        # A later explicit original comparison supersedes this legacy
        # registration. preserve_source_repairs already retained that page.
        if page not in included or page in explicitly_repaired:
            continue
        canonical = old_pages[page]
        expected = group.get("canonical_fingerprints", [])
        if not expected or [source_fingerprint(b) for b in canonical] != expected:
            raise ValueError("Canonical reconstruction changed or incomplete: " + str(page))
        raw = [source_fingerprint(b) for b in raw_pages[page]]
        # Idempotent when an upstream preservation step already retained the
        # exact source layout. Translations still come from the current canon.
        if raw != expected and raw != group.get("raw_fingerprints"):
            raise ValueError("PDF reconstruction source changed or incomplete: " + str(page))
        replacements[page] = deepcopy(canonical)
    result = []
    for page in sorted(set(raw_pages) | set(replacements)):
        result.extend(replacements.get(page, raw_pages[page]))
    current["contents"] = result
    current["source_reconstructions"] = deepcopy(registry)
    return current
