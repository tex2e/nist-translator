import json
import math
import unittest
from copy import deepcopy
from pathlib import Path

from src.nist_translater.translation import carry_translations

ROOT=Path(__file__).resolve().parents[1]


class SourceBoundaryRepairsTests(unittest.TestCase):
    def document(self,slug):
        return json.loads((ROOT/'data'/f'sp800-{slug}-trans.json').read_text())

    def test_printed_arithmetic_is_not_silently_replaced_by_correct_result(self):
        b=next(b for b in self.document('142')['contents'] if b['id']=='pdf-p0024-r0013')
        self.assertEqual(24**4,331776)
        for field in ('html','html_ja'):
            self.assertIn('331,736',b[field])
            self.assertNotIn('331,776',b[field])
        self.assertIn('331,776',b['math_review_notes'])
        self.assertEqual([r['page'] for r in b['source_refs']],[24,25])

    def test_cross_page_formula_excludes_marginal_quotation(self):
        bs={b['id']:b for b in self.document('142')['contents']}
        body,quote=bs['pdf-p0026-r0009'],bs['pdf-p0026-r0010']
        self.assertNotIn('The larger the system',body['html'])
        self.assertIn('The larger the system',quote['html'])
        self.assertNotIn('possible settings',quote['html'])
        self.assertEqual([r['page'] for r in body['source_refs']],[26,27])
        for n,value in ((3,5984),(4,46376)):
            self.assertEqual(math.comb(34,n),value)
            for field in ('html','html_ja'):
                self.assertIn(r'\binom{34}{'+str(n)+'}',body[field])
                self.assertIn(f'{value:,}',body[field])

    def test_growth_is_display_math_with_equation_number(self):
        b=next(b for b in self.document('142')['contents'] if b['id']=='pdf-p0069-r0006')
        self.assertEqual(b['kind'],'math')
        self.assertEqual(b['html'],r'\[v^t\log n\tag{2}\]')
        self.assertEqual(b['html'],b['html_ja'])

    def test_math_source_region_does_not_claim_next_citation(self):
        bs={b['id']:b for b in self.document('182')['contents']}
        self.assertLess(bs['pdf-p0110-r0107']['source_refs'][0]['bbox'][3],
                        bs['pdf-p0110-r0108']['source_refs'][0]['bbox'][1])
        self.assertLess(bs['pdf-p0110-r0109']['source_refs'][0]['bbox'][3],
                        bs['pdf-p0110-r0110']['source_refs'][0]['bbox'][1])
        self.assertEqual(len(bs['pdf-p0110-r0106']['source_refs']),2)

    def test_source_repairs_survive_carry_and_preserve_unreviewed_neighbors(self):
        for slug in ('142','182'):
            with self.subTest(slug=slug):
                d=self.document(slug);r=d['source_repairs']
                raw={'source_format':'pdf','source_sha256':r['source_sha256'],
                     'included_pages':r['pages'],'contents':deepcopy(r['original_blocks'])}
                current=carry_translations(d,raw)
                expected=[b for b in d['contents'] if b['source_page'] in r['pages']]
                self.assertEqual({b['id']:b for b in current['contents']},
                                 {b['id']:b for b in expected})
                if slug=='182':
                    tail=next(b for b in current['contents'] if b['id']=='pdf-p0110-r0111')
                    self.assertEqual(tail['status'],'untranslated')
