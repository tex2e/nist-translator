import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SummaryTests(unittest.TestCase):
    def test_summary_files_are_well_formed(self):
        for path in ROOT.glob("data/*-summary.json"):
            with self.subTest(path=path.name):
                summary = json.loads(path.read_text())
                self.assertTrue((ROOT / "data" / path.name.replace("-summary.json", "-trans.json")).exists())
                self.assertIsInstance(summary.get("number"), str)
                self.assertTrue(2 <= len(summary.get("summary", [])) <= 5)
                for sentence in summary["summary"]:
                    self.assertIsInstance(sentence, str)
                    self.assertTrue(sentence.strip())
                    self.assertNotIn("<", sentence)


if __name__ == "__main__":
    unittest.main()
