import unittest

from src.nist_translater.render import heading_text, toc_entries


def headings(*texts):
    return [{"id": "h%d" % index, "text": text, "text_ja": text, "level": 1} for index, text in enumerate(texts)]


class TocTests(unittest.TestCase):
    def depths(self, *texts):
        return [entry["depth"] for entry in toc_entries(headings(*texts))]

    def test_depth_comes_from_the_section_number(self):
        self.assertEqual(self.depths("1. Introduction", "1.1 Purpose", "1.1.2 Scope", "2 Terms"), [1, 2, 3, 1])
        self.assertEqual(self.depths("Appendix A. References", "A.1 Normative", "B.2.3 Deep"), [1, 2, 3])
        self.assertEqual(self.depths("10.4.2.1.3 Very deep"), [4])

    def test_unnumbered_headings(self):
        # front matter stays at the top level; later ones sit under the numbered heading before them
        self.assertEqual(self.depths("Abstract", "Keywords", "3.2 Usage", "Note on usage"), [1, 1, 2, 3])

    def test_a_capital_word_is_not_a_section_number(self):
        self.assertEqual(self.depths("1 Scope", "A Glossary entry"), [1, 2])

    def test_heading_text_drops_tex_delimiters_and_empty_headings(self):
        self.assertEqual(heading_text(r"<h3>Algorithm 1 \(\mathsf{KeyGen}\)</h3>"), r"Algorithm 1 \mathsf{KeyGen}")
        self.assertEqual(toc_entries(headings("", "1 Scope"))[0]["text"], "1 Scope")


if __name__ == "__main__":
    unittest.main()
