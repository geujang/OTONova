import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import csv,json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from arpasing_core import ArpasingResolver,parse_sequence,catalog,create_oto,match_template,EnglishEngine
from vcv_core import recalculate_file,move_boundary,run_folder,save_record,persist_report,RULES_VERSION

def record():
    units,_=parse_sequence('hh_ah_l_ow_w_er_l_d')
    phones=['SP'];mapped=[]
    for u in units:
        ids=list(range(len(phones),len(phones)+len(u['model'])));phones+=u['model'];mapped.append(dict(phone=u['phone'],indices=ids))
    phones+=['SP']
    return dict(wav='001.wav',language='en',phones=phones,arpasing_units=mapped,duration=len(phones),
        intervals=[[float(i),float(i+1),p] for i,p in enumerate(phones)])

class ArpasingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def touch(self,name):
        path=self.folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch();return path
    def index(self,rows,name='index.csv',delimiter=','):
        with (self.folder/name).open('w',encoding='utf-8-sig',newline='') as stream:csv.writer(stream,delimiter=delimiter).writerows(rows)

    def test_model_spelling_and_no_foreign_substitution(self):
        units,notes=parse_sequence('F_V_Z_DX_Q_DR_TR')
        self.assertEqual([u['phone'] for u in units],['f','v','z','dx','q','dr','tr'])
        for value in ['ix','rr','aar','h','ɜ','ae\'','@r','6l','dd']:
            with self.assertRaises(ValueError):parse_sequence(value)
        self.assertEqual(parse_sequence('kr_st')[0],[{'phone':'kr','model':['k','r']},{'phone':'st','model':['s','t']}])

    def test_index_word_and_semicolon_uppercase_missing_extension(self):
        wav=self.touch('word.wav');self.index([['word','HH_AH_L_OW','']],name='index_Ag.csv',delimiter=';')
        metadata=ArpasingResolver(self.folder).metadata(wav)
        self.assertEqual(metadata['phones'],['SP','hh','ah','l','ow','SP'])
        self.assertEqual(metadata['input_source'],'index_Ag.csv')

    def test_foreign_index_not_ignored_for_filename(self):
        wav=self.touch('aa_iy.wav');self.index([['aa_iy.wav','ɑ_i']])
        with self.assertRaises(ValueError):ArpasingResolver(self.folder).metadata(wav)

    def test_invalid_filename_never_loses_unknown_phones(self):
        for name in ['aa_ix_iy.wav','aa_rr_iy.wav',"aa'_iy.wav"]:
            wav=self.touch(name)
            with self.assertRaises(ValueError):ArpasingResolver(self.folder).metadata(wav)

    def test_builtin_identifier_and_prefixed_suffix(self):
        wav=self.touch('prefix_a00_C4.wav')
        data=ArpasingResolver(self.folder).metadata(wav)
        self.assertEqual(data['phones'][1:-1],['ao','ao','aa','ao','iy','ao'])

    def test_ambiguous_numeric_bank_requires_index(self):
        wav=self.touch('001.wav')
        with self.assertRaisesRegex(ValueError,'index.csv'):ArpasingResolver(self.folder).metadata(wav)

    def test_dx_override_only_matches_registered_append(self):
        wav=self.touch('_EN_00516_dx(EX).wav');self.index([[wav.name,'aa_d_ae_d_aa']])
        data=ArpasingResolver(self.folder).metadata(wav)
        self.assertEqual(data['phones'][1:-1],['aa','dx','ae','dx','aa'])
        self.index([[wav.name,'aa_d_aa']]);data=ArpasingResolver(self.folder).metadata(wav)
        self.assertEqual(data['phones'][1:-1],['aa','d','aa'])

    def test_nested_same_basename_uses_scoped_indexes(self):
        first=self.touch('low/001.wav');second=self.touch('high/001.wav')
        (first.parent/'index.csv').write_text('001.wav,aa_b\n',encoding='utf-8')
        (second.parent/'index.csv').write_text('001.wav,iy_d\n',encoding='utf-8')
        resolver=ArpasingResolver(self.folder)
        self.assertEqual(resolver.metadata(first)['phones'],['SP','aa','b','SP'])
        self.assertEqual(resolver.metadata(second)['phones'],['SP','iy','d','SP'])
        self.assertEqual(resolver.metadata(second)['wav'],'high/001.wav')

    def test_catalog_exclusions_and_duplicates(self):
        data=catalog();ids={int(p['id'].split('-')[0]) for p in data['profiles']}
        self.assertTrue({6,8,16,18}.isdisjoint(ids));self.assertEqual(len(ids),21)
        self.assertTrue(any(p['duplicates']>0 for p in data['profiles']))

    def test_diphone_rules_and_live_existing_aliases(self):
        data=record();rows=create_oto(data)
        self.assertTrue({'- hh','hh ah','ah l','l ow','ow w','w er','er l','l d','d -'}<={r['alias'] for r in rows})
        template=[dict(wav='001.wav',alias=r['alias']+'_EN',values=r['values']) for r in rows]
        matched=match_template(template,rows,{'001.wav':data['duration']},{'001.wav':data})
        self.assertEqual([r['alias'] for r in matched],[r['alias'] for r in template])
        self.assertFalse(any(r.get('unmapped_template') for r in matched))
        with_outlier=match_template(template+[dict(wav='failed.wav',alias='keep_original',values=[100,200,-300,40,20])],rows,{'001.wav':data['duration']},{'001.wav':data})
        self.assertFalse(any(r.get('unmapped_template') for r in with_outlier[:-1]))
        self.assertEqual(with_outlier[-1]['values'],[100,200,-300,40,20])
        before=deepcopy(matched);report={'mode':'en_arpasing','entries':matched}
        move_boundary(data,2,2.2);recalculate_file(report,data)
        self.assertNotEqual([r['absolute'] for r in before],[r['absolute'] for r in report['entries']])
        self.assertEqual([r['alias'] for r in report['entries']],[r['alias'] for r in template])
        for row in rows:
            if row['entry_kind']=='cv':self.assertAlmostEqual(row['absolute'][4]-row['absolute'][3],.07)
            if row['entry_kind'] in ['vc','cc']:self.assertAlmostEqual(row['absolute'][4]-row['absolute'][3],.015)

    def test_nested_unmapped_alias_follows_boundary(self):
        data=record();data['wav']='pitch/001.wav';rows=create_oto(data)
        template=[dict(wav='pitch\\001.wav',alias='custom',values=[2100,300,-600,100,50])]
        matched=match_template(template,rows,{data['wav']:data['duration']},{data['wav']:data})
        self.assertTrue(matched[0].get('boundary_anchors'))
        before=list(matched[0]['absolute']);move_boundary(data,2,2.3)
        recalculate_file({'mode':'en_arpasing','entries':matched},data)
        self.assertNotEqual(before,matched[0]['absolute'])

    def test_cache_keeps_manual_boundaries_without_loading_backend(self):
        wav=self.touch('hh_ah_l_ow_w_er_l_d.wav');data=record();data['wav']=wav.name
        data.update(sha256=__import__('hashlib').sha256(b'').hexdigest(),manually_edited=True)
        cache=self.folder/'cache';cache.mkdir();(cache/wav.with_suffix('.json').name).write_text(json.dumps(data),encoding='utf-8')
        model_root=self.folder/'models';model=model_root/'English';model.mkdir(parents=True)
        (model/'last.ckpt').write_bytes(b'unit-test model signature')
        (model/'phonemes.txt').write_text((Path(__file__).parent/'English/phonemes.txt').read_text(encoding='utf-8'),encoding='utf-8')
        with patch('vcv_core.WORKSPACE',model_root):engine=EnglishEngine(self.folder)
        with patch('korean_core.KoreanEngine',side_effect=AssertionError('should not load model')):
            rows,result=engine.analyze(wav,cache)
        self.assertEqual(result['intervals'],data['intervals']);self.assertTrue(rows);engine.close()

    def test_gui_english_report_two_stages(self):
        import numpy as np,soundfile as sf
        from PySide6.QtWidgets import QApplication
        from vcv_gui import Window
        app=QApplication.instance() or QApplication([])
        data=record();sf.write(self.folder/'001.wav',np.zeros(16000*10),16000)
        self.index([['001.wav','hh_ah_l_ow_w_er_l_d']])
        save_record(self.folder,data);rows=create_oto(data)
        report=dict(mode='en_arpasing',rules_version=RULES_VERSION,files=1,successful_files=1,entries=rows,failures=[],duplicates_removed=0)
        persist_report(self.folder,report)
        window=Window();window.folder.setText(str(self.folder));window.set_mode('en_arpasing')
        self.assertEqual(window.mode,'en_arpasing');self.assertIsNotNone(window.report)
        window.set_stage(2);self.assertEqual(window.wave.stage,2);window.close()

if __name__=='__main__':unittest.main()
