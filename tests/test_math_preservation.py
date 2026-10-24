import unittest
from copy import deepcopy

from src.nist_translater.translation import carry_translations


class MathPreservationTests(unittest.TestCase):
    def setUp(self):
        self.raw = {"id": "raw-a", "kind": "paragraph", "html": "x squared",
                    "html_ja": "", "status": "untranslated", "source_hash": "raw-hash",
                    "source_page": 2, "source_refs": [{"page": 2, "bbox": [10, 20, 30, 40]}]}
        self.formula = dict(deepcopy(self.raw), id="math-a", kind="math", html=r"\[x^2\]",
                            html_ja=r"\[x^2\]", source_hash="math-hash", status="reviewed",
                            extraction_status="verified", replaces=["raw-a"],
                            math_source_hashes={"raw-a": "raw-hash"},
                            translation_review={"mode": "self-review"},
                            math_reconstruction={"method": "editorial_structure"})
        self.previous = {"source_format": "pdf", "source_sha256": "pdf-hash",
                         "contents": [self.formula]}
        self.current = {"source_format": "pdf", "source_sha256": "pdf-hash",
                        "included_pages": [2], "contents": [self.raw]}

    def test_exact_raw_sources_keep_formula_translation_and_review(self):
        result = carry_translations(self.previous, self.current)
        self.assertEqual(result["contents"], [self.formula])
        result["contents"][0]["translation_review"]["mode"] = "changed"
        self.assertEqual(self.formula["translation_review"]["mode"], "self-review")

    def test_changed_or_missing_member_fails_before_changing_contents(self):
        for mutation in ("changed", "missing", "missing-evidence"):
            with self.subTest(mutation=mutation):
                current, previous = deepcopy(self.current), deepcopy(self.previous)
                if mutation == "changed":
                    current["contents"][0]["source_hash"] = "different"
                elif mutation == "missing":
                    current["contents"] = []
                else:
                    previous["contents"][0].pop("math_source_hashes")
                snapshot = deepcopy(current)
                with self.assertRaisesRegex(ValueError, "source changed or incomplete"):
                    carry_translations(previous, current)
                self.assertEqual(current, snapshot)

    def test_pdf_change_or_missing_hash_never_inherits_old_math(self):
        for value in ("new-pdf", None):
            current = deepcopy(self.current)
            current["source_sha256"] = value
            with self.assertRaisesRegex(ValueError, "PDF changed or hash missing"):
                carry_translations(self.previous, current)

    def test_partial_other_page_does_not_reintroduce_math(self):
        self.current["included_pages"] = [3]
        self.current["contents"][0]["source_page"] = 3
        result = carry_translations(self.previous, self.current)
        self.assertEqual([b["id"] for b in result["contents"]], ["raw-a"])

    def test_already_retained_formula_keeps_reconstruction_record(self):
        self.current["contents"] = [deepcopy(self.formula)]
        self.current["contents"][0].pop("math_reconstruction")
        self.assertEqual(carry_translations(self.previous, self.current)["contents"], [self.formula])

    def test_two_formulae_cannot_hide_the_same_raw_source(self):
        self.previous["contents"].append(dict(deepcopy(self.formula), id="math-b"))
        snapshot = deepcopy(self.current)
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            carry_translations(self.previous, self.current)
        self.assertEqual(self.current, snapshot)
