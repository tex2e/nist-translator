import json
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]


class MailContinuationTests(unittest.TestCase):
    def document(self):
        return json.loads((ROOT/'data/sp800-177r1-trans.json').read_text())

    def test_key_certification_retains_both_source_fragments_in_one_item(self):
        d=self.document();bs={b['id']:b for b in d['contents']}
        merged=bs['pdf-p0024-b0008']
        self.assertNotIn('pdf-p0025-b0001',bs)
        self.assertEqual([r['page'] for r in merged['source_refs']],[24,25])
        self.assertIn('by any number of parties.',merged['html'])
        self.assertIn('任意の数の主体が署名できる。',merged['html_ja'])
        archive={b['id']:b for b in d['source_repairs']['original_blocks']}
        self.assertIn('pdf-p0025-b0001',archive)
        self.assertIn('pdf-p0024-b0008',archive)
        self.assertEqual(merged['source_merge']['members'],['pdf-p0024-b0008','pdf-p0025-b0001'])

    def test_iana_footnote_is_not_part_of_the_registry_name(self):
        b=next(b for b in self.document()['contents'] if b['id']=='pdf-p0023-b0007')
        for field in ['html','html_ja']:
            soup=BeautifulSoup(b[field],'html.parser')
            self.assertEqual(soup.sup.get_text(),'5')
            self.assertNotIn('registry5',b[field])
            self.assertNotIn('レジストリ5',b[field])
