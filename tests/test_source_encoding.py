import hashlib
import html
import json
import importlib
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.nist_translater.pdf_source_repairs import (
    preserve_source_repairs, repair_font_maps,
)
from src.nist_translater.source_quality import encoding_issues
from src.nist_translater.render import build_site
from src.nist_translater.translation import audit_translations, make_queue, merge_translations
from scripts.repair_source_encoding import repair_text

ROOT = Path(__file__).resolve().parents[1]


def block(key="p1", text="Clean source", page=1):
    return {"id": key, "kind": "paragraph", "html": text, "html_ja": "訳文",
            "status": "draft", "extraction_status": "needs_review", "source_page": page,
            "source_refs": [{"page": page, "bbox": [1, 2, 3, 4]}],
            "source_hash": hashlib.sha256(("paragraph\n" + text + "\n").encode()).hexdigest()[:16]}


class SourceEncodingTests(unittest.TestCase):
    def test_font_fix_requires_pdf_font_code_and_bad_mapping_to_match(self):
        class Stream:
            data = b"<019F> <FFFD>\n<014C> <FFFD>\n<01AB> <FFFD>\n<0100> <FFFD>"

            def get_data(self):
                return self.data

        stream = Stream()
        pdf = SimpleNamespace(pages=[SimpleNamespace(page_obj=SimpleNamespace(resources={
            "Font": {"F1": {"BaseFont": SimpleNamespace(name="STXQJN+Calibri"),
                            "ToUnicode": stream}}}))])
        original = stream.data
        self.assertEqual(repair_font_maps(pdf, "different-pdf"), [])
        self.assertEqual(stream.data, original)
        records = repair_font_maps(pdf, "75665570048b969ad465a4f4f1db425ce505c374951c2c64e462949c6b21be47")
        self.assertEqual({r["replacement"] for r in records}, {"ti", "tti", "ft"})
        self.assertIn(b"<019F> <00740069>", stream.data)
        self.assertIn(b"<0100> <FFFD>", stream.data)  # Unknown code stays unresolved.
        self.assertEqual(repair_font_maps(pdf, "75665570048b969ad465a4f4f1db425ce505c374951c2c64e462949c6b21be47"), [])

    def test_word_alignment_handles_ligatures_and_clipped_table_suffixes(self):
        pairs = [("organiza�on", "organization"), ("se�ngs", "settings"),
                 ("dra�", "draft"), ("�e", "The")]
        self.assertEqual(repair_text("za�on se�ngs dra� �e", pairs), "zation settings draft The")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            repair_text("�", pairs)

    def test_damaged_source_is_not_sent_to_translation_or_certified(self):
        b = block(text="&#xfffd;e source")
        doc = {"source_format": "pdf", "contents": [b]}
        self.assertEqual(make_queue(doc), [])
        with self.assertRaisesRegex(ValueError, "replacement"):
            merge_translations(doc, [{"id": b["id"], "source_hash": b["source_hash"], "html_ja": "訳"}])
        b["extraction_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "cannot be verified"):
            audit_translations(doc)

    def test_even_unverified_reference_text_cannot_publish_loss_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "page.html"
            doc = {"contents": [block(text="� source")]}
            with self.assertRaisesRegex(ValueError, "before publishing"):
                build_site(doc, {}, ROOT / "templates/page.html", output)
            self.assertFalse(output.exists())

    def test_archived_loss_markers_are_evidence_not_published_source(self):
        doc = {"contents": [block()], "source_repairs": {"original_blocks": [block(text="�")]}}
        self.assertEqual(encoding_issues(doc), [])
        doc["contents"][0]["html_ja"] = "&#65533;"
        self.assertEqual(encoding_issues(doc)[0]["field"], "html_ja")

    def test_repairs_survive_partial_reparse_and_reject_different_pdf(self):
        repaired = block("fixed", "Corrected source")
        previous = {"contents": [repaired], "source_repairs": {
            "source_sha256": "pinned", "pages": [1], "block_ids": [], "original_blocks": []}}
        current = {"contents": [block("new", page=2)], "source_sha256": "pinned",
                   "included_pages": [2], "pdf_page_count": 2}
        result = preserve_source_repairs(previous, deepcopy(current))
        self.assertEqual([b["id"] for b in result["contents"]], ["fixed", "new"])
        self.assertEqual(result["included_pages"], [1, 2])
        current["source_sha256"] = "new-version"
        with self.assertRaisesRegex(ValueError, "PDF changed"):
            preserve_source_repairs(previous, current)

    def test_known_47r1_reextraction_retains_diagram_and_complete_body(self):
        from src.nist_translater.pdf_parser import parse_pdf_document
        path = ROOT / "data/sp800-47r1.pdf"
        if not path.exists():
            self.skipTest("Original PDF is not present")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        result = parse_pdf_document(path, "SP 800-47 Rev. 1", "https://example.test/original",
                                    pages=[38])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sha)
        self.assertEqual(encoding_issues(result), [])
        self.assertEqual(sum(b["kind"] == "figure" for b in result["contents"]), 1)
        self.assertFalse(any(b["kind"] == "table" for b in result["contents"]))
        text = " ".join(b["html"] for b in result["contents"])
        self.assertIn("in writing and waits to receive an acknowledgment", text)
        self.assertIn("identifies the technical and managerial staff", text)

    def test_repaired_cross_page_paragraph_does_not_duplicate_its_tail(self):
        repaired = block("fixed", "Start and tail")
        repaired["source_refs"].append({"page": 2, "bbox": [1, 2, 3, 4]})
        previous = {"contents": [repaired], "source_repairs": {
            "source_sha256": "pinned", "pages": [1], "block_ids": []}}
        raw = {"source_sha256": "pinned", "included_pages": [2],
               "contents": [block("raw-tail", "and tail", page=2)]}
        current = preserve_source_repairs(previous, raw)
        self.assertEqual([b["id"] for b in current["contents"]], ["fixed"])

    def test_math_repair_survives_actual_reparse_without_recurring_loss_marker(self):
        from src.nist_translater.pdf_parser import parse_pdf_document
        from src.nist_translater.translation import carry_translations
        path = ROOT / "data/sp800-231.pdf"
        if not path.exists():
            self.skipTest("Original PDF is not present")
        previous = json.loads((ROOT / "data/sp800-231-trans.json").read_text())
        raw = parse_pdf_document(path, "SP 800-231", "https://example.test/original", pages=[45])
        self.assertTrue(encoding_issues(raw))  # CMEX10 requires semantic reconstruction.
        current = carry_translations(previous, raw)
        self.assertEqual(encoding_issues(current), [])
        self.assertEqual(current["encoding_issues"], [])
        expected = next(b for b in previous["contents"] if b["id"] == "pdf-p0045-b0018")
        actual = next(b for b in current["contents"] if b["id"] == expected["id"])
        self.assertEqual(actual, expected)

    def test_repository_active_source_and_translations_have_no_loss_markers(self):
        issues = []
        for path in (ROOT / "data").glob("*-trans.json"):
            issues.extend((path.name, issue) for issue in encoding_issues(json.loads(path.read_text())))
        for path in (ROOT / "html").glob("*.html"):
            if "\ufffd" in html.unescape(path.read_text()):
                issues.append((path.name, "stale generated HTML"))
        self.assertEqual(issues, [])

    def test_batch_build_propagates_publication_failure(self):
        cli = importlib.import_module("nist_translater.cli")
        with patch.object(cli, "build", side_effect=ValueError("Replacement character")), \
                patch.object(cli, "build_translation_index", return_value="test index"), \
                patch.object(sys, "argv", ["build_all.py", "47r1"]):
            with self.assertRaises(SystemExit) as error:
                runpy.run_path(str(ROOT / "reports/work-in-progress/build_all.py"))
            self.assertEqual(error.exception.code, 1)

    def test_all_recorded_repaired_blocks_survive_a_raw_reparse(self):
        from src.nist_translater.pdf_source_repairs import preserve_source_repairs
        for key in ["47r1", "177r1", "189", "53ar5", "231"]:
            document = json.loads((ROOT / "data" / ("sp800-" + key + "-trans.json")).read_text())
            if "source_repairs" not in document:
                continue
            record = document["source_repairs"]
            raw = {"source_sha256": record["source_sha256"], "contents": deepcopy(record["original_blocks"]),
                   "included_pages": [b["source_page"] for b in record["original_blocks"]]}
            current = preserve_source_repairs(document, raw)
            expected = {b["id"]: b for b in document["contents"]
                        if b["source_page"] in record["pages"] or b["id"] in record["block_ids"]}
            found = {b["id"]: b for b in current["contents"]}
            for key, value in expected.items():
                self.assertEqual(found[key], value)
            self.assertEqual(encoding_issues(current), [])
