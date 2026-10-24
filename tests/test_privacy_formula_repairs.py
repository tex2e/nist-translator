import json
import unittest
from pathlib import Path
from copy import deepcopy
from bs4 import BeautifulSoup

from src.nist_translater.translation import carry_translations
from src.nist_translater.source_quality import encoding_issues, assert_publishable_source

ROOT=Path(__file__).resolve().parents[1]


class PrivacyFormulaRepairTests(unittest.TestCase):
    def document(self,slug):
        return json.loads((ROOT/'data'/f'sp800-{slug}-trans.json').read_text())

    def test_furniture_label_cannot_conceal_a_broken_math_fragment(self):
        b={'id':'broken-fragment','source_page':49,'kind':'paragraph',
           'html':'�,','html_ja':'','page_furniture':True}
        d={'contents':[b]}
        self.assertEqual(encoding_issues(d)[0]['id'],'broken-fragment')
        with self.assertRaisesRegex(ValueError,'repair source before publishing'):
            assert_publishable_source(d)

    def test_formula_fragments_are_repaired_and_linked_instead_of_page_furniture(self):
        bs={b['id']:b for b in self.document('90b')['contents']}
        for bid,parent,html in [('pdf-p0049-r0015','pdf-p0049-math-444','),'),
                                ('pdf-p0054-r0001','pdf-p0054-math-259',r'\(\bar{X}=\)')]:
            b=bs[bid]
            self.assertEqual(b['math_duplicate_of'],parent)
            self.assertFalse(b.get('page_furniture'))
            self.assertEqual(b['html'],html)
            self.assertEqual(b['extraction_status'],'verified')
            self.assertEqual(b['math_duplicate_check']['retained_source_hash'],bs[parent]['source_hash'])
            outer=bs[parent]['source_refs'][0]['bbox'];inner=b['source_refs'][0]['bbox']
            self.assertTrue(outer[0]<=inner[0]<=inner[2]<=outer[2])
            self.assertTrue(outer[1]<=inner[1]<=inner[3]<=outer[3])

    def test_sensitivity_definitions_keep_their_distinct_norms(self):
        bs={b['id']:b for b in self.document('226')['contents']}
        for n,index in [(1,124),(2,127)]:
            b=bs[f'pdf-p0085-math-{index}']
            for f in ('html','html_ja'):
                self.assertIn(r'\Delta_'+str(n),b[f])
                self.assertIn(r'\rVert_'+str(n),b[f])
                self.assertIn(r'\max_',b[f])
        duplicate=bs['pdf-p0085-r0011']
        self.assertEqual(duplicate['math_duplicate_of'],'pdf-p0085-math-124')
        self.assertEqual({r['page'] for r in duplicate['source_refs']},{85})
        self.assertLess(max(r['bbox'][3] for r in duplicate['source_refs']),500)

    def test_definition_boxes_are_separate_paragraphs_and_heading_has_no_nested_p(self):
        bs={b['id']:b for b in self.document('226')['contents']}
        for index in [119,123,126]:
            for f in ('html','html_ja'):
                self.assertEqual(len(BeautifulSoup(bs[f'pdf-p0085-math-{index}'][f],'html.parser').find_all('p')),2)
        heading=bs['pdf-p0085-math-118']
        self.assertEqual(heading['kind'],'heading')
        self.assertEqual(heading['level'],3)
        self.assertNotIn('<p>',heading['html'])

    def test_continuing_explanation_does_not_claim_the_l2_formula(self):
        bs={b['id']:b for b in self.document('226')['contents']}
        self.assertEqual([r['page'] for r in bs['pdf-p0085-r0017']['source_refs']],[85,86])
        self.assertGreater(bs['pdf-p0085-r0017']['source_refs'][0]['bbox'][1],
                           max(r['bbox'][3] for r in bs['pdf-p0085-math-128']['source_refs']))

    def test_l2_equation_precedes_the_following_explanation(self):
        order=[b['id'] for b in self.document('226')['contents']]
        self.assertLess(order.index('pdf-p0085-math-127'),order.index('pdf-p0085-math-128'))
        self.assertLess(order.index('pdf-p0085-math-128'),order.index('pdf-p0085-r0017'))

    def test_repairs_and_archive_are_preserved_on_reparse(self):
        for slug in ('90b','226'):
            d=self.document(slug);r=d['source_repairs']
            raw={'source_format':'pdf','source_sha256':r['source_sha256'],
                 'included_pages':r['pages'],'contents':deepcopy(r['original_blocks'])}
            out=carry_translations(d,raw)
            self.assertEqual(out['included_pages'],r['pages'])
            self.assertEqual({b['id']:b for b in out['contents']},
                             {b['id']:b for b in d['contents'] if b['source_page'] in r['pages']})

    def test_fragment_of_next_page_does_not_certify_that_page_as_complete(self):
        d=self.document('226');r=d['source_repairs']
        raw={'source_format':'pdf','source_sha256':r['source_sha256'],
             'included_pages':[85], 'pdf_page_count':2, 'contents':deepcopy(r['original_blocks'])}
        # A compact fixture with page 1 pinned and a reference into page 2.
        kept=deepcopy(d['contents'][0]);kept.update(source_page=1,
            source_refs=[{'page':1,'bbox':[1,2,3,4]},{'page':2,'bbox':[1,2,3,4]}])
        prev={'source_sha256':r['source_sha256'],'contents':[kept],
              'source_repairs':{'source_sha256':r['source_sha256'],'pages':[1]}}
        raw.update(included_pages=[1],contents=[])
        from src.nist_translater.pdf_source_repairs import preserve_source_repairs
        out=preserve_source_repairs(prev,raw)
        self.assertEqual(out['included_pages'],[1])
        self.assertTrue(out['extraction_partial'])
