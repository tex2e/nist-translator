import glob
import json
import re
import unittest
from pathlib import Path

from src.nist_translater.private_glyphs import PROFILES, replace_private_glyphs

ROOT = Path(__file__).resolve().parents[1]
SP53A = "75665570048b969ad465a4f4f1db425ce505c374951c2c64e462949c6b21be47"


class PrivateGlyphTests(unittest.TestCase):
    def test_calibri_ligatures_follow_the_word(self):
        mapping = PROFILES[SP53A]
        for raw, word in (("informaon", "information"), ("sengs", "settings"),
                          ("aributes", "attributes"), ("hps", "https"),
                          ("transming", "transmitting"), ("soware", "software"),
                          ("plaorm", "platform")):
            self.assertEqual(replace_private_glyphs(raw, mapping), word)

    def test_no_private_use_glyph_is_shown(self):
        for path in glob.glob(str(ROOT / "data" / "*-trans.json")):
            for block in json.loads(Path(path).read_text())["contents"]:
                if block.get("page_furniture"):
                    continue
                for field in ("html", "html_ja"):
                    self.assertIsNone(re.search(r"[-]", block.get(field) or ""),
                                      "%s %s %s" % (Path(path).name, block["id"], field))


if __name__ == "__main__":
    unittest.main()
