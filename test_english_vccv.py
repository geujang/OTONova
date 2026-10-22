import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile,unittest
from english_vccv import tokens,parse_recording,VccvResolver,create_oto,detect,read_templates,match_template,catalog

class VccvTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def record(self,section,stem):
        p=self.root/section/(stem+'.wav');p.parent.mkdir(exist_ok=True);p.touch()
        r=VccvResolver(self.root).metadata(p)
        r.update(language='en',duration=len(r['phones'])*.2,
                 intervals=[[i*.2,(i+1)*.2,s] for i,s in enumerate(r['phones'])])
        return r
    def row(self,rows,alias):return next(r for r in rows if r['alias']==alias)
    def test_vccv_not_delta_alphabet(self):
        self.assertEqual([u['model'] for u in tokens('aAeEIoO@x0')],
                         [['aa'],['ey'],['eh'],['iy'],['ay'],['uw'],['ow'],['ae'],['ax'],['ao']])
        with self.assertRaises(ValueError):tokens('d+e')
        self.assertEqual([p for u in tokens('AngAnk') for p in u['model']],['ae','ng','ae','ng','k'])
    def test_organizer_tags_not_recorded(self):
        r=self.record('CC-','b__kebd_kebd')
        self.assertEqual(r['phones'],['SP','k','eh','b','d','SP','k','eh','b','d','SP'])
        self.assertEqual(len(parse_recording('_AA---','VV')),1)
    def test_all_ten_sections(self):
        cases={'CC-':'b__kebd_kebd','CCV':'-ble_ble','CV':'-dd@_dd@','CVC_CV':'-b&m_bx_b&m',
               'CV_CVC':'-ba_bab_kab','V':'-a__ka','VC':'l_k@l_k@l','VCC':'r__karb_karb','VV':'_Aa--','_CV':'-kla'}
        for section,stem in cases.items():
            with self.subTest(section=section):
                rows=create_oto(self.record(section,stem));self.assertTrue(rows)
                for r in rows:self.assertAlmostEqual(r['values'][4],r['values'][3]/2)
        self.assertEqual(len(catalog()['sections']),10)
    def test_space_vc_and_tail_are_different(self):
        r=self.record('CV_CVC','-ba_bab_kab');rows=create_oto(r)
        bridge=self.row(rows,'a b');vc=self.row(rows,'ab');tail=self.row(rows,'ab-')
        units=r['vccv_units'];spans=r['intervals'];groups=r['vccv_groups']
        def end(i):return spans[units[i]['indices'][-1]][1]
        self.assertAlmostEqual(bridge['absolute'][2],end(groups[0][-1]))
        self.assertAlmostEqual(vc['absolute'][2],end(groups[1][-1]))
        self.assertAlmostEqual(tail['absolute'][2],end(groups[2][-2]))
        self.assertNotEqual(vc['absolute'][2],tail['absolute'][2])
    def test_nested_templates_and_live_edit(self):
        from vcv_core import move_boundary,recalculate_file
        r=self.record('CV_CVC','-ba_bab_kab');generated=create_oto(r)
        p=self.root/'CV_CVC/oto.ini';p.write_text('-ba_bab_kab.wav=強ab-_soft,0,100,-500,100,50\n',encoding='utf-8')
        original=p.read_bytes();template,_=read_templates(self.root)
        self.assertEqual(template[0]['wav'],'CV_CVC/-ba_bab_kab.wav')
        rows=match_template(template,generated,{r['wav']:r['duration']},{r['wav']:r})
        self.assertFalse(rows[0].get('unmapped_template'));self.assertEqual(rows[0]['alias'],'強ab-_soft')
        report=dict(mode='en_vccv',entries=rows);before=rows[0]['absolute'][2]
        # Move the last syllable's V/C boundary.
        index=r['vccv_units'][r['vccv_groups'][2][-1]]['indices'][0]
        move_boundary(r,index,r['intervals'][index][0]+.01);recalculate_file(report,r)
        self.assertNotEqual(report['entries'][0]['absolute'][2],before)
        self.assertAlmostEqual(report['entries'][0]['values'][4],report['entries'][0]['values'][3]/2)
        self.assertEqual(p.read_bytes(),original)
        from vcv_core import persist_report,install_oto
        persist_report(self.root,report);install_oto(self.root,'en_vccv')
        self.assertFalse((self.root/'oto.ini').exists())
        backups=list(p.parent.glob('oto.backup.*.ini'))
        self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),original)
        self.assertIn('強ab-_soft',p.read_text(encoding='utf-8'))
    def test_unknown_and_missing_original_rows(self):
        r=self.record('CCV','-vre_vre')
        self.assertTrue(r['vccv_inferred_aliases']);self.assertTrue(create_oto(r)[0]['warnings'])
        r=self.record('V','-0r_k0r');self.assertEqual(len(create_oto(r)),4)
        p=self.root/'garbage.wav';p.touch()
        with self.assertRaises(ValueError):VccvResolver(self.root).metadata(p)
        self.assertEqual(len(detect(self.root)['input_failures']),1)
    def test_cc_vcc_landmarks(self):
        r=self.record('VCC','r__karb_karb');rows=create_oto(r);units=r['vccv_units'];spans=r['intervals']
        first,last=[ [units[i] for i in group] for group in r['vccv_groups'] ]
        self.assertAlmostEqual(self.row(rows,'arb')['absolute'][2],spans[first[-1]['indices'][-1]][1])
        self.assertAlmostEqual(self.row(rows,'arb-')['absolute'][2],spans[last[-2]['indices'][-1]][1])
    def test_gui_choice_and_stage_controls(self):
        from PySide6.QtWidgets import QApplication
        from vcv_gui import Window
        app=QApplication.instance() or QApplication([])
        record=self.record('CV_CVC','-ba_bab_kab')
        w=Window();w.folder.setText(str(self.root));w.set_mode('en_vccv')
        self.assertIn('영어 VCCV',w.mode_button.text());self.assertTrue(all(b.isEnabled() for b in w.stage_buttons))
        self.assertEqual(w.files.count(),1)
        w.report=dict(mode='en_vccv',entries=create_oto(record),files=1,successful_files=1,failures=[])
        w.current_record=record;w.set_stage(2);w.save_edits()
        target=self.root/'CV_CVC/oto.ini';before=target.read_bytes()
        w.report['entries'][0]['values'][0]+=.01;w.save_edits()
        self.assertNotEqual(before,target.read_bytes());self.assertFalse((self.root/'oto.ini').exists())
        w.close();app.processEvents()

if __name__=='__main__':unittest.main()
