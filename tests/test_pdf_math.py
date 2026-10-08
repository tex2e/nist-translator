import json
import re
import shutil
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from bs4 import BeautifulSoup

from src.nist_translater.pdf_equations import (
    inline_katex_html,
    pending_math_translation,
)
from src.nist_translater.translation import assert_same_html_structure
from src.nist_translater.semantic_math import semantic_math
from src.nist_translater.pdf_math import preserve_sp800_22_math, restore_extraction

ROOT = Path(__file__).resolve().parents[1]


class PdfMathTests(unittest.TestCase):
    def test_pending_translation_preserves_display_math_and_numeric_table_cells(self):
        source = (
            r"<div>Compute \[x=\frac12\]</div><table><tr><td>0.125</td></tr></table>"
        )
        translated = pending_math_translation(source)
        self.assertIn(r"\[x=\frac12\]", translated)
        self.assertIn("<td>0.125</td>", translated)
        assert_same_html_structure(source, translated)
        with self.assertRaisesRegex(ValueError, "LaTeX formulas differ"):
            assert_same_html_structure(
                source, translated.replace("frac12", "frac13"), preserve_math=True
            )

    def test_seed_literals_are_complete_and_identical_in_both_languages(self):
        blocks = {
            int(b["id"][-3:]): b
            for b in self.document["contents"]
            if b["kind"] == "math"
        }
        for number in (325, 327, 329, 331, 333):
            values = []
            for field in ("html", "html_ja"):
                code = BeautifulSoup(blocks[number][field], "html.parser").select_one(
                    "code.math-value"
                )
                self.assertIsNotNone(code)
                value = code.get_text()
                self.assertRegex(value, r"^[0-9a-f]+$")
                self.assertEqual(len(value), 127 if number == 331 else 128)
                values.append(value)
            self.assertEqual(*values)
        self.assertEqual(
            BeautifulSoup(blocks[327]["html"], "html.parser").code.get_text(),
            BeautifulSoup(blocks[329]["html"], "html.parser").code.get_text(),
        )

    def test_source_review_preserves_separate_indices_powers_and_table_rows(self):
        blocks = {
            int(b["id"][-3:]): b
            for b in self.document["contents"]
            if b["kind"] == "math"
        }
        self.assertNotIn(r"v_{iv_{1}}", blocks[113]["html"])
        self.assertIn(r"\(v_1\)", blocks[113]["html"])
        self.assertIn(r"\(2^m\)", blocks[151]["html"])
        self.assertIn(r"2^m = 2^3 = 8", blocks[167]["html"])
        self.assertIn(r"\begin{aligned}\chi^2", blocks[198]["html"])
        table = BeautifulSoup(blocks[204]["html"], "html.parser").table
        self.assertEqual(len(table.select("tr")), 9)
        self.assertTrue(
            all(
                len(row.find_all(["td", "th"], recursive=False)) == 4
                for row in table.select("tr")
            )
        )

    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / "data/sp800-22r1-trans.json").read_text())

    def test_result_tables_keep_serial_labels_and_source_values(self):
        blocks = {
            int(b["id"][-3:]): b
            for b in self.document["contents"]
            if b["kind"] == "math"
        }
        for number in range(318, 323):
            for field in ("html", "html_ja"):
                rows = BeautifulSoup(blocks[number][field], "html.parser").select("tr")
                self.assertEqual(len(rows), 17)
                self.assertIn(r"\nabla\Psi_m^2", str(rows[-1]))
                self.assertEqual(len(rows[-1].select("td")), 2)
        for number, expected in (
            (321, ("0.216235", "0.566118")),
            (322, ("0.610051", "0.473961", "0.917121", "0.689519")),
        ):
            for field in ("html", "html_ja"):
                for value in expected:
                    self.assertIn(value, blocks[number][field])

    def test_repair_preserves_original_records_and_translations_for_reparse(self):
        restored = restore_extraction(self.document)
        self.assertEqual(len(restored["contents"]), 2927)
        self.assertEqual(len({b["id"] for b in restored["contents"]}), 2927)
        self.assertTrue(all(not b.get("replaces") for b in restored["contents"]))
        archived = {
            b["id"]: b for b in self.document["math_preservation"]["original_blocks"]
        }
        for block in restored["contents"]:
            if block["id"] in archived:
                self.assertEqual(block["html_ja"], archived[block["id"]]["html_ja"])
        self.assertGreater(sum(bool(b["html_ja"]) for b in restored["contents"]), 2000)

    def test_figures_remain_images_but_body_math_does_not(self):
        figures = [
            b for b in self.document["contents"] if b["kind"] == "source_excerpt"
        ]
        maths = [b for b in self.document["contents"] if b["kind"] == "math"]
        self.assertEqual(len(figures), 7)
        self.assertEqual({b["source_excerpt_type"] for b in figures}, {"figure"})
        for block in figures:
            self.assertTrue((ROOT / "html" / block["source_image"]).is_file())
        self.assertGreater(len(maths), 300)
        self.assertTrue(all("<img" not in b["html"] for b in maths))
        by_id = {b["id"]: b for b in maths}
        formula = by_id["pdf-p0025-math-027"]
        self.assertIn(r"\frac{|S_n|}{\sqrt n}", formula["html"])
        self.assertIn(r"\frac{|S_n|}{\sqrt n}", formula["html_ja"])
        self.assertIn(r"\varepsilon_{(i-1)M+j}", by_id["pdf-p0026-math-038"]["html"])

    def test_changed_pdf_is_rejected_and_matching_repair_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.pdf"
            path.write_bytes(b"changed source")
            with self.assertRaisesRegex(ValueError, "PDF changed"):
                preserve_sp800_22_math(
                    self.document, path, Path(directory) / "assets", "assets"
                )
        source = ROOT / "data/sp800-22r1.pdf"
        if not source.exists():
            return
        result = preserve_sp800_22_math(
            self.document, source, ROOT / "html/assets/22r1", "assets/22r1"
        )
        self.assertEqual(result, self.document)
        result["contents"][0]["html"] = "edited copy"
        self.assertNotEqual(
            result["contents"][0]["html"], self.document["contents"][0]["html"]
        )

    def test_source_geometry_becomes_structural_subscript_without_layout_commands(self):
        chars = [
            dict(
                text="S",
                x0=90,
                x1=98,
                top=135,
                bottom=147,
                size=12,
                fontname="Times-Italic",
                matrix=(1, 0, 0, 1, 90, 646),
            ),
            dict(
                text="n",
                x0=98,
                x1=104,
                top=144,
                bottom=151,
                size=7,
                fontname="Times-Italic",
                matrix=(1, 0, 0, 1, 98, 642),
            ),
        ]
        result = semantic_math(chars, [], 146)
        self.assertIn(r"S_{n}", result)
        self.assertNotIn("style=", result)
        self.assertEqual(inline_katex_html(result), result)
        chars[0]["text"] = "\ue123"
        with self.assertRaisesRegex(ValueError, "Unknown glyph"):
            semantic_math(chars, [], 146)

    def test_math_is_stored_inline_in_both_translation_fields(self):
        maths = [b for b in self.document["contents"] if b["kind"] == "math"]
        for block in maths:
            self.assertTrue(block["math_source_hashes"])
            for field in ("html", "html_ja"):
                self.assertTrue(block[field])
                if re.search(r"\\[([]", block["html"]):
                    self.assertRegex(block[field], r"\\[([]")
                self.assertNotIn("data-tex", block[field])
                self.assertNotIn("pdf-math-glyph", block[field])
                self.assertNotIn(r"\htmlStyle", block[field])
            if block["math_translation_pending"]:
                self.assertEqual(block["status"], "untranslated")
        self.assertEqual(sum(b["math_translation_pending"] for b in maths), 273)

    def test_inline_edits_survive_rebuilding_from_original_extraction(self):
        source = ROOT / "data/sp800-22r1.pdf"
        if not source.exists():
            self.skipTest("Original PDF required for re-extraction round trip")
        previous = deepcopy(self.document)
        block = next(b for b in previous["contents"] if b.get("math_mode") == "latex")
        identifier = block["id"]
        block["html"] += "<p>Direct source edit: \\(x=1\\)</p>"
        block["html_ja"] += "<p>直接編集した訳文: \\(x=1\\)</p>"
        with tempfile.TemporaryDirectory() as directory:
            result = preserve_sp800_22_math(
                restore_extraction(previous),
                source,
                Path(directory),
                "assets",
                previous_document=previous,
            )
        rebuilt = next(b for b in result["contents"] if b["id"] == identifier)
        self.assertEqual(rebuilt["html"], block["html"])
        self.assertEqual(rebuilt["html_ja"], block["html_ja"])

    def test_coordinate_fallbacks_are_rejected_instead_of_silently_reintroduced(self):
        for command in (
            "htmlStyle",
            "mathrlap",
            "vphantom",
            "raisebox",
            "kern",
            "rule",
        ):
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, "Coordinate-layout"):
                    inline_katex_html("<p>\\(" + "\\" + command + "{x}\\)</p>")
        structural = r"<p>\(\sum_{i=0}^K\frac{(v_i-N\pi_i)^2}{N\pi_i}\)</p>"
        self.assertEqual(inline_katex_html(structural), structural)

    def test_complex_formulas_and_matrices_have_native_structures(self):
        blocks = {b["id"]: b for b in self.document["contents"]}
        self.assertIn(
            r"\sum_{i=0}^K\frac{(v_i-N\pi_i)^2}{N\pi_i}",
            blocks["pdf-p0031-math-061"]["html"],
        )
        self.assertIn(
            r"\begin{vmatrix}0&amp;1&amp;0", blocks["pdf-p0033-math-072"]["html"]
        )
        self.assertIn(
            r"\frac{\left(M/3+2/9\right)}{2^M}", blocks["pdf-p0047-math-145"]["html"]
        )
        self.assertIn(
            r"\frac{|\xi_J(x)(\mathrm{obs})-J|}", blocks["pdf-p0086-math-368"]["html"]
        )
        for block in blocks.values():
            if block["kind"] == "math":
                self.assertEqual(block["math_mode"], "latex")
                inline_katex_html(block["html"])
                inline_katex_html(block["html_ja"])

    def test_local_katex_assets_are_complete_and_copied(self):
        source = ROOT / "static/vendor/katex"
        target = ROOT / "html/vendor/katex"
        for path in source.rglob("*"):
            if path.is_file():
                self.assertEqual(
                    path.read_bytes(), (target / path.relative_to(source)).read_bytes()
                )
        css = (source / "katex.min.css").read_text()
        for url in re.findall(r"url\(([^)]+)\)", css):
            self.assertTrue((source / url.strip("\"'")).is_file(), url)
        template = (ROOT / "templates/page.html").read_text()
        for name in ("katex.min.css", "katex.min.js", "auto-render.min.js"):
            self.assertIn("vendor/katex/" + name, template)

    @unittest.skipUnless(
        shutil.which("node"), "Node is required for KaTeX syntax validation"
    )
    def test_every_stored_equation_parses_with_the_bundled_katex(self):
        expressions = set()
        for block in self.document["contents"]:
            if block["kind"] != "math":
                continue
            for field in ("html", "html_ja"):
                soup = BeautifulSoup(block[field], "html.parser")
                expressions.update((e["data-tex"], False) for e in soup.select("[data-tex]"))
                expressions.update(
                    (a or b, bool(b))
                    for a, b in re.findall(
                        r"\\\((.*?)\\\)|\\\[(.*?)\\\]", soup.get_text(), flags=re.S
                    )
                )
        self.assertGreater(len(expressions), 500)
        script = """
const katex = require(process.argv[1]);
const expressions = JSON.parse(require('fs').readFileSync(0, 'utf8'));
for (const [tex, displayMode] of expressions) {
  try { katex.renderToString(tex, {
    throwOnError: true, strict: 'ignore', maxExpand: 20000,
    trust: false, displayMode
  }); } catch (error) {
    console.error(tex + '\\n' + error.message);
    process.exitCode = 1;
  }
}
"""
        result = subprocess.run(
            ["node", "-e", script, str(ROOT / "static/vendor/katex/katex.min.js")],
            input=json.dumps(sorted(expressions)),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
