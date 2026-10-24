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

    def test_sender_list_service_name_and_following_advice_are_one_paragraph(self):
        d=self.document();bs={b['id']:b for b in d['contents']}
        merged=bs['pdf-p0089-b0007']
        self.assertNotIn('pdf-p0090-b0001',bs)
        self.assertEqual([r['page'] for r in merged['source_refs']],[89,90])
        self.assertIn('Spam and Open Relay Blocking System',merged['html'])
        self.assertIn('Spam and Open Relay Blocking System',merged['html_ja'])
        self.assertIn('maintain a dynamic reject list',merged['html'])
        self.assertIn('動的な拒否リスト',merged['html_ja'])
        self.assertIn('pdf-p0090-b0001',{b['id'] for b in d['source_repairs']['original_blocks']})

    def test_mail_footnotes_remain_superscripts_in_both_languages(self):
        bs={b['id']:b for b in self.document()['contents']}
        for block_id,number,joined in [
            ('pdf-p0049-b0002','10','filters10'),
            ('pdf-p0056-b0006','12','DNS12'),
            ('pdf-p0061-b0007','13','[RFC7489]13'),
            ('pdf-p0065-b0001','14','(ARC)14'),
            ('pdf-p0067-b0004','15','clients15'),
            ('pdf-p0070-b0004',['17','18'],'occasions.1718'),
            ('pdf-p0072-b0008','19','OpenSSL19'),
            ('pdf-p0086-b0004',['24','25'],'Symantec24'),
            ('pdf-p0089-b0007',['27','28','29'],'Project27'),
            ('pdf-p0090-b0007','30','checks.30'),
            ('pdf-p0091-b0005','31','component31'),
            ('pdf-p0092-b0001','32','Connect.”32'),
            ('pdf-p0093-b0008','33','IMAP,33'),
        ]:
            for field in ['html','html_ja']:
                with self.subTest(block=block_id,field=field):
                    soup=BeautifulSoup(bs[block_id][field],'html.parser')
                    expected=number if isinstance(number,list) else [number]
                    self.assertEqual([s.get_text() for s in soup.find_all('sup')],expected)
                    self.assertNotIn(joined,bs[block_id][field])
