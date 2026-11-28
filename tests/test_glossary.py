import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_glossary import all_keys, check_document, load_exceptions, load_rules, violations  # noqa: E402


class GlossaryRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()

    def test_katakana_long_vowel_keeps_separate_words(self):
        self.assertEqual(violations(self.rules, "ユーザビリティとユーザブルセキュリティ", "usability"), [])
        self.assertEqual(violations(self.rules, "ユーザー認証", "user"), [])
        self.assertIn("user", violations(self.rules, "ユーザ認証", "user"))

    def test_nonce_ignores_governance(self):
        self.assertEqual(violations(self.rules, "ガバナンスとファイナンス", "governance"), [])
        self.assertIn("nonce", violations(self.rules, "ナンスを使う", "nonce"))

    def test_english_condition_limits_rule(self):
        self.assertEqual(violations(self.rules, "機密情報", "classified information"), [])
        self.assertEqual(violations(self.rules, "機密情報", "sensitive and classified information"), [])
        self.assertIn("sensitive", violations(self.rules, "機密情報", "sensitive information"))
        self.assertEqual(violations(self.rules, "機密情報", None), [])


class CorpusGlossaryTests(unittest.TestCase):
    def test_translations_follow_glossary(self):
        rules, exceptions = load_rules(), load_exceptions()
        found = [item for key in all_keys() for item in check_document(key, rules, exceptions)]
        sample = ["%s %s [%s]" % (item["document"], item["id"], item["rule"]) for item in found[:20]]
        self.assertFalse(found, "%d glossary violations (python scripts/check_glossary.py):\n%s" % (len(found), "\n".join(sample)))


if __name__ == "__main__":
    unittest.main()
