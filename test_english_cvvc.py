import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from english_cvvc import catalog, detect, parse_sequence, create_oto, match_template, CvvcResolver

COMMON = '_+_@-p@-b@-t@-d@-k@-g@'
LITE = '_+_@-n@-N@-j@-w@-l@-r@-4@'


class RecognitionTests(unittest.TestCase):
    def test_catalog_and_case_sensitive_xsampa(self):
        self.assertEqual(len(catalog()['profiles']), 36)
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, '_+_A-tSA-dZA-fA-vA-TA-DA.wav').touch()
            self.assertEqual(detect(folder)['recognized_files'], 1)
            Path(folder, '_+_A-tSA-dZA-fA-vA-TA-DA.wav').unlink()
            Path(folder, '_+_A-tSA-dZA-fA-vA-TA-DA'.lower()+'.wav').touch()
            self.assertEqual(detect(folder)['recognized_files'], 0)

    def test_affixes_subfolders_and_partial_bank(self):
        with tempfile.TemporaryDirectory() as folder:
            sub = Path(folder, 'A4');sub.mkdir()
            Path(sub, '強_'+LITE+'_softA4.WAV').touch()
            Path(sub, 'unknown.wav').touch()
            result = detect(folder)
            self.assertEqual(result['profile'], 'LITE_8_core')
            self.assertEqual(result['recognized_files'], 1)
            self.assertIn('일부 WAV', result['warning'])

    def test_common_items_remain_ambiguous(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, COMMON+'.wav').touch()
            result = detect(folder)
            self.assertIsNone(result['profile'])
            self.assertIn('LITE_8_core', result['candidates'])
            self.assertIn('FULL_8_core', result['candidates'])
            self.assertTrue(result['warning'])

    def test_text_and_original_oto_names(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'reclist.txt').write_text(LITE, encoding='utf-16')
            result = detect(folder, [{'wav': LITE+'.wav', 'alias': 'original'}])
            self.assertEqual(result['profile'], 'LITE_8_core')
            self.assertEqual(result['list_matches'], 1)
            self.assertEqual(result['recognized_files'], 0)

    def test_delta_mapping_and_excluded_lists(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('_d+e.wav','_d+E.wav','01_A_b_01.wav'):Path(folder,name).touch()
            resolver=CvvcResolver(folder)
            a=resolver.metadata(Path(folder,'_d+e.wav'));b=resolver.metadata(Path(folder,'_d+E.wav'))
            self.assertEqual(a['phones'],['SP','dh','eh','SP'])
            self.assertEqual(a['phones'],b['phones'])
            with self.assertRaises(ValueError):resolver.metadata(Path(folder,'01_A_b_01.wav'))

    def test_gui_alignment_enabled(self):
        from PySide6.QtWidgets import QApplication
        from vcv_gui import Window
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, LITE+'.wav').touch()
            window = Window();window.folder.setText(folder)
            window.set_mode('en_cvvc')
            self.assertIn('OTONova V2.0', window.windowTitle())
            self.assertFalse(window.windowIcon().isNull())
            self.assertEqual(window.files.count(), 1)
            self.assertIsNone(window.report)
            self.assertFalse(window.save.isEnabled())
            self.assertTrue(all(b.isEnabled() for b in window.stage_buttons))
            self.assertIn('자동원설',window.generate.text())
            window.set_mode('vcv')
            self.assertTrue(all(b.isEnabled() for b in window.stage_buttons))
            window.close();app.processEvents()


class MappingTests(unittest.TestCase):
    def test_user_corrections_and_case(self):
        u,_=parse_sequence('ju_ts_dz_{+_a_o_e_d+e_d+E')
        self.assertEqual([p for x in u for p in x['model']],
                         'y uh t s d z ae aa ao eh dh eh dh eh'.split())
        self.assertEqual(parse_sequence('i_I')[0][0]['model'],['iy'])
        self.assertEqual(parse_sequence('i_I')[0][1]['model'],['ih'])

    def test_salem_breath_and_separated_cvc(self):
        u,_=parse_sequence('@-hh__{-hh','Salem','breath')
        self.assertEqual([p for x in u for p in x['model']],['ax','SP','ae','SP'])
        u,_=parse_sequence('p@p_b@b','Salem','cvc')
        self.assertEqual(sum(x['kind']=='pause' for x in u),1)

    def record(self,sequence):
        units,notes=parse_sequence(sequence,'DELTA');phones=['SP'];mapped=[]
        for u in units:
            ids=list(range(len(phones),len(phones)+len(u['model'])))
            phones.extend(u['model']);mapped.append(dict(u,indices=ids))
        phones.append('SP')
        return dict(wav='sample.wav',phones=phones,format='en_cvvc',language='en',cvvc_units=mapped,
                    intervals=[[i*.4,(i+1)*.4,p] for i,p in enumerate(phones)],duration=len(phones)*.4,label_warnings=notes)

    def test_cv_vc_vv_and_consonant_tail_rules(self):
        r=self.record('k_a_i_ts');rows=create_oto(r)
        cv=next(x for x in rows if x['alias']=='ka')
        self.assertAlmostEqual(cv['absolute'][4]-cv['absolute'][3],.07)
        vc=next(x for x in rows if x['alias']=='i ts')
        self.assertAlmostEqual(vc['absolute'][4]-vc['absolute'][3],.015)
        vv=next(x for x in rows if x['alias']=='a i')
        self.assertAlmostEqual(vv['absolute'][4]-vv['absolute'][3],.04)
        start=next(x for x in rows if x['alias']=='- ka')
        self.assertAlmostEqual(start['absolute'][1]-start['absolute'][0],.3)
        tail=next(x for x in rows if x['alias']=='ts -')
        self.assertAlmostEqual(tail['absolute'][2],r['intervals'][-1][0])

    def test_template_aliases_and_live_edit(self):
        from vcv_core import move_boundary,recalculate_file
        r=self.record('d+e');generated=create_oto(r)
        cv=next(x for x in generated if x['alias']=='DE')
        template=[dict(wav='sample.wav',alias='強d+e_soft',values=cv['values'])]
        rows=match_template(template,generated,{'sample.wav':r['duration']},{'sample.wav':r})
        self.assertFalse(rows[0].get('unmapped_template'))
        self.assertEqual(rows[0]['alias'],'強d+e_soft')
        report=dict(mode='en_cvvc',entries=rows)
        before=rows[0]['absolute'][2]
        move_boundary(r,2,.85);recalculate_file(report,r)
        self.assertNotEqual(before,report['entries'][0]['absolute'][2])
        self.assertEqual(report['entries'][0]['alias'],'強d+e_soft')


if __name__ == '__main__':unittest.main()
