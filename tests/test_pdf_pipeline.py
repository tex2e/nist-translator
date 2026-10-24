import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from src.nist_translater.pdf_parser import _bounded_bbox, parse_pdf_document
from src.nist_translater.render import build_site
from src.nist_translater.translation import audit_translations, carry_translations


ROOT = Path(__file__).resolve().parents[1]


def make_pdf(path, empty=False, pages=1, stream_override=None):
    """Write a small PDF without a test-only PDF creation dependency."""
    stream = (b"BT /F2 14 Tf 90 700 Td (1 Introduction) Tj ET\n"
              b"BT /F1 12 Tf 90 670 Td (A first sentence about cryptography.) Tj "
              b"0 -15 Td (A second line of the same paragraph.) Tj "
              b"0 -30 Td (A separate paragraph.) Tj ET\n"
              b"BT /F1 9 Tf 90 90 Td (1 A footnote.) Tj ET\n")
    if empty:
        stream = b""
    if stream_override is not None:
        stream = stream_override
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (b"<< /Type /Pages /Kids [3 0 R 7 0 R] /Count 2 >>" if pages == 2
         else b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    if pages == 2:
        objects.extend([
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 8 0 R >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        ])
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(b"%d 0 obj\n" % index + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets[1:]:
        data.extend(b"%010d 00000 n \n" % offset)
    data.extend(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                % (len(objects) + 1, xref))
    path.write_bytes(data)


class PdfPipelineTests(unittest.TestCase):
    def test_full_pdf_includes_every_page_and_preview_is_marked_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "two-pages.pdf"
            make_pdf(source, pages=2)
            full = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            self.assertEqual(full["included_pages"], [1, 2])
            self.assertFalse(full["extraction_partial"])
            self.assertEqual({block["source_page"] for block in full["contents"]}, {1, 2})
            preview = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf", pages=[1])
            self.assertEqual(preview["included_pages"], [1])
            self.assertTrue(preview["extraction_partial"])

    def test_textless_pdf_requires_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scan.pdf"
            make_pdf(source, empty=True)
            with self.assertRaisesRegex(ValueError, "OCR"):
                parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")

    def test_detected_bbox_is_clamped_before_crop(self):
        import pdfplumber

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.pdf"
            make_pdf(source)
            with pdfplumber.open(str(source)) as pdf:
                page = pdf.pages[0]
                bounded = _bounded_bbox((0, 0, page.width + 4.5, page.height), page)
                self.assertEqual(bounded, (0, 0, page.width, page.height))
                self.assertTrue(page.crop(bounded).extract_text())

    def test_toc_heading_and_row_number_are_combined(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "toc.pdf"
            stream = (b"BT /F2 55 Tf 65 740 Td (Table of) Tj 0 -61 Td (CONTENTS) Tj ET\n"
                      b"BT /F1 18 Tf 100 550 Td (Education & Workforce) Tj ET\n"
                      b"BT /F2 27 Tf 490 550 Td (09) Tj ET\n"
                      b"BT /F1 18 Tf 100 470 Td (Human-) Tj ET\n"
                      b"BT /F2 27 Tf 490 470 Td (11) Tj ET\n"
                      b"BT /F1 18 Tf 130 450 Td (Centered Cybersecurity) Tj ET\n"
                      b"BT /F1 18 Tf 100 360 Td (Introduction) Tj ET\n"
                      b"BT /F2 27 Tf 490 360 Td (04) Tj ET\n"
                      b"BT /F2 16 Tf 280 300 Td (- PRIORITY AREAS -) Tj ET\n")
            make_pdf(source, stream_override=stream)
            document = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            texts = [block["html"] for block in document["contents"]]
            self.assertIn("Table of Contents", texts)
            self.assertIn("Education &amp; Workforce 09", texts)
            self.assertIn("Human-Centered Cybersecurity 11", texts)
            self.assertIn("Introduction 04", texts)
            self.assertIn("- PRIORITY AREAS -", texts)
            self.assertNotIn("09", texts)

    def test_wide_same_line_fragment_does_not_join_heading_to_body(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "foreword.pdf"
            stream = (b"BT /F2 30 Tf 75 590 Td (FOREWORD) Tj ET\n"
                      b"BT /F1 14 Tf 324 590 Td (applications continue here) Tj ET\n"
                      b"BT /F1 12 Tf 324 560 Td (We are proud of the result.) Tj ET\n")
            make_pdf(source, stream_override=stream)
            document = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            headings = [block["html"] for block in document["contents"]
                        if block["kind"] == "heading"]
            paragraphs = [block["html"] for block in document["contents"]
                          if block["kind"] == "paragraph"]
            self.assertIn("FOREWORD", headings)
            self.assertIn("applications continue here", paragraphs)
            self.assertIn("We are proud of the result.", paragraphs)
            self.assertNotIn("FOREWORD applications", paragraphs)

    def test_wrapped_title_and_bold_callout_keep_semantic_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "wrapped-title.pdf"
            stream = (b"BT /F2 30 Tf 90 620 Td (Identity &) Tj 0 -30 Td (Access) Tj "
                      b"0 -30 Td (Management) Tj ET\n"
                      b"BT /F2 14 Tf 90 470 Td (A bold explanatory sentence that continues) Tj "
                      b"0 -15 Td (on the next visual line.) Tj ET\n"
                      b"BT /F1 14 Tf 90 430 Td (2024 with industry partners, NIST completed the work.) Tj ET\n"
                      b"BT /F1 9 Tf 490 90 Td (PPAAGGEE 2255) Tj ET\n")
            make_pdf(source, stream_override=stream)
            document = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            content = document["contents"]
            headings = [block["html"] for block in content if block["kind"] == "heading"]
            paragraphs = [block["html"] for block in content if block["kind"] == "paragraph"]
            self.assertIn("Identity &amp; Access Management", headings)
            self.assertIn("A bold explanatory sentence that continues on the next visual line.",
                          paragraphs)
            self.assertIn("2024 with industry partners, NIST completed the work.", paragraphs)
            self.assertFalse(any("PAGE" in block["html"] for block in content))

    def test_adjacent_list_items_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "list.pdf"
            stream = (b"BT /F1 14 Tf 90 600 Td (1. First accomplishment) Tj 0 -23 Td "
                      b"(2. Second accomplishment) Tj ET\n")
            make_pdf(source, stream_override=stream)
            document = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            items = [block["html"] for block in document["contents"]
                     if block["kind"] == "list_item"]
            self.assertEqual(len(items), 2)
            self.assertEqual(items, ["First accomplishment", "Second accomplishment"])

    def test_parse_and_build_pdf_with_page_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.pdf"
            output = Path(directory) / "page.html"
            make_pdf(source)
            document = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            self.assertEqual(document["pdf_page_count"], 1)
            self.assertEqual([block["kind"] for block in document["contents"]],
                             ["heading", "paragraph", "paragraph", "footnote"])
            self.assertEqual(document["contents"][1]["html"],
                             "A first sentence about cryptography. A second line of the same paragraph.")
            self.assertEqual(document["contents"][0]["source_page"], 1)
            self.assertEqual(document["contents"][0]["extraction_status"], "needs_review")
            build_site(document, {}, ROOT / "templates/page.html", output)
            soup = BeautifulSoup(output.read_text(encoding="utf-8"), "html.parser")
            self.assertEqual(len(soup.select(".pair")), 4)
            self.assertEqual(soup.select_one(".source-ref a")["href"],
                             "https://example.test/source.pdf#page=1")
            self.assertIn("NIST PDF 原文", soup.get_text())
            self.assertNotIn("NIST HTML 原文", soup.get_text())

    def test_cross_page_footnote_has_an_anchor_and_complete_page_range(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.pdf';output=Path(directory)/'page.html'
            make_pdf(source,pages=2)
            document=parse_pdf_document(source,'SP 800-999','https://example.test/source.pdf')
            footnote=next(b for b in document['contents'] if b['kind']=='footnote')
            footnote['source_page_end']=2
            build_site(document,{},ROOT/'templates/page.html',output)
            soup=BeautifulSoup(output.read_text(),'html.parser')
            section=soup.find('section',id=footnote['id'])
            self.assertIsNotNone(section)
            self.assertIn('原本 PDF pp.1–2',section.get_text())
            self.assertEqual(section.select_one('.source-ref a')['href'],'https://example.test/source.pdf#page=1')

    def test_multi_paragraph_note_does_not_nest_paragraph_elements(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.pdf';output=Path(directory)/'page.html'
            make_pdf(source)
            document=parse_pdf_document(source,'SP 800-999','https://example.test/source.pdf')
            note=next(b for b in document['contents'] if b['kind']=='paragraph')
            note.update(kind='note',html='<p>First condition.</p><p>Second condition.</p>',
                        html_ja='<p>第1の条件。</p><p>第2の条件。</p>',status='draft')
            build_site(document,{},ROOT/'templates/page.html',output)
            soup=BeautifulSoup(output.read_text(),'html.parser')
            section=soup.find('section',id=note['id'])
            for language in ['english','japanese']:
                column=section.select_one('.'+language)
                self.assertEqual(len(column.find_all('p',recursive=False)),2)
                self.assertIsNone(column.select_one('p p'))

    def test_pdf_reparse_preserves_exact_text_and_marks_changed_text_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.pdf"
            make_pdf(source)
            previous = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            paragraph = previous["contents"][1]
            paragraph["html_ja"] = "暗号についての最初の文。二行目。"
            paragraph["status"] = "reviewed"
            paragraph["extraction_status"] = "verified"
            current = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            current["contents"][1]["html_ja"] = paragraph["html_ja"]
            current["contents"][1]["status"] = "reviewed"
            with self.assertRaisesRegex(ValueError, "PDF source must be verified"):
                audit_translations(current)
            current["contents"][1]["html_ja"] = ""
            current["contents"][1]["status"] = "untranslated"
            current["contents"][1]["id"] = "moved-paragraph"
            carry_translations(previous, current)
            self.assertEqual(current["contents"][1]["status"], "reviewed")
            self.assertEqual(current["contents"][1]["extraction_status"], "verified")
            self.assertEqual(audit_translations(current), 0)
            changed = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            changed["contents"][1]["html"] += " Changed."
            carry_translations(previous, changed)
            self.assertEqual(changed["contents"][1]["status"], "stale")
            self.assertEqual(changed["contents"][1]["extraction_status"], "needs_review")
            retyped = parse_pdf_document(source, "SP 800-999", "https://example.test/source.pdf")
            retyped["contents"][1]["kind"] = "heading"
            carry_translations(previous, retyped)
            self.assertEqual(retyped["contents"][1]["status"], "untranslated")
            self.assertEqual(retyped["contents"][1]["html_ja"], "")

    def test_pdf_reparse_matches_repeated_text_by_page_after_block_ids_shift(self):
        previous = {"source_format": "pdf", "contents": [
            {"id": "old-1", "kind": "paragraph", "html": "Credit: NIST",
             "source_hash": "same", "html_ja": "NIST提供", "status": "draft",
             "source_page": 4, "source_refs": [{"page": 4, "bbox": [1, 2, 3, 4]}]},
            {"id": "old-2", "kind": "paragraph", "html": "Credit: NIST",
             "source_hash": "same", "html_ja": "NISTクレジット", "status": "draft",
             "source_page": 8, "source_refs": [{"page": 8, "bbox": [1, 2, 3, 4]}]},
        ]}
        current = {"source_format": "pdf", "contents": [
            {"id": "new-1", "kind": "paragraph", "html": "Credit: NIST",
             "source_hash": "same", "html_ja": "", "status": "untranslated",
             "source_page": 8, "source_refs": [{"page": 8, "bbox": [1, 2, 3, 4]}]},
            {"id": "new-2", "kind": "paragraph", "html": "Credit: NIST",
             "source_hash": "same", "html_ja": "", "status": "untranslated",
             "source_page": 4, "source_refs": [{"page": 4, "bbox": [1, 2, 3, 4]}]},
        ]}
        carry_translations(previous, current)
        self.assertEqual([block["html_ja"] for block in current["contents"]],
                         ["NISTクレジット", "NIST提供"])


if __name__ == "__main__":
    unittest.main()
