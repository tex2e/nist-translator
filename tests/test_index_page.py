import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from src.nist_translater import index_page
from src.nist_translater.fips_index import build_fips_index
from src.nist_translater.index_page import _natural, _render_row, build_translation_index


ENTRY = {
    "series": "sp800", "number": "SP 800-53 Rev. 5", "title": "Security <controls>",
    "title_ja": "セキュリティ管理策", "date": "2020-12-10", "withdrawn": False,
    "href": "sp800-53r5.html", "summary": "管理策のカタログ", "order": "1 " + _natural("SP 800-53 Rev. 5"),
}


class IndexPageTests(unittest.TestCase):
    def test_row_has_number_titles_and_date_only(self):
        soup = BeautifulSoup(_render_row(ENTRY), "html.parser")
        cells = soup.find_all("td")
        self.assertEqual([cell["class"][0] for cell in cells], ["number", "title", "date"])
        self.assertEqual(soup.select_one(".number a")["href"], "sp800-53r5.html")
        self.assertIn("Security <controls>", soup.get_text())
        self.assertIsNone(soup.find("controls"))
        self.assertEqual(soup.time["datetime"], "2020-12-10")
        self.assertEqual(soup.tr["data-series"], "sp800")
        self.assertEqual(soup.tr["data-withdrawn"], "0")
        # the summary is searchable but not shown
        self.assertIn("管理策のカタログ", soup.tr["data-search"])
        self.assertNotIn("管理策のカタログ", soup.get_text())

    def test_withdrawn_rows_are_marked(self):
        soup = BeautifulSoup(_render_row(dict(ENTRY, withdrawn=True, date="")), "html.parser")
        self.assertEqual(soup.tr["data-withdrawn"], "1")
        self.assertIn("廃止", soup.select_one(".tag").get_text())
        self.assertEqual(soup.select_one(".date").get_text(), "—")

    def test_natural_order_compares_numbers_by_value(self):
        numbers = ["SP 800-100", "SP 800-53A Rev. 5", "SP 800-53 Rev. 5", "SP 800-9"]
        self.assertEqual(sorted(numbers, key=_natural),
                         ["SP 800-9", "SP 800-53 Rev. 5", "SP 800-53A Rev. 5", "SP 800-100"])

    def test_build_lists_both_series_with_filters(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fips = dict(ENTRY, series="fips", number="FIPS 203", href="fips-203.html", order="2 " + _natural("FIPS 203"))
            with patch.object(index_page, "_entries", return_value=[ENTRY, fips]):
                page = build_translation_index(root).read_text()
        soup = BeautifulSoup(page, "html.parser")
        self.assertEqual([row["data-series"] for row in soup.select("tbody tr")], ["sp800", "fips"])
        self.assertEqual([radio["value"] for radio in soup.select('input[name="series"]')], ["all", "sp800", "fips"])
        self.assertTrue(soup.select_one("#hide-withdrawn").has_attr("checked"))
        self.assertEqual([th.get_text(strip=True) for th in soup.select("thead th")], ["資料番号", "タイトル", "刊行日"])
        self.assertIn("非公式", soup.select_one(".site-panel").get_text())
        self.assertNotIn("$", soup.select_one("main").get_text())

    def test_old_fips_index_forwards_to_the_filtered_list(self):
        with tempfile.TemporaryDirectory() as temp:
            page = build_fips_index(Path(temp)).read_text()
        self.assertIn('url=index.html?series=fips', page)


if __name__ == "__main__":
    unittest.main()
