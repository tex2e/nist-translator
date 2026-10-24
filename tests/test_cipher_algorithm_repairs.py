import json
import unittest
from pathlib import Path
from copy import deepcopy
from bs4 import BeautifulSoup
from src.nist_translater.translation import carry_translations,assert_same_html_structure

ROOT=Path(__file__).resolve().parents[1]


class CipherAlgorithmRepairTests(unittest.TestCase):
    def document(self,slug):return json.loads((ROOT/'data'/f'sp800-{slug}-trans.json').read_text())
    def block(self,slug,bid):return next(b for b in self.document(slug)['contents'] if b['id']==bid)

    def test_multiplication_cases_and_return_are_distinct_numbered_steps(self):
        b=self.block('38d','pdf-p0019-r0010')
        for field in ['html','html_ja']:
            soup=BeautifulSoup(b[field],'html.parser');top=soup.ol
            self.assertEqual(top['start'],'3')
            self.assertEqual(len(top.find_all('li',recursive=False)),2)
            tex=soup.get_text()
            self.assertEqual(tex.count(r'\begin{cases}'),2)
            for value in ['x_i=0','x_i=1',r'\operatorname{LSB}_1(V_i)=0',r'\operatorname{LSB}_1(V_i)=1',r'Z_{128}',r'Z_i\oplus V_i']:
                self.assertIn(value,tex)
        self.assertEqual([r['page'] for r in b['source_refs']],[19,20])

    def test_gctr_last_partial_block_and_three_final_steps_are_preserved(self):
        b=self.block('38d','pdf-p0021-r0014')
        for f in ['html','html_ja']:
            soup=BeautifulSoup(b[f],'html.parser')
            self.assertEqual(soup.ol['start'],'7')
            self.assertEqual(len(soup.ol.find_all('li',recursive=False)),3)
            text=soup.get_text()
            self.assertIn(r'Y_n^*=X_n^*\oplus',text)
            self.assertIn(r'\operatorname{MSB}_{\operatorname{len}(X_n^*)}',text)
            self.assertIn(r'Y=Y_1\parallel Y_2\parallel\ldots\parallel Y_n^*',text)
        self.assertIn('手順8',b['math_review_notes'])
        partial=self.block('38d','pdf-p0021-r0010')
        self.assertEqual(BeautifulSoup(partial['html'],'html.parser').sup.get_text(),'2')
        self.assertEqual(self.block('38d','pdf-p0021-math-090')['kind'],'footnote')

    def test_wrapping_nested_steps_keep_iteration_time_separate_from_block_index(self):
        b=self.block('38f','pdf-p0019-r0009')
        for f in ['html','html_ja']:
            soup=BeautifulSoup(b[f],'html.parser');steps=soup.ol.find_all('li',recursive=False)
            self.assertEqual(len(steps),3)
            self.assertEqual([len(li.ol.find_all('li',recursive=False)) for li in steps],[4,3,3])
            text=soup.get_text()
            for value in [r'n\ge3','s=6(n-1)','A^0=S_1','R_i^0=S_i','A^{t-1}',r'R_2^{t-1}',r'\oplus[t]_{64}','R_i^t=R_{i+1}^{t-1}','C_i=R_i^s']:
                self.assertIn(value,text)
        self.assertEqual({r['page'] for r in b['source_refs']},{19,20})

    def test_authenticated_unwrap_checks_every_rejection_before_returning_plaintext(self):
        b=self.block('38f','pdf-p0023-r0005')
        for f in ['html','html_ja']:
            soup=BeautifulSoup(b[f],'html.parser');steps=soup.ol.find_all('li',recursive=False)
            self.assertEqual(len(steps),9)
            self.assertIn(r'\operatorname{CIPH}^{-1}_K(C)',steps[2].get_text())
            self.assertIn(r'\operatorname{W}^{-1}(C)',steps[2].get_text())
            for i in [3,6,7]:self.assertIn('FAIL',steps[i].get_text())
            self.assertIn(r'\mathit{padlen}<0',steps[6].get_text())
            self.assertIn(r'\mathit{padlen}>7',steps[6].get_text())
            self.assertIn(r'\mathtt{0}^{8\mathit{padlen}}',steps[7].get_text())
            self.assertIn(r'\operatorname{MSB}_{8\mathit{Plen}}',steps[8].get_text())
            self.assertIn('A65959A6',steps[1].get_text())
        self.assertEqual({r['page'] for r in b['source_refs']},{23,24})

    def test_pinned_algorithm_pages_survive_reparse_without_changing_neighbor_status(self):
        for slug in ['38d','38f']:
            d=self.document(slug);r=d['source_repairs']
            raw={'source_format':'pdf','source_sha256':r['source_sha256'],'included_pages':r['pages'],'contents':deepcopy(r['original_blocks'])}
            out=carry_translations(d,raw)
            self.assertEqual({b['id']:b for b in out['contents']},{b['id']:b for b in d['contents'] if b['source_page'] in r['pages']})

    def test_every_candidate_has_current_source_and_translation_evidence(self):
        s=json.loads((ROOT/'reports/math-candidate-status.json').read_text());self.assertEqual(len(s['items']),20)
        for item in s['items']:
            self.assertEqual(item['status'],'source_and_translation_checked_final_display_pending')
            d=json.loads((ROOT/'data'/f"{item['document']}-trans.json").read_text());bs={b['id']:b for b in d['contents']}
            for v in item['current_blocks']:
                self.assertEqual(bs[v['id']]['source_hash'],v['source_hash'])
                self.assertEqual(bs[v['id']]['status'],'reviewed')
