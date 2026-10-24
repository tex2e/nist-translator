import json
import unittest
from copy import deepcopy
from pathlib import Path

from bs4 import BeautifulSoup
from src.nist_translater.pdf_source_repairs import preserve_source_repairs

ROOT = Path(__file__).resolve().parents[1]


class GoalMathRepairTests(unittest.TestCase):
    @staticmethod
    def document(slug):
        return json.loads((ROOT / "data" / f"sp800-{slug}-trans.json").read_text())

    def test_inventory_formula_does_not_claim_the_following_page(self):
        blocks = {b["id"]: b for b in self.document("128")["contents"]}
        formula = blocks["pdf-p0037-r0017"]
        self.assertEqual(formula["kind"], "math")
        self.assertEqual([r["page"] for r in formula["source_refs"]], [37])
        self.assertIn(r"\mathrm{SC}_n", formula["html"])
        self.assertIn(r"\mathrm{SC}_n", formula["html_ja"])
        self.assertEqual([r["page"] for r in blocks["pdf-p0037-r0019"]["source_refs"]], [37, 38])
        self.assertLess(blocks["pdf-p0037-r0015"]["source_refs"][0]["bbox"][3],
                        blocks["pdf-p0037-r0016"]["source_refs"][0]["bbox"][1])

    def test_sensitivity_tail_is_not_reintroduced_as_an_untranslated_fragment(self):
        previous = self.document("168")
        raw = {"source_sha256": previous["source_repairs"]["source_sha256"],
               "included_pages": [16], "contents": [{
                   "id": "raw-sensitivity-tail", "kind": "paragraph", "html": "features being correlated",
                   "html_ja": "", "status": "untranslated", "extraction_status": "needs_review",
                   "source_hash": "new-raw-tail", "source_page": 16,
                   "source_refs": [{"page": 16, "bbox": [126, 73.5, 493.5, 122.2]}]}]}
        current = preserve_source_repairs(previous, raw)
        blocks = {b["id"]: b for b in current["contents"]}
        self.assertNotIn("raw-sensitivity-tail", blocks)
        block = blocks["pdf-p0015-r0015"]
        self.assertEqual(len(BeautifulSoup(block["html"], "html.parser").find_all("p")), 2)
        self.assertIn("single-common-block", block["html"])
        self.assertEqual(block["status"], "reviewed")

    def test_original_ceiling_and_rounding_inconsistency_are_preserved_explicitly(self):
        blocks = {b["id"]: b for b in self.document("168")["contents"]}
        ratio = blocks["pdf-p0019-math-004"]
        for field in ("html", "html_ja"):
            self.assertIn(r"\left\lceil", ratio[field])
            self.assertIn(r"\right\rceil", ratio[field])
            self.assertIn(r"\min", ratio[field])
            self.assertIn(r"\mathit{f1}", ratio[field])
            self.assertNotIn(r"\lfloor", ratio[field])
        self.assertIn("1000000", ratio["math_review_notes"])
        self.assertIn("0.01%", ratio["math_review_notes"])
        self.assertIn("一致しない", ratio["math_review_notes"])
        self.assertEqual(blocks["pdf-p0019-r0009"]["math_duplicate_of"], "pdf-p0019-math-013")

    def test_piv_table_retains_year_columns_and_separates_footnote_three(self):
        block = next(b for b in self.document("78r5")["contents"] if b["id"] == "pdf-p0015-b0002")
        for field in ("html", "html_ja"):
            table = BeautifulSoup(block[field], "html.parser").table
            rows = table.find_all("tr")
            self.assertEqual(len(rows), 7)
            self.assertTrue(all(len(row.find_all("td")) == 3 for row in rows))
            self.assertIn("2030", rows[0].find_all("td")[1].get_text())
            self.assertIn("2031", rows[0].find_all("td")[2].get_text())
            self.assertEqual(rows[3].sup.get_text(), "3")
            self.assertTrue(rows[3].find_all("td")[1].get_text().startswith("3TDEA3"))
            self.assertNotIn("3TDEA", rows[3].find_all("td")[2].get_text())
        self.assertEqual(block["extraction_status"], "verified")

    def test_rule_predicate_and_attribute_arguments_remain_one_formula(self):
        formula = next(b for b in self.document("95")["contents"] if b["id"] == "pdf-p0050-r0007")
        self.assertEqual(formula["kind"], "math")
        for field in ("html", "html_ja"):
            self.assertEqual(formula[field].count(r"\leftarrow"), 1)
            self.assertEqual(formula[field].count(r"\operatorname{ATTR}"), 3)
            self.assertIn(r"\operatorname{can\_access}(s,r,e)", formula[field])
        note = next(b for b in self.document("95")["contents"] if b["id"] == "pdf-p0050-r0006")
        self.assertIn("<sup>38</sup>", note["html"])
        self.assertIn("<sup>38</sup>", note["html_ja"])

    def test_all_four_repairs_survive_raw_archives(self):
        for slug in ("128", "78r5", "95", "168"):
            with self.subTest(slug=slug):
                previous = self.document(slug)
                record = previous["source_repairs"]
                raw = {"source_sha256": record["source_sha256"],
                       "included_pages": record["pages"],
                       "contents": deepcopy(record["original_blocks"])}
                current = preserve_source_repairs(previous, raw)
                expected = {b["id"]: b for b in previous["contents"] if b["source_page"] in record["pages"]}
                found = {b["id"]: b for b in current["contents"]}
                self.assertEqual(found, expected)
