import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("translation_review", ROOT / "scripts" / "translation_review.py")
translation_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(translation_review)


def block(block_id, check, status="reviewed"):
    return {"id": block_id, "kind": "paragraph", "source_hash": "h-" + block_id,
            "html": "The module shall do it.", "html_ja": "モジュールはそれを行わなければなりません。",
            "status": status, "translation_check": check, "extraction_status": "verified",
            "source_page": 1, "source_refs": [{"page": 1, "bbox": [1, 2, 3, 4]}]}


class CrossReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        self.saved_root, translation_review.ROOT = translation_review.ROOT, self.root
        self.document = {"source_format": "pdf", "number": "FIPS 0", "contents": [
            block("a", "claude-review"), block("b", "claude-fix"), block("c", "codex-review"),
            block("d", "claude-review", status="draft")]}
        self.path = self.root / "data" / "fips-0-trans.json"
        self.path.write_text(json.dumps(self.document, ensure_ascii=False))

    def tearDown(self):
        translation_review.ROOT = self.saved_root
        self.tmp.cleanup()

    def test_recheck_exports_only_reviewed_blocks_with_the_named_checks(self):
        out = self.root / "batches"
        translation_review.export(out, 40, ["fips-0"], False, "codex", {"claude-review", "claude-fix"})
        batch = json.loads((out / "fips-0.001.batch.json").read_text())
        self.assertEqual([item["id"] for item in batch["blocks"]], ["a", "b"])

    def test_recheck_apply_keeps_ok_reviewed_and_returns_corrections_to_draft(self):
        out = self.root / "batches"
        translation_review.export(out, 40, ["fips-0"], False, "codex", {"claude-review", "claude-fix"})
        (out / "fips-0.001.verdict.json").write_text(json.dumps([
            {"id": "a", "source_hash": "h-a", "verdict": "ok", "note": "", "suggested_ja": ""},
            {"id": "b", "source_hash": "h-b", "verdict": "issue", "note": "語順",
             "suggested_ja": "モジュールは、それを行わなければなりません。"}], ensure_ascii=False))
        translation_review.apply(out, None, "codex", recheck=True)
        blocks = {item["id"]: item for item in json.loads(self.path.read_text())["contents"]}
        self.assertEqual((blocks["a"]["status"], blocks["a"]["translation_check"]), ("reviewed", "codex-review"))
        self.assertEqual(blocks["a"]["cross_review_of"], "claude-review")
        self.assertEqual((blocks["b"]["status"], blocks["b"]["translation_check"]), ("draft", "codex-fix"))
        self.assertEqual(blocks["b"]["cross_review_of"], "claude-fix")
        self.assertEqual(blocks["b"]["html_ja"], "モジュールは、それを行わなければなりません。")

    def test_apply_without_recheck_skips_reviewed_blocks(self):
        out = self.root / "batches"
        translation_review.export(out, 40, ["fips-0"], False, "codex", {"claude-review"})
        (out / "fips-0.001.verdict.json").write_text(json.dumps([
            {"id": "a", "source_hash": "h-a", "verdict": "ok", "note": "", "suggested_ja": ""}]))
        translation_review.apply(out, None, "codex")
        blocks = {item["id"]: item for item in json.loads(self.path.read_text())["contents"]}
        self.assertEqual(blocks["a"]["translation_check"], "claude-review")


if __name__ == "__main__":
    unittest.main()
