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
        self.assertEqual(footnote_numbers("2: During FY 2016, Mr. Jon Boyens"), [2])
        self.assertEqual(footnote_numbers("1 * See Glossary definition"), [1])
        self.assertEqual(footnote_numbers("2 &lt;PrintedName&gt; in"), [2])
        self.assertEqual(footnote_numbers("7 \\(b\\) will be the value"), [7])
        self.assertEqual(footnote_numbers("1.1 Scope"), [])

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

    def test_grouped_references_link_each_note(self):
        rows = page([row("p1", "paragraph", "model:<sup>36,37</sup> data", "モデル:<sup>36,37</sup> データ"),
                     row("f1", "footnote", "36 One."), row("f2", "footnote", "37 Two.")])
        self.assertIn('href="#f1"', str(rows[0]["english_html"]))
        self.assertIn('href="#f2"', str(rows[0]["japanese_html"]))

    def test_footnote_can_refer_to_another_footnote(self):
        rows = page([row("p1", "paragraph", "text<sup>54</sup>"),
                     row("f1", "footnote", "54 Derived from related information<sup>55</sup> and 2<sup>32</sup>."),
                     row("f2", "footnote", "55 Another note."), row("f3", "footnote", "32 Unrelated.")])
        note = next(r for r in rows if r["id"] == "f1")
        self.assertIn('href="#f2"', str(note["english_html"]))
        self.assertIn("2<sup>32</sup>", str(note["english_html"]))

    def test_space_separated_group_links_each(self):
        rows = page([row("p1", "paragraph", "Measures<sup>90 91</sup>"),
                     row("f1", "footnote", "90 One."), row("f2", "footnote", "91 Two.")])
        self.assertIn('href="#f2"', str(rows[0]["english_html"]))

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
        # an exponent (after a digit) never links to a far note
        rows = page([row("p1", "paragraph", "2<sup>9</sup>", page=1), row("f1", "footnote", "9 Far away.", page=8)])
        self.assertEqual(str(rows[0]["english_html"]), "2<sup>9</sup>")
        # a far note links only when it is the document's one note with that number
        rows = page([row("p1", "paragraph", "x<sup>9</sup>", page=1), row("f1", "footnote", "9 Far.", page=8),
                     row("f2", "footnote", "9 Another.", page=20)])
        self.assertEqual(str(rows[0]["english_html"]), "x<sup>9</sup>")

    def test_endnote_far_away_links_when_unique(self):
        rows = page([row("p1", "paragraph", "the Guidelines.<sup>9</sup>", page=1),
                     row("f1", "footnote", "9 Endnote.", page=30)])
        self.assertIn('href="#f1"', str(rows[0]["english_html"]))

    def test_html_footnotes_are_numbered_by_their_run(self):
        rows = split_footnotes([row("h1", "footnote", "First note. ↩", page=None),
                                row("h2", "footnote", "Second note. ↩", page=None),
                                row("p1", "paragraph", "text", page=None),
                                row("h3", "footnote", "Again first. ↩", page=None)])
        self.assertEqual([r.get("footnote_numbers") for r in rows], [[1], [2], None, [1]])
        self.assertEqual(str(rows[1]["english_html"]), '<span class="fn-num">2</span>Second note.')

    def test_html_reference_to_the_nist_site_links_here(self):
        rows = page([row("p1", "paragraph", 'id<sup><a href="https://pages.nist.gov/x.html#fn:GovID">1</a></sup>', page=None),
                     row("h1", "footnote", "A note. ↩", page=None)])
        self.assertIn('href="#h1"', str(rows[0]["english_html"]))
        self.assertNotIn("pages.nist.gov", str(rows[0]["english_html"]))

    def test_note_moves_to_end_of_referring_section_but_captions_stay(self):
        rows = page([row("h1", "heading", "1 Intro"), row("p1", "paragraph", "refers<sup>1</sup>"),
                     row("h2", "heading", "2 Next"), row("p2", "paragraph", "the text runs"),
                     row("f1", "footnote", "1 A note.", page=2), row("c1", "footnote", "Figure 2. Caption", page=2),
                     row("p3", "paragraph", "on to the next page", page=2), row("h3", "heading", "3 Last", page=2)])
        self.assertEqual([item["id"] for item in rows], ["h1", "p1", "f1", "h2", "p2", "c1", "p3", "h3"])


if __name__ == "__main__":
    unittest.main()
