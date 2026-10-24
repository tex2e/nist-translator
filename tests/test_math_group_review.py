import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.nist_translater.render import build_site
from src.nist_translater.translation import audit_translations, math_group_review_hash

ROOT = Path(__file__).resolve().parents[1]


class MathGroupReviewTests(unittest.TestCase):
    def setUp(self):
        self.group = {"id": "g", "members": ["m"], "tex": r"\[x=1\]",
                      "source_hashes": {"m": "source"},
                      "prefix_html": "<p>Source note.</p>",
                      "prefix_html_ja": "<p>原本注記。</p>"}
        self.document = {
            "title": {"text": "Test"}, "source_url": "https://example.invalid/source.pdf",
            "source_format": "pdf", "math_groups": [self.group],
            "contents": [{"id": "m", "kind": "math", "html": r"\[x=1\]",
                          "html_ja": r"\[x=1\]", "source_hash": "source",
                          "source_page": 1, "source_refs": [{"page": 1}],
                          "status": "reviewed", "extraction_status": "verified"}],
        }

    def certify(self):
        self.group["status"] = "reviewed"
        self.group["translation_review"] = {"reviewer": "gpt-6.1-sol", "mode": "self-review",
                                            "content_hash": math_group_review_hash(self.group)}

    def render(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "page.html"
            build_site(self.document, {}, ROOT / "templates/page.html", output)
            return output.read_text()

    def test_only_explicit_group_review_removes_pending_label(self):
        self.assertIn("未レビュー訳", self.render())
        self.certify()
        self.assertNotIn("未レビュー訳", self.render())

    def test_changes_to_formula_prefix_or_membership_invalidate_review(self):
        self.certify()
        original = deepcopy(self.group)
        for field, value in [("tex", r"\[x=2\]"), ("tex_ja", r"\[x=2\]"),
                             ("prefix_html", "<p>Changed.</p>"),
                             ("prefix_html_ja", "<p>変更。</p>")]:
            with self.subTest(field=field):
                self.group.clear()
                self.group.update(deepcopy(original))
                self.group[field] = value
                with self.assertRaisesRegex(ValueError, "group review"):
                    audit_translations(self.document)
        self.group.clear()
        self.group.update(original)
        self.group["members"] = ["m", "unknown"]
        with self.assertRaisesRegex(ValueError, "Invalid KaTeX group"):
            audit_translations(self.document)

    def test_pending_member_or_unverified_source_cannot_certify_group(self):
        self.certify()
        block = self.document["contents"][0]
        block["status"] = "draft"
        with self.assertRaisesRegex(ValueError, "group review"):
            audit_translations(self.document)
        block["extraction_status"] = "needs_review"
        with self.assertRaisesRegex(ValueError, "group review"):
            audit_translations(self.document)
