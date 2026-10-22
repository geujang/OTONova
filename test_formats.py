import unittest
from copy import deepcopy
from pathlib import Path
from formats import FORMATS,is_korean
from korean_formats import make_record_metadata,create_oto,match_template
from korean_core import filename_phones,AUXILIARY
from vcv_core import create_oto as japanese_oto,parse_name,recalculate_file,move_boundary,output_dir

def record(stem,mode):
    data=make_record_metadata(stem,mode)
    data.update(wav=stem+'.wav',duration=float(len(data['phones'])),language='ko',
                intervals=[[float(i),float(i+1),p] for i,p in enumerate(data['phones'])])
    return data

class FormatTests(unittest.TestCase):
    def test_every_format_has_separate_output_and_language(self):
        self.assertEqual(len({str(output_dir('bank',mode)) for mode in FORMATS}),len(FORMATS))
        for mode in FORMATS:self.assertEqual(is_korean(mode),mode.startswith('ko_'))

    def test_japanese_cv_uses_initial_rule_and_kana_alias(self):
        spans=[[0,1,'pau'],[1,1.5,'k'],[1.5,3,'a'],[3,4,'pau']]
        rows=japanese_oto('カ.wav',parse_name('カ'),spans,4,'ja_cv')
        self.assertEqual([r['alias'] for r in rows],['か'])
        self.assertAlmostEqual(rows[0]['absolute'][0],.7)
        self.assertAlmostEqual(rows[0]['absolute'][4]-rows[0]['absolute'][3],.07)

    def test_korean_cv_and_source_spelling(self):
        data=record('가','ko_cv');rows=create_oto(data,'ko_cv')
        self.assertIn('가',[r['alias'] for r in rows])
        self.assertIn('ga',[r['alias'] for r in rows])
        data=record('fa_va_za_rra_tha','ko_cv')
        self.assertEqual(data['phones'],['SP','h','a','s','a','s','a','L','a','h','a','SP'])
        self.assertTrue({'fa','va','za','rra','tha'}<={r['alias'] for r in create_oto(data,'ko_cv')})

    def test_cvc_spellings_and_closure_aliases(self):
        for mode in ['ko_cvc_zetty','ko_cvc_binbin','ko_cvc_gyutaeng']:
            data=record("gga'gga'ggi_an'ga",mode)
            self.assertIn('kk',data['phones']);self.assertIn('N',data['phones'])
            aliases={r['alias'] for r in create_oto(data,mode)}
            self.assertTrue({'gga','ggi','an','a n','a gg','ak','n g'}<=aliases)
        self.assertEqual(filename_phones('rere','ko_cvc_zetty'),['SP','r','e','r','e','SP'])

    def test_malcha_internal_rests_and_long_vcv(self):
        for mode in ['ko_cvvc_malcha','ko_vcv_malcha7','ko_vcv_malcha15']:
            data=record("_ga'ga'_'na'na'-'da'da",mode)
            self.assertEqual(data['phones'].count('SP'),4)
            aliases={r['alias'] for r in create_oto(data,mode)}
            self.assertTrue({'- ga','- na','- da'}<=aliases)
        data=record("ga'ga'gi",'ko_vcv_malcha7')
        self.assertIn('a gi',{r['alias'] for r in create_oto(data,'ko_vcv_malcha7')})

    def test_diko_batchim_and_diphthong(self):
        for mode in ['ko_vcv_diko','ko_vcv_diko_ex']:
            data=record("N'gaN'hui",mode);rows=create_oto(data,mode)
            self.assertTrue({'n ga','n hui'}<={r['alias'] for r in rows})
            self.assertIn('vowel_continuation',data['phone_roles'])
        self.assertEqual(filename_phones('_aaeoaeaoaNGH','ko_vcv_diko_ex')[:4],['SP','a','a','eo'])

    def test_tabi_uppercase_cc_and_fry(self):
        for mode in ['ko_cvvc_tabi','ko_cvvc_tabi_old']:
            data=record("_giNG'giN'gi",mode)
            aliases={r['alias'] for r in create_oto(data,mode)}
            self.assertTrue({'NG g','NG gy','N g','i NG'}<=aliases)
        data=record('_a(vf)','ko_cvvc_tabi')
        self.assertEqual(data['phones'],['SP','vf','a','vf','SP'])
        self.assertTrue({'*a','a *'}<={r['alias'] for r in create_oto(data,'ko_cvvc_tabi')})

    def test_template_preserves_aliases_and_live_derived_rows(self):
        mode='ko_cvvc_tabi';data=record('_neuNG','ko_cvvc_tabi');rows=create_oto(data,mode)
        original=[{'wav':data['wav'],'alias':alias,'values':[0,0,0,0,0]} for alias in ['- n','neu','eu NG']]
        result=match_template(original,rows,{data['wav'].casefold():data['duration']},{data['wav'].casefold():data},mode)
        self.assertEqual([r['alias'] for r in result],[r['alias'] for r in original])
        self.assertTrue(all(r['absolute'][4]>0 for r in result))
        report={'mode':mode,'entries':result};before=deepcopy(result[0]['absolute'])
        move_boundary(data,1,1.2);recalculate_file(report,data)
        self.assertNotEqual(report['entries'][0]['absolute'],before)
        self.assertEqual(report['entries'][0]['alias'],'- n')

    def test_auxiliary_phones_are_preserved_until_model_inference(self):
        data=record('dha_tsa_er_@r','ko_cvc_gyutaeng_plus')
        self.assertTrue({'dh','ts','er','@r'}<=set(data['phones']))
        self.assertEqual(AUXILIARY,{'dh':('en','dh','d'),'ts':('ja','ts','ch'),
                                    'er':('en','r','L'),'@r':('en','r','L')})

if __name__=='__main__':unittest.main()
