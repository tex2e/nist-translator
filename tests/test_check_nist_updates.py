import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_nist_updates as updates  # noqa: E402


def row(series, number, status, date, path):
    return ('<tr><td>%s</td><td>%s</td><td><a id="pub-title-link-1" href="%s">Title %s</a></td>'
            '<td>%s</td><td>%s</td></tr>' % (series, number, path, number, status, date))


def live(series, stem, date, url):
    return {"series": series, "number": stem, "title": stem, "status": "Final", "release_date": date,
            "record_url": url, "stem": stem}


class CheckNistUpdatesTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "data").mkdir()
        (self.root / "html").mkdir()

    def write_catalog(self, series, records):
        updates.catalog_path(self.root, series).write_text(json.dumps({"record_count": len(records), "records": records}))

    def translate(self, stem):
        (self.root / "data" / (stem + "-trans.json")).write_text("{}")
        (self.root / "html" / (stem + ".html")).write_text("")

    def test_parse_keeps_only_final_rows_of_the_series(self):
        raw = "<table><tr><th>h</th></tr>" + "".join([
            row("SP", "800-221 A", "Final", "11/02/2026", "/pubs/sp/800/221/a/final"),
            row("SP", "800-300", "Draft", "11/02/2026", "/pubs/sp/800/300/ipd"),
            row("SP", "1800-1", "Final", "11/02/2026", "/pubs/sp/1800/1/final"),
        ]) + "</table>"
        records = updates.parse_list("sp800", raw)
        self.assertEqual([r["stem"] for r in records], ["sp800-221a"])
        self.assertEqual(records[0]["release_date"], "2026-11-02")

    def test_compare_finds_missing_removed_changed_and_excluded(self):
        url = "https://csrc.nist.gov/pubs/ir/%s/final"
        self.write_catalog("ir", [
            {"number": "IR 1", "title": "a", "release_date": "2026-01-01", "record_url": url % 1, "stem": "ir-1"},
            {"number": "IR 2", "title": "b", "release_date": "2026-01-01", "record_url": url % 2, "stem": "ir-2"},
            {"number": "IR 3", "title": "c", "release_date": "2026-01-01", "record_url": url % 3, "stem": "ir-7275r2"},
        ])
        self.translate("ir-1")
        result = updates.compare(self.root, "ir", [
            live("ir", "ir-1", "2026-02-01", url % 1),
            live("ir", "ir-7275r2", "2026-01-01", url % 3),
            live("ir", "ir-4", "2026-03-01", url % 4),
        ], {"ir-4"})
        self.assertEqual(result["translated"], 1)
        self.assertEqual([r["stem"] for r in result["missing"]], ["ir-4"])
        self.assertTrue(result["missing"][0]["pending_pr"])
        self.assertEqual([r["stem"] for r in result["removed"]], ["ir-2"])
        self.assertEqual([r["stem"] for r in result["date_changed"]], ["ir-1"])
        self.assertEqual([r["stem"] for r in result["excluded"]], ["ir-7275r2"])

    def test_excluded_publication_is_not_reported_as_removed(self):
        url = "https://csrc.nist.gov/pubs/ir/7621/r1/final"
        self.write_catalog("ir", [{"number": "IR 7621 Rev. 1", "title": "t", "release_date": "2016-11-03",
                                   "record_url": url, "stem": "ir-7621r1"}])
        self.assertEqual(updates.compare(self.root, "ir", [live("ir", "ir-1", "2026-01-01", "new")])["removed"], [])

    def test_a_short_list_is_an_error_not_a_withdrawal(self):
        self.write_catalog("ir", [{"number": "IR %d" % i, "title": "t", "release_date": "2026-01-01",
                                   "record_url": "u%d" % i, "stem": "ir-%d" % i} for i in range(10)])
        with self.assertRaises(RuntimeError):
            updates.compare(self.root, "ir", [])

    def test_next_is_the_oldest_without_a_pull_request(self):
        def item(stem, date, pending=False):
            return dict(live("ir", stem, date, stem), pending_pr=pending)
        results = {"ir": {"missing": [item("ir-3", "2026-03-01"), item("ir-1", "2026-01-01", True),
                                      item("ir-2", "2026-02-01")]}}
        self.assertEqual(updates.choose_next(results)["stem"], "ir-2")
        self.assertEqual(updates.choose_next(results, ["ir-2"])["stem"], "ir-3")

    def test_existing_catalog_stems_match_the_translated_files(self):
        for series in updates.SERIES:
            catalog = json.loads(updates.catalog_path(ROOT, series).read_text(encoding="utf-8"))["records"]
            for entry in catalog:
                stem = updates.local_stem(series, entry)
                if stem not in updates.EXCLUDED and entry.get("pdf_url", True):
                    self.assertTrue((ROOT / "data" / (stem + "-trans.json")).is_file(), stem)


if __name__ == "__main__":
    unittest.main()
