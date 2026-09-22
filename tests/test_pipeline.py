import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from bs4 import BeautifulSoup

from src.nist_translater.render import build_site
from src.nist_translater.storage import read_json
from src.nist_translater.translation import make_queue, merge_translations


ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = read_json(ROOT / "data/sp800-63b-trans.json")

    def test_nist_structure_and_links(self):
        blocks = self.document["contents"]
        self.assertGreater(len(blocks), 1200)
        self.assertEqual(len({b["id"] for b in blocks}), len(blocks))
        self.assertEqual(sum(b["kind"] == "table" for b in blocks), 5)
        self.assertEqual(sum(b["kind"] == "figure" for b in blocks), 3)
        self.assertIn("https://pages.nist.gov/800-63-4/", "".join(b["html"] for b in blocks[:50]))
        self.assertTrue(any(b.get("ordered") for b in blocks if b["kind"] == "list_item"))

    def test_queue_and_merge_reject_changed_source(self):
        document = deepcopy(self.document)
        block = next(block for block in document["contents"]
                     if block["kind"] == "paragraph" and "<" not in block["html"])
        block["html_ja"] = ""
        block["status"] = "untranslated"
        pending = make_queue(document)
        item = next(x for x in pending if x["id"] == block["id"])
        item["html_ja"] = "仮の訳"
        count = merge_translations(document, [item])
        self.assertEqual(count, 1)
        self.assertEqual(block["status"], "draft")
        item["source_hash"] = "old-hash"
        with self.assertRaisesRegex(ValueError, "Source changed"):
            merge_translations(document, [item])

    def test_render_hides_stale_translation_and_escapes_japanese(self):
        document = deepcopy(self.document)
        block = next(block for block in document["contents"]
                     if block["kind"] == "paragraph" and "<" not in block["html"])
        block["html_ja"] = ""
        block["status"] = "untranslated"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "page.html"
            block["html_ja"] = "<script>alert(1)</script>"
            block["status"] = "draft"
            with self.assertRaisesRegex(ValueError, "HTML tags"):
                build_site(document, {}, ROOT / "templates/page.html", output)
            block["html_ja"] = "日本語訳"
            baseline = sum(x["status"] == "draft" and bool(x["html_ja"]) for x in document["contents"]) - 1
            build_site(document, {}, ROOT / "templates/page.html", output)
            page = output.read_text(encoding="utf-8")
            soup = BeautifulSoup(page, "html.parser")
            self.assertEqual(len(soup.select(".pair")), sum(
                block["kind"] not in {"figure", "footnote"}
                for block in document["contents"]
            ))
            self.assertEqual(len(soup.select(".draft-badge")), baseline + 1)

            block["html_ja"] = "古い訳"
            block["status"] = "stale"
            build_site(document, {}, ROOT / "templates/page.html", output)
            self.assertNotIn("古い訳", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
