import unittest

from src.nist_translater.printed_toc import printed_toc, strip_page


def block(id_, kind, html, html_ja=""):
    return {"id": id_, "kind": kind, "html": html, "html_ja": html_ja or html}


class PrintedTocTests(unittest.TestCase):
    def test_page_numbers_and_leaders_are_removed(self):
        self.assertEqual(strip_page("1.1 Purpose — 1"), "1.1 Purpose")
        self.assertEqual(strip_page("Executive Summary ............ iv"), "Executive Summary")
        self.assertEqual(strip_page("Imperative 2 – Risk Management . . . . . 12"), "Imperative 2 – Risk Management")
        self.assertEqual(strip_page("2.4 Interpreting the Pseudocode 6"), "2.4 Interpreting the Pseudocode")

    def test_lines_link_to_headings_with_depth(self):
        blocks = [
            block("t", "heading", "Table of Contents"),
            block("l1", "paragraph", "1 Introduction — 1", "1 はじめに — 1"),
            block("l2", "paragraph", "1.1 Purpose — 2", "1.1 目的 — 2"),
            block("l3", "paragraph", "Table 3: Key types — 5"),
            block("h0", "heading", "3. Identification schemes"),
            block("h1", "heading", "1 Introduction"),
            block("p", "paragraph", "Table 3 provides a summary of the key types used in this guide."),
            block("h2", "heading", "1.1 Purpose"),
            block("c", "table", "<table><caption>Table 3: Key types</caption></table>"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: (value["depth"], value["target"]) for key, value in toc.items()},
                         {"l1": (1, "h1"), "l2": (2, "h2"), "l3": (1, "c")})
        self.assertEqual(toc["l2"]["ja"], "1.1 目的")

    def test_titles_extracted_as_paragraphs_and_bare_list_titles(self):
        blocks = [
            block("t", "paragraph", "Contents"),
            block("l1", "paragraph", "1. Introduction — 1"),
            block("f", "paragraph", "Figures"),
            block("l2", "paragraph", "Figure 1: Overview — 8"),
            block("x", "paragraph", "Figures"),   # a bare "Figures" in body text is not a list title
            block("y", "paragraph", "These figures show the flow."),
            block("h1", "heading", "1. Introduction"),
            block("c", "figure", "<p>Figure 1: Overview</p>"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: value["target"] for key, value in toc.items()}, {"l1": "h1", "l2": "c"})

    def test_chapter_page_numbers_and_merged_lines(self):
        self.assertEqual(strip_page("2.1 Frequency (Monobit) Test........ 2-2"), "2.1 Frequency (Monobit) Test")
        blocks = [
            block("t", "heading", "Table of Contents"),
            block("m", "paragraph", "1. Introduction ......1-1 1.1 General Discussion ......1-1 Fig. 3-1 Overview ...... 31",
                  "1. はじめに ......1-1 1.1 概論 ......1-1 Fig. 3-1 概要 ...... 31"),
            block("h1", "heading", "1. Introduction"),
            block("h2", "heading", "1.1 General Discussion"),
            block("f", "figure", "<p>Figure 3-1 Overview</p>"),
        ]
        entries = printed_toc(blocks)["m"]["entries"]
        self.assertEqual([(e["en"], e["ja"], e["depth"], e["target"]) for e in entries],
                         [("1. Introduction", "1. はじめに", 1, "h1"), ("1.1 General Discussion", "1.1 概論", 2, "h2"),
                          ("Fig. 3-1 Overview", "Fig. 3-1 概要", 1, "f")])

    def test_untitled_toc_title_lines_and_page_styles(self):
        self.assertEqual(strip_page("Executive Summary ............ ES-1"), "Executive Summary")
        self.assertEqual(strip_page("Appendix D— Acquisition .......... D–1"), "Appendix D— Acquisition")
        self.assertEqual(strip_page("2.1 System Description………....………A.1-5"), "2.1 System Description")
        blocks = [
            block("cover", "paragraph", "Standard for Personal Identity Verification"),
            block("a", "paragraph", "1. Introduction . . . . . . . . . . 1"),
            block("b", "paragraph", "1.1 Purpose . . . . . . . . . . 1"),
            block("c", "paragraph", "2.0 Basis . . . . . . . . . . 3"),
            block("d", "paragraph", "2.1 Scope . . . . . . . . . . 4"),
            block("t", "heading", "Table of Contents"),
            block("x", "paragraph", "Federal Information Processing Standards Publication 204"),
            block("y", "heading", "Specification for the Standard"),
            block("e", "paragraph", "1 Introduction 1"),
            block("f", "paragraph", "1.1 Purpose and Scope . . . . . . . . 1"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: value["depth"] for key, value in toc.items()},
                         {"a": 1, "b": 2, "c": 1, "d": 2, "e": 1, "f": 2})


if __name__ == "__main__":
    unittest.main()
