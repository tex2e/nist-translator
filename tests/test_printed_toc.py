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


    def test_part_pages_roman_chapters_and_repeated_titles(self):
        # IR 5424: "— Intro-iii" pages, roman chapters, "A. Introduction" in two chapters
        blocks = [
            block("t", "heading", "TABLE OF CONTENTS"),
            block("l0", "paragraph", "PREFACE — Intro-iii"),
            block("l1", "paragraph", "I. INTRODUCTION — I-1"),
            block("l2", "paragraph", "A. Introduction — I-1"),
            block("l3", "paragraph", "III. ANALYSIS OF SURVEY DATA — III-1"),
            block("l4", "paragraph", "A. Introduction — III-1"),
            block("p", "heading", "PREFACE"),
            block("h1", "heading", "SECTION I. INTRODUCTION"),
            block("a1", "heading", "A. Introduction"),
            block("h3", "heading", "SECTION III. ANALYSIS OF SURVEY DATA"),
            block("a3", "heading", "A. Introduction"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: value["target"] for key, value in toc.items()},
                         {"l0": "p", "l1": "h1", "l2": "a1", "l3": "h3", "l4": "a3"})
        self.assertEqual(toc["l0"]["en"], "PREFACE")

    def test_lists_that_leave_out_the_label(self):
        # tables listed as "III-1 ..." under "LIST OF TABLES"; appendices without page numbers
        blocks = [
            block("t", "heading", "LIST OF TABLES"),
            block("hd", "paragraph", "Table — Content"),
            block("l1", "paragraph", "III-1 Target Agency Survey Participation — III-2"),
            block("l2", "paragraph", "APX(N)-1 Distribution of Responses — Appendix-87"),
            block("a", "heading", "LIST OF APPENDICES"),
            block("ad", "paragraph", "Appendix — Content"),
            block("m1", "paragraph", "A FIRMPOC Survey and Results"),
            block("m2", "paragraph", "B - Vendor List<br>C - Product List"),
            block("x", "paragraph", "This report presents the results of a study."),
            block("c1", "paragraph", "TABLE III-1 TARGET AGENCY SURVEY PARTICIPATION"),
            block("ha", "heading", "APPENDIX A — FIRMPOC SURVEY AND RESULTS"),
            block("hb", "heading", "APPENDIX B"),
            block("hb2", "paragraph", "VENDOR LIST"),
            block("c2", "paragraph", "TABLE APX(N)-1 DISTRIBUTION OF RESPONSES"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: [e["target"] for e in value["entries"]] for key, value in toc.items()},
                         {"l1": ["c1"], "l2": ["c2"], "m1": ["ha"], "m2": ["hb", None]})
        self.assertNotIn("x", toc)

    def test_loose_titles_run_in_headings_and_the_toc_itself(self):
        blocks = [
            block("t", "heading", "TABLE OF CONTENTS"),
            block("l0", "paragraph", "TABLE OF CONTENTS — iii"),
            block("l1", "paragraph", "Network Security Analysis Using Attach Graphs — 2"),
            block("l2", "paragraph", "b. National Documents — 3"),
            block("l3", "paragraph", "The Narrowest Internal Width — 4"),
            block("l4", "paragraph", "Computer Security Division Publications – 2004 — 5"),
            block("h1", "heading", "Network Security Analysis Using Attack Graphs"),
            block("p2", "paragraph", "b. National Documents. National policy and guidance documents include:"),
            block("p3", "paragraph", "The narrowest internal width of a conditioning component is the minimum."),
            block("h3", "heading", "Appendix E—The Narrowest Internal Width"),
            block("h4", "heading", "COMPUTER SECURITY DIVISION PUBLICATIONS - 2005"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: value["target"] for key, value in toc.items()},
                         {"l0": "t", "l1": "h1", "l2": "p2", "l3": "h3", "l4": None})

    def test_list_numbered_differently_from_the_captions(self):
        # SP 800-56A Rev. 3: the list numbers one figure more than the body; the direction decides
        blocks = [
            block("t", "heading", "List of Figures"),
            block("l5", "paragraph", "Figure 5: C(2e, 2s) scheme with unilateral key confirmation from party U to party V — 87"),
            block("l6", "paragraph", "Figure 6: C(2e, 2s) scheme with unilateral key confirmation from party V to party U — 88"),
            block("h", "heading", "6.1 C(2e, 2s) Schemes"),
            block("f4", "paragraph", "Figure 4: C(2e, 2s) scheme with unilateral key confirmation from party U to party V"),
            block("f5", "paragraph", "Figure 5: C(2e, 2s) scheme with unilateral key confirmation from party V to party U"),
        ]
        toc = printed_toc(blocks)
        self.assertEqual({key: value["target"] for key, value in toc.items()}, {"l5": "f4", "l6": "f5"})

if __name__ == "__main__":
    unittest.main()
