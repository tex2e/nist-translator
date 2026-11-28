import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from markupsafe import Markup  # noqa: E402

from nist_translater.footnotes import (footnote_numbers, gather_footnotes, link_footnotes,  # noqa: E402
                                       split_footnotes)


def row(block_id, kind, en, ja="", page=1):
    return {"id": block_id, "kind": kind, "source_page": page,
            "english_html": Markup(en), "japanese_html": Markup(ja), "html_ja": ja}


def page(rows):
    """What the reading page does: split, link, gather."""
    rows = split_footnotes(rows)
    link_footnotes(rows)
    return gather_footnotes(rows)


class FootnoteTests(unittest.TestCase):
    def test_numbers_of_one_and_several_notes(self):
        self.assertEqual(footnote_numbers("15 A reasonable basis"), [15])
        self.assertEqual(footnote_numbers("3For example, [FCS]. 4For example, OMB. 5NACI was replaced."), [3, 4, 5])
        self.assertEqual(footnote_numbers("<sup>2</sup>See [CSP]."), [2])
        self.assertEqual(footnote_numbers("<sup>4</sup> 45 CFR 160"), [4])
        self.assertEqual(footnote_numbers("<sup>4</sup> <i>See</i> Overview"), [4])
        self.assertEqual(footnote_numbers("Figure 4-6. Card Back"), [])
        self.assertEqual(footnote_numbers("7 | TRUSTWORTHY SYSTEMS"), [])

    def test_block_of_several_notes_becomes_one_row_per_note(self):
        rows = split_footnotes([row("f1", "footnote", "3For example. 4For example, OMB.",
                                    "³たとえば。4 たとえば、OMB。")])
        self.assertEqual([item["id"] for item in rows], ["f1", "f1-fn4"])
        self.assertEqual(str(rows[1]["english_html"]), '<span class="fn-num">4</span>For example, OMB.')
        self.assertEqual(str(rows[0]["japanese_html"]), '<span class="fn-num">3</span>たとえば。')
        self.assertEqual(str(rows[1]["japanese_html"]), '<span class="fn-num">4</span>たとえば、OMB。')

    def test_japanese_that_cannot_be_cut_keeps_the_block_whole(self):
        rows = split_footnotes([row("f1", "footnote", "3For example. 4For example.", "たとえば。たとえば。")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["footnote_numbers"], [3, 4])

    def test_reference_links_to_its_note_and_note_links_back(self):
        rows = page([row("p1", "paragraph", "Director<sup>3</sup> and OMB.<sup>4</sup>", "長官³およびOMB<sup>4</sup>"),
                     row("f1", "footnote", "3For example. 4For example.", "³たとえば。⁴たとえば。")])
        self.assertIn('href="#f1"', str(rows[0]["english_html"]))
        self.assertIn('href="#f1-fn4"', str(rows[0]["english_html"]))
        self.assertIn('href="#f1"', str(rows[0]["japanese_html"]))
        self.assertNotIn("³", str(rows[0]["japanese_html"]))
        self.assertEqual(rows[1]["footnote_backrefs"], [(3, "p1")])
        self.assertEqual(rows[2]["footnote_backrefs"], [(4, "p1")])

    def test_reference_without_a_nearby_note_stays_plain(self):
        rows = page([row("p1", "paragraph", "x<sup>9</sup>", page=1), row("f1", "footnote", "9 Far away.", page=8)])
        self.assertEqual(str(rows[0]["english_html"]), "x<sup>9</sup>")

    def test_note_moves_to_end_of_referring_section_but_captions_stay(self):
        rows = page([row("h1", "heading", "1 Intro"), row("p1", "paragraph", "refers<sup>1</sup>"),
                     row("h2", "heading", "2 Next"), row("p2", "paragraph", "the text runs"),
                     row("f1", "footnote", "1 A note.", page=2), row("c1", "footnote", "Figure 2. Caption", page=2),
                     row("p3", "paragraph", "on to the next page", page=2), row("h3", "heading", "3 Last", page=2)])
        self.assertEqual([item["id"] for item in rows], ["h1", "p1", "f1", "h2", "p2", "c1", "p3", "h3"])


if __name__ == "__main__":
    unittest.main()
