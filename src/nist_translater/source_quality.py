"""Detect loss markers before damaged source can be certified or published."""

import html


def encoding_issues(document):
    issues = []
    for block in document.get("contents", []):
        if any(block.get(k) for k in (
                "page_furniture", "math_duplicate_of", "duplicate_artifact_of", "official_mark")):
            continue
        for field in ("html", "html_ja"):
            value = block.get(field, "")
            if not isinstance(value, str):
                continue  # The document schema validator reports invalid field types.
            count = html.unescape(value).count("\ufffd")
            if count:
                issues.append({"id": block["id"], "page": block.get("source_page"),
                               "field": field, "count": count})
    return issues


def assert_publishable_source(document):
    issues = encoding_issues(document)
    if issues:
        first = issues[0]
        raise ValueError("Replacement character in %s %s; repair source before publishing (%d affected fields)"
                         % (first["id"], first["field"], len(issues)))
