import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.nist_translater.auto_translate import (
    CliExecutionError, TranslationError, run_cli, translate_pending, validate_response,
)
from src.nist_translater.storage import read_json, write_json
from src.nist_translater.translation import (
    assert_same_html_structure, audit_translations, merge_translations,
)


class AutoTranslateTests(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            {"id": "one", "kind": "paragraph", "html": "The verifier SHALL check it.", "source_hash": "abc", "html_ja": "", "status": "untranslated"},
            {"id": "two", "kind": "paragraph", "html": "Authentication", "source_hash": "def", "html_ja": "", "status": "untranslated"},
        ]
        self.document = {"contents": self.blocks}

    def test_agy_envelope_and_cli_args(self):
        model = {"translations": [{"id": "one", "source_hash": "abc", "html_ja": "検証者は SHALL（必須）確認する。"}]}
        completed = subprocess.CompletedProcess([], 0, json.dumps({
            "status": "SUCCESS", "response": "not machine readable", "structured_output": model,
            "denied_actions": [],
        }), "")
        with patch("subprocess.run", return_value=completed) as call:
            result = run_cli([{"id": "one", "source_hash": "abc", "html": self.blocks[0]["html"]}], timeout=10)
        self.assertEqual(result, model)
        command = call.call_args.args[0]
        self.assertEqual(command[0], "agy")
        self.assertIn("--output-format", command)
        self.assertTrue(any(arg.startswith("--print=") for arg in command))
        self.assertIn('"html"', next(arg for arg in command if arg.startswith("--print=")))
        self.assertNotIn("--mode", command)
        self.assertFalse(call.call_args.kwargs.get("shell", False))

    def test_empty_or_denied_agy_response_is_failure(self):
        completed = subprocess.CompletedProcess([], 0, json.dumps({
            "status": "SUCCESS", "response": "", "denied_actions": [{"action": "command"}],
        }), "")
        with patch("subprocess.run", return_value=completed):
            with self.assertRaises(TranslationError):
                run_cli([], timeout=10)

    def test_batch_validation_rejects_invalid_json_shape_and_missing_requirement_word(self):
        batch = [{"id": "one", "source_hash": "abc", "html": self.blocks[0]["html"]}]
        with self.assertRaises(TranslationError):
            validate_response({"translations": []}, batch)
        with self.assertRaises(TranslationError):
            validate_response({"translations": [{"id": "two", "source_hash": "abc", "html_ja": "SHALL"}]}, batch)
        with self.assertRaises(TranslationError):
            validate_response({"translations": [{"id": "one", "source_hash": "abc", "html_ja": "確認する。"}]}, batch)
        with self.assertRaises(TranslationError):
            validate_response({"translations": [{"id": "one", "source_hash": "abc", "html_ja": "SHALL（必須）確認する。MAY"}]}, batch)

    def test_retry_and_atomic_resume(self):
        responses = iter([
            {"translations": []},
            {"translations": [{"id": "one", "source_hash": "abc", "html_ja": "検証者は SHALL（必須）確認する。"}]},
            {"translations": []},
            {"translations": []},
        ])

        def fake_runner(batch, **_kwargs):
            return next(responses)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sp800-63b-trans.json"
            with self.assertRaises(TranslationError):
                translate_pending(self.document, path, batch_size=1, attempts=2,
                                  runner=fake_runner)
            saved = read_json(path)
            first = next(block for block in saved["contents"] if block["id"] == "one")
            self.assertEqual(first["status"], "draft")
            with self.assertRaises(ValueError):
                write_json(path, {"invalid": float("nan")})
            self.assertEqual(read_json(path), saved)

    def test_stored_translation_audit_rejects_added_normative_word(self):
        self.blocks[1]["html_ja"] = "認証。MAY"
        self.blocks[1]["status"] = "draft"
        with self.assertRaisesRegex(ValueError, "Requirement terms differ"):
            audit_translations(self.document)

    def test_table_translation_must_keep_tags_and_attributes(self):
        self.blocks[1].update({
            "kind": "table",
            "html": '<table><tr><th><a href="https://example.test/ref">Requirement</a></th></tr></table>',
            "source_hash": "table-hash",
            "status": "untranslated",
        })
        valid = [{"id": "two", "source_hash": "table-hash",
                  "html_ja": '<table><tr><th><a href="https://example.test/ref">要件</a></th></tr></table>'}]
        self.assertEqual(merge_translations(self.document, valid), 1)
        self.assertEqual(self.blocks[1]["status"], "draft")
        self.blocks[1]["status"] = "untranslated"
        invalid = [{"id": "two", "source_hash": "table-hash",
                    "html_ja": '<table><tr><th><a href="https://elsewhere.test/ref">要件</a></th></tr></table>'}]
        with self.assertRaisesRegex(ValueError, "tags or attributes"):
            merge_translations(self.document, invalid)

    def test_image_alt_text_can_be_translated_but_source_is_preserved(self):
        source = '<img src="https://example.test/figure.png" alt="English description" loading="lazy">'
        translated = '<img src="https://example.test/figure.png" alt="日本語の説明" loading="lazy">'
        assert_same_html_structure(source, translated)
        with self.assertRaisesRegex(ValueError, "tags or attributes"):
            assert_same_html_structure(
                source, '<img src="https://example.test/other.png" alt="日本語の説明" loading="lazy">',
            )

    def test_failed_batch_is_split_and_valid_parts_are_saved(self):
        def fake_runner(batch, **_kwargs):
            if len(batch) > 1:
                raise TranslationError("truncated")
            item = batch[0]
            japanese = "SHALL（必須）確認する。" if item["id"] == "one" else "認証"
            return {"translations": [{"id": item["id"], "source_hash": item["source_hash"],
                                      "html_ja": japanese}]}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sp800-63b-trans.json"
            count, selected = translate_pending(self.document, path, batch_size=2,
                                                attempts=1, runner=fake_runner)
            self.assertEqual((count, selected), (2, 2))
            self.assertEqual({block["id"] for block in read_json(path)["contents"]}, {"one", "two"})

    def test_cli_failure_does_not_multiply_calls(self):
        calls = []

        def fake_runner(batch, **_kwargs):
            calls.append(len(batch))
            raise CliExecutionError("authentication failed")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sp800-63b-trans.json"
            with self.assertRaises(CliExecutionError):
                translate_pending(self.document, path, batch_size=2, attempts=1,
                                  runner=fake_runner)
            self.assertEqual(calls, [2])
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
