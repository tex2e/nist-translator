import json
import unittest
from copy import deepcopy
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


class Sp80053AStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / "data/sp800-53ar5-trans.json").read_text())
        cls.blocks = {b["id"]: b for b in cls.document["contents"]}

    def test_callouts_are_separate_and_previously_missing_ca03_statement_is_present(self):
        block = self.blocks["pdf-p0028-b0002"]
        en = BeautifulSoup(block["html"], "html.parser")
        ja = BeautifulSoup(block["html_ja"], "html.parser")
        rows = {tr.td.get_text(): tr.find_all("td")[1].get_text() for tr in en.table.find_all("tr") if tr.td.get_text()}
        self.assertIn("approved and managed using", rows["CA-03a."])
        self.assertIn("the interface characteristics", rows["CA-03b.[01]"])
        self.assertNotIn("Embedded Assignment", en.table.get_text())
        self.assertIn("Embedded Assignment", en.ul.get_text())
        self.assertIn("インターフェースの特性", ja.table.get_text())
        self.assertIn("了解覚書または合意覚書", ja.table.get_text())
        self.assertEqual(len(en.ul.find_all("li")), 4)

    def test_findings_keep_four_columns_blank_comments_and_s_o_values(self):
        block = self.blocks["pdf-p0731-b0001"]
        found = []
        for field in ("html", "html_ja"):
            rows = BeautifulSoup(block[field], "html.parser").table.find_all("tr")[2:]
            cells = [[td.get_text() for td in tr.find_all("td")] for tr in rows]
            self.assertEqual([len(row) for row in cells], [4] * 9)
            self.assertEqual([row[2] for row in cells], ["S", "S", "S", "O", "S", "O", "S", "S", "O"])
            self.assertEqual([cells[i][3] for i in (4, 6, 7)], ["", "", ""])
            self.assertIn("CP-03_ODP[04]", cells[8][3])
            found.append([row[0] for row in cells])
        self.assertEqual(found[0], found[1])

    def test_recorded_raw_fragments_do_not_replace_structured_tables_or_diagram(self):
        from src.nist_translater.pdf_source_repairs import preserve_source_repairs
        record = self.document["source_repairs"]
        raw = {"source_sha256": record["source_sha256"], "included_pages": [28, 47, 731],
               "contents": deepcopy(record["structural_review_20261024"]["original_blocks"])}
        current = preserve_source_repairs(self.document, raw)
        found = {b["id"]: b for b in current["contents"]}
        for bid in ["pdf-p0028-b0002", "pdf-p0047-b0002", "pdf-p0731-b0001"]:
            self.assertEqual(found[bid], self.blocks[bid])
        self.assertNotIn("pdf-p0047-b0003", found)
        self.assertEqual(found["pdf-p0047-b0002"]["kind"], "figure")
