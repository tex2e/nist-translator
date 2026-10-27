import unittest
from copy import deepcopy

from src.nist_translater.pdf_reconstruction import (
    preserve_pdf_reconstruction, source_fingerprint,
)
from src.nist_translater.translation import carry_translations


class PdfReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.raw = self.block("raw", "First. Second.")
        self.first = self.block("first", "First.")
        self.second = self.block("second", "Second.")
        # Shared legacy rectangles cannot determine editorial reading order.
        self.first.update(html_ja="最初。", status="reviewed", extraction_status="verified",
                          column_reflow={"rebuilt": True, "from": ["raw"]},
                          extraction_check="visual-page", translation_check="gpt-self-review")
        self.second.update(html_ja="", status="untranslated", extraction_status="needs_review")
        self.registry = {"source_sha256": "pdf", "pages": [{
            "page": 2,
            "raw_fingerprints": [source_fingerprint(self.raw)],
            "canonical_fingerprints": [source_fingerprint(self.first), source_fingerprint(self.second)],
        }]}
        self.previous = {"source_format": "pdf", "source_sha256": "pdf",
                         "contents": [self.first, self.second], "source_reconstructions": self.registry}
        self.current = {"source_format": "pdf", "source_sha256": "pdf",
                        "included_pages": [2], "contents": [deepcopy(self.raw)]}

    def block(self, identifier, text, page=2):
        return {"id": identifier, "kind": "paragraph", "html": text,
                "source_hash": identifier + "-hash", "source_page": page,
                "source_refs": [{"page": page, "bbox": [20, 40, 200, 100]}],
                "html_ja": "", "status": "untranslated", "extraction_status": "needs_review"}

    def test_split_ids_order_translation_and_unreviewed_neighbor_are_preserved(self):
        result = carry_translations(self.previous, self.current)
        self.assertEqual(result["contents"], self.previous["contents"])
        self.assertEqual(result["contents"][1]["status"], "untranslated")
        self.assertEqual(result["included_pages"], [2])
        result["contents"][0]["column_reflow"]["from"].append("changed")
        self.assertEqual(self.first["column_reflow"]["from"], ["raw"])

    def test_changed_raw_text_location_or_new_member_fails_without_mutation(self):
        for change in ("text", "location", "missing", "extra"):
            with self.subTest(change=change):
                current = deepcopy(self.current)
                if change == "text":
                    # A stale source_hash must not hide changed HTML.
                    current["contents"][0]["html"] = "New source text."
                elif change == "location":
                    current["contents"][0]["source_refs"][0]["bbox"][0] += 1
                elif change == "missing":
                    current["contents"] = []
                else:
                    current["contents"].append(self.block("new", "New material."))
                snapshot = deepcopy(current)
                with self.assertRaisesRegex(ValueError, "source changed or incomplete"):
                    preserve_pdf_reconstruction(self.previous, current)
                self.assertEqual(current, snapshot)

    def test_changed_canonical_source_or_members_require_registration_update(self):
        for change in ("html", "kind", "order", "missing"):
            previous = deepcopy(self.previous)
            if change in ("html", "kind"):
                previous["contents"][0][change] = "changed"
            elif change == "order":
                previous["contents"].reverse()
            else:
                previous["contents"].pop()
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "Canonical reconstruction"):
                preserve_pdf_reconstruction(previous, deepcopy(self.current))

    def test_pdf_change_or_missing_hash_does_not_inherit_layout(self):
        for value in (None, "new-pdf"):
            current = deepcopy(self.current)
            current["source_sha256"] = value
            with self.assertRaisesRegex(ValueError, "PDF changed or hash missing"):
                preserve_pdf_reconstruction(self.previous, current)

    def test_partial_request_keeps_other_pages_and_does_not_expand_coverage(self):
        other = self.block("other", "Another page.", page=3)
        self.current.update(included_pages=[3], contents=[other])
        result = preserve_pdf_reconstruction(self.previous, self.current)
        self.assertEqual(result["contents"], [other])
        self.assertEqual(result["included_pages"], [3])

    def test_validation_of_later_group_happens_before_any_replacement(self):
        later = self.block("later", "Later page.", page=3)
        self.registry["pages"].append({"page": 3, "raw_fingerprints": ["wrong"],
                                      "canonical_fingerprints": [source_fingerprint(later)]})
        self.previous["contents"].append(later)
        self.current["contents"].append(self.block("raw-later", "Later page.", page=3))
        self.current["included_pages"].append(3)
        snapshot = deepcopy(self.current)
        with self.assertRaisesRegex(ValueError, "source changed or incomplete"):
            preserve_pdf_reconstruction(self.previous, self.current)
        self.assertEqual(self.current, snapshot)

    def test_duplicate_groups_fail_and_already_retained_layout_is_idempotent(self):
        retained = deepcopy(self.current)
        retained["contents"] = deepcopy(self.previous["contents"])
        self.assertEqual(preserve_pdf_reconstruction(self.previous, retained)["contents"],
                         self.previous["contents"])
        self.registry["pages"].append(deepcopy(self.registry["pages"][0]))
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            preserve_pdf_reconstruction(self.previous, deepcopy(self.current))

    def test_new_canonical_translation_does_not_change_source_binding_or_approval(self):
        self.first.update(html_ja="更新した訳。", status="draft", translation_check="pending")
        result = carry_translations(self.previous, self.current)["contents"][0]
        self.assertEqual(result["html_ja"], "更新した訳。")
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["translation_check"], "pending")

    def test_later_explicit_source_repair_supersedes_old_registration(self):
        self.first.update(html="Corrected after a new original comparison.", source_hash="new-hash")
        self.previous["source_repairs"] = {"source_sha256": "pdf", "pages": [2],
                                           "original_blocks": [deepcopy(self.raw)]}
        result = carry_translations(self.previous, self.current)
        self.assertEqual(result["contents"], self.previous["contents"])
