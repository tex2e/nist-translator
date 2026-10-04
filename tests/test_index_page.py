import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from src.nist_translater.index_page import _load_document, _render_row, build_translation_index


class IndexPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "data").mkdir()
        (self.root / "html").mkdir()
        self.record = {
            "number": "800-53 Rev. 5", "title": "Security <controls>",
            "release_date": "9/10/2020", "record_url": "https://example.com/source",
            "json_path": "data/doc.json", "html_path": "html/doc.html",
        }

    def load(self, blocks, **metadata):
        (self.root / "data/doc.json").write_text(json.dumps({"contents": blocks, **metadata}))
        return _load_document(self.root, self.record)

    def test_created_reviewed_and_source_preservation_are_separate(self):
        draft = {"status": "draft", "html_ja": "訳"}
        reviewed = {"status": "reviewed", "html_ja": "訳"}
        source_only = {"status": "source_only", "html_ja": ""}
        self.assertEqual(self.load([draft, source_only])["status"], "created")
        progress = self.load([reviewed, source_only])
        self.assertEqual(progress["status"], "reviewed")
        soup = BeautifulSoup(_render_row(self.record, progress), "html.parser")
        self.assertIn("原文保持あり", soup.get_text())
        self.assertEqual(float(soup.select_one('[role="progressbar"]')["aria-valuenow"]), 50)
        self.assertEqual(self.load([source_only])["status"], "source_ready")
        self.assertEqual(self.load([])["status"], "source_ready")

    def test_stale_and_missing_translation_prevent_created_status(self):
        reviewed = {"status": "reviewed", "html_ja": "訳"}
        self.assertEqual(self.load([reviewed, {"status": "stale", "html_ja": "旧訳"}])["status"], "stale")
        self.assertEqual(self.load([reviewed, {"status": "reviewed", "html_ja": " "}])["status"], "in_progress")
        self.assertEqual(self.load([reviewed, {"status": "untranslated", "html_ja": ""}])["status"], "in_progress")

    def test_links_dates_and_extraction_notes(self):
        (self.root / "html/doc.html").write_text("page")
        progress = self.load([{"status": "reviewed", "html_ja": "訳", "extraction_status": "needs_review"}],
                             extraction_partial=True)
        soup = BeautifulSoup(_render_row(self.record, progress), "html.parser")
        self.assertEqual(soup.tr["data-date"], "2020-09-10")
        self.assertEqual(soup.tr["data-available"], "yes")
        self.assertEqual(soup.select_one(".title a")["href"], "doc.html")
        self.assertEqual(soup.select_one(".number a")["href"], "doc.html")
        self.assertIn("Security <controls>", soup.get_text())
        self.assertIsNone(soup.find("controls"))
        self.assertIn("一部収録", soup.get_text())
        self.assertIn("原文抽出の照合待ち", soup.get_text())
        (self.root / "html/doc.html").unlink()
        soup = BeautifulSoup(_render_row(self.record, _load_document(self.root, self.record)), "html.parser")
        self.assertIsNone(soup.select_one(".title a"))
        self.assertEqual(soup.tr["data-available"], "no")

    def test_build_recounts_json_and_renders_new_labels(self):
        self.load([{"status": "draft", "html_ja": "訳"}])
        (self.root / "data/sp800-final-catalog.json").write_text(json.dumps({"records": [self.record]}))
        page = build_translation_index(self.root).read_text()
        self.assertNotIn("翻訳完了", page)
        self.assertIn("訳文作成済み 1 件", page)
        self.assertNotIn("$table_rows", page)


if __name__ == "__main__":
    unittest.main()
