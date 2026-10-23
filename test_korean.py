import unittest
from copy import deepcopy
from pathlib import Path
from korean_core import filename_phones,create_oto,KNOWN,match_existing_template
from vcv_core import recalculate_file,move_boundary

class KoreanTests(unittest.TestCase):
    def test_post_consonant_glides_have_no_independent_label(self):
        from korean_formats import make_record_metadata
        self.assertEqual(filename_phones('캬솨'),['SP','k','a','s','a','SP'])
        self.assertEqual(filename_phones('야와'),['SP','y','a','w','a','SP'])
        for mode in ['ko_cv','ko_cvvc_malcha','ko_cvc_zetty','ko_vcv_diko','ko_coc','ko_cbnn','ko_cmpx']:
            with self.subTest(mode=mode):
                data=make_record_metadata('kya_swa',mode)
                self.assertEqual([p for p in data['phones'] if p!='SP'],['k','a','s','a'])
                self.assertIn('ky',data['source_phones']);self.assertIn('sw',data['source_phones'])
                self.assertEqual(len(data['phones']),len(data['phone_roles']))

    def test_actual_filename_parser(self):
        for path in Path('Natural').glob('*.wav'):self.assertTrue(filename_phones(path.stem))
        self.assertEqual(filename_phones('_baNG\'baN\'baM\'baL\'ba'),
            ['SP','b','a','NG','b','a','N','b','a','M','b','a','L','b','a','SP'])
        self.assertEqual(filename_phones('가나'),['SP','g','a','n','a','SP'])
    def test_decomposed_macos_hangul_filename(self):
        import unicodedata
        from korean_formats import transcribe
        stem='가나';decomposed=unicodedata.normalize('NFD',stem)
        self.assertNotEqual(stem,decomposed)
        self.assertEqual(filename_phones(stem),filename_phones(decomposed))
        self.assertEqual(transcribe(stem,'ko_cv'),transcribe(decomposed,'ko_cv'))
    def test_user_substitutions(self):
        self.assertEqual(filename_phones('fa_va_za_rra_aH'),['SP','h','a','s','a','s','a','L','a','a','axh','SP'])
        self.assertEqual(filename_phones('tha_lwa'),['SP','h','a','L','w','a','SP'])
    def test_alias_substitution_with_shared_suffix_and_number(self):
        record={'wav':'fa.wav','duration':5,'language':'ko',
                'intervals':[[0,1,'SP'],[1,2,'h'],[2,4,'a'],[4,5,'SP']]}
        rows=create_oto(record)
        template=[{'wav':'fa.wav','alias':'- fa_NU','values':[700,500,-1500,1300,300]},
                  {'wav':'fa.wav','alias':'fa_NU1','values':[1200,500,-1500,800,300]}]
        kept=match_existing_template(template,rows,{'fa.wav':5},{'fa.wav':record})
        self.assertEqual([r['alias'] for r in kept],[r['alias'] for r in template])
        self.assertTrue(all(not r.get('mapping_warning') and not r.get('unmapped_template') for r in kept))
    def test_rules_coda_cv_vc_vv_and_live(self):
        spans=[[0,1,'SP'],[1,1.5,'b'],[1.5,3,'a'],[3,3.6,'N'],
               [3.6,4,'n'],[4,5.5,'a'],[5.5,7,'i'],[7,8,'SP']]
        record={'wav':'test.wav','language':'ko','intervals':deepcopy(spans),'duration':8}
        rows=create_oto(record)
        by={r['alias']:r for r in rows}
        self.assertIn('a N',by);self.assertIn('na',by);self.assertIn('a i',by)
        self.assertAlmostEqual(by['- ba']['absolute'][0],.7)
        self.assertAlmostEqual(by['a N']['absolute'][4],3.3)
        self.assertAlmostEqual(by['a N']['absolute'][4]-by['a N']['absolute'][3],.015)
        self.assertAlmostEqual(by['na']['absolute'][4]-by['na']['absolute'][3],.07)
        self.assertAlmostEqual(by['a i']['absolute'][4]-by['a i']['absolute'][3],.04)
        report={'mode':'ko_cvvc','entries':rows};before=deepcopy(rows)
        move_boundary(record,3,3.2);recalculate_file(report,record)
        self.assertNotEqual(rows,before)
        self.assertEqual([r['alias'] for r in rows],[r['alias'] for r in before])

if __name__=='__main__':unittest.main()
