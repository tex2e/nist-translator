import unittest
from copy import deepcopy

from src.nist_translater.translation import carry_translations


class TranslationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.block = {"id": "p1", "kind": "paragraph", "source_hash": "original",
                      "html": "A source paragraph.", "html_ja": "原文の段落。",
                      "status": "reviewed", "extraction_status": "verified",
                      "source_page": 1, "source_refs": [{"page": 1, "bbox": [1, 2, 3, 4]}],
                      "translation_check": "gpt-self-review",
                      "translation_review": {"source_hash": "original", "mode": "self-review"},
                      "translation_reuse": {"donor_id": "donor", "recipient_review": "self-reviewed"},
                      "unverified_source_review_history": [{"previous_review": {"translation_check": "claude-review"}}]}
        self.previous = {"source_format": "pdf", "contents": [self.block]}

    def raw(self):
        block = {key: deepcopy(value) for key, value in self.block.items()
                 if not key.startswith("translation_") and key != "unverified_source_review_history"}
        block.update(html_ja="", status="untranslated", extraction_status="needs_review")
        return {"source_format": "pdf", "contents": [block]}

    def test_exact_reparse_retains_review_and_reuse_evidence_without_aliasing(self):
        result = carry_translations(self.previous, self.raw())["contents"][0]
        for key in ("translation_check", "translation_review", "translation_reuse", "unverified_source_review_history"):
            self.assertEqual(result[key], self.block[key])
        self.assertEqual(result["status"], "reviewed")
        result["translation_review"]["mode"] = "changed"
        self.assertEqual(self.block["translation_review"]["mode"], "self-review")

    def test_changed_source_suspends_review_and_retains_old_text_with_provenance(self):
        raw = self.raw()
        raw["contents"][0].update(html="A changed source paragraph.", source_hash="changed")
        result = carry_translations(self.previous, raw)["contents"][0]
        self.assertEqual(result["status"], "stale")
        self.assertNotIn("translation_check", result)
        self.assertNotIn("translation_review", result)
        self.assertNotIn("translation_reuse", result)
        history = result["translation_review_history"][-1]
        self.assertEqual(history["html"], self.block["html"])
        self.assertEqual(history["html_ja"], self.block["html_ja"])
        self.assertEqual(history["previous_review"]["translation_reuse"], self.block["translation_reuse"])
        self.assertEqual(result["unverified_source_review_history"], self.block["unverified_source_review_history"])

    def test_new_pdf_version_does_not_inherit_approval_for_identical_extracted_text(self):
        self.previous["source_sha256"] = "old-pdf"
        raw = self.raw()
        raw["source_sha256"] = "new-pdf"
        result = carry_translations(self.previous, raw)["contents"][0]
        self.assertEqual(result["extraction_status"], "needs_review")
        self.assertEqual(result["status"], "stale")
        self.assertNotIn("translation_review", result)
        self.assertEqual(result["translation_review_history"][-1]["reason"], "source_pdf_changed")
        self.assertEqual(result["translation_review_history"][-1]["previous_pdf_sha256"], "old-pdf")
        self.assertEqual(result["translation_review_history"][-1]["current_pdf_sha256"], "new-pdf")

    def test_same_pdf_keeps_source_proof_without_aliasing(self):
        self.previous["source_sha256"] = "same-pdf"
        evidence = {"extraction_check": "visual-page", "page_check": {"page_proof": "matches_original"},
                    "fragment_reviewed": True, "structure_recheck": {"result": "ok"}}
        self.block.update(deepcopy(evidence))
        raw = self.raw()
        raw["source_sha256"] = "same-pdf"
        for key in evidence:
            raw["contents"][0].pop(key, None)
        result = carry_translations(self.previous, raw)["contents"][0]
        for key, value in evidence.items():
            self.assertEqual(result[key], value)
        result["page_check"]["page_proof"] = "changed"
        self.assertEqual(self.block["page_check"]["page_proof"], "matches_original")

    def test_changed_source_or_pdf_does_not_inherit_source_proof(self):
        self.block.update(extraction_check="visual-page", page_check={"page_proof": "matches_original"})
        self.previous["source_sha256"] = "same-pdf"
        for change in ("source", "pdf", "missing-hash"):
            raw = self.raw()
            raw["source_sha256"] = "same-pdf"
            for key in ("extraction_check", "page_check"):
                raw["contents"][0].pop(key, None)
            if change == "source":
                raw["contents"][0].update(html="Changed", source_hash="new")
            else:
                raw["source_sha256"] = "different" if change == "pdf" else None
            result = carry_translations(self.previous, raw)["contents"][0]
            with self.subTest(change=change):
                self.assertNotIn("extraction_check", result)
                self.assertNotIn("page_check", result)
