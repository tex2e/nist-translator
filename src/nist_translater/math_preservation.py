"""Keep canonical restored formulae only with exact PDF/source evidence."""

from copy import deepcopy


def preserve_restored_math(previous, current):
    """Plan every replacement before mutating a fresh PDF extraction.

    Raw IDs and hashes are intentionally required. Changed extraction needs
    comparison, rather than silently discarding editorial math or hiding new
    source text behind an old formula. Unrequested pages stay unrequested.
    """
    if current.get("source_format") != "pdf":
        return current
    pages = set(current.get("included_pages", []))
    formulae = [b for b in previous.get("contents", []) if b.get("kind") == "math"
                and (not pages or any(r["page"] in pages for r in b.get("source_refs", [])))]
    if not formulae:
        return current
    if not previous.get("source_sha256") or previous["source_sha256"] != current.get("source_sha256"):
        raise ValueError("PDF changed or hash missing; restored math requires a new original comparison")
    raw = {b["id"]: b for b in current["contents"]}
    removed, retained = set(), []
    for formula in formulae:
        same = raw.get(formula["id"])
        if (same and same.get("kind") == "math" and same.get("html") == formula["html"]
                and same.get("source_hash") == formula.get("source_hash")):
            members = [formula["id"]]
        else:
            members = formula.get("replaces", [])
            hashes = formula.get("math_source_hashes", {})
            if (not members or any(member not in raw or not hashes.get(member)
                                   or raw[member].get("source_hash") != hashes[member]
                                   for member in members)):
                raise ValueError("Restored math source changed or incomplete: " + formula["id"])
        if removed.intersection(members):
            raise ValueError("Overlapping restored math source: " + formula["id"])
        removed.update(members)
        retained.append(deepcopy(formula))
    # A formula already present under its own id (e.g. on a pinned page) keeps
    # its place; one rebuilt from raw fragments goes where its first fragment was.
    # Formulae with no such anchor are placed by position on the page.
    first = {}
    for formula in retained:
        members = [formula["id"]] if formula["id"] in raw and raw[formula["id"]].get("kind") == "math" \
            and raw[formula["id"]].get("html") == formula["html"] else formula.get("replaces", [])
        for member in members:
            first.setdefault(member, formula)
            break
    result, placed = [], set()
    for block in current["contents"]:
        formula = first.get(block["id"])
        if formula is not None and id(formula) not in placed:
            result.append(formula)
            placed.add(id(formula))
        elif block["id"] not in removed:
            result.append(block)
    rest = [f for f in retained if id(f) not in placed]
    if rest:
        result = sorted(result + rest, key=lambda b: (b["source_page"], b["source_refs"][0]["bbox"][1],
                                                      b["source_refs"][0]["bbox"][0]))
    current["contents"] = result
    return current
