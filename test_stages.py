import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from vcv_core import (RULES_VERSION,parse_name,create_oto,save_record,persist_report,
                      install_oto,edit_oto_marker)
from vcv_gui import Window

APP=QApplication.instance() or QApplication([])

class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.wav='か.wav'
        sf.write(self.folder/self.wav,np.zeros(16000*5,dtype=np.float32),16000)
        self.record={'wav':self.wav,'phones':['pau','k','a','pau'],
                     'intervals':[[0,1,'pau'],[1,1.5,'k'],[1.5,3,'a'],[3,5,'pau']],
                     'duration':5,'label_warnings':['音素検討']}
        rows=create_oto(self.wav,parse_name('か'),self.record['intervals'],5)
        rows[0]['warnings']=['原設検討']
        self.report={'rules_version':RULES_VERSION,'mode':'vcv','files':1,'successful_files':1,
                     'entries':rows,'failures':[]}
        save_record(self.folder,self.record)
        persist_report(self.folder,self.report)
        install_oto(self.folder)
        self.window=Window()
        self.window.folder.setText(str(self.folder))
        self.window.done(deepcopy(self.report))
        self.window.show();APP.processEvents()

    def tearDown(self):
        self.window.close();APP.processEvents();self.temp.cleanup()

    def test_supported_and_proxy_palatalized_phones(self):
        for phone in ['ty','dy','fy','py','vy']:
            token=parse_name(phone)[0]
            self.assertEqual(token['phones'],[phone[0]])
            self.assertEqual(token['alias_phones'],[phone])
        for phone in ['ky','by']:
            self.assertEqual(parse_name(phone)[0]['phones'],[phone])
        self.assertEqual(parse_name('てゃ')[0]['phones'],['t','a'])

    def test_boundary_stage_does_not_write_oto_and_splits_warnings(self):
        w=self.window
        self.assertEqual(w.stage,1)
        self.assertFalse(w.table.isVisible())
        self.assertIn('音素検討',w.files.item(0).text())
        self.assertNotIn('原設検討',w.files.item(0).text())
        w.set_stage(2)
        self.assertIn('原設検討',w.files.item(0).text())
        self.assertNotIn('音素検討',w.files.item(0).text())
        w.set_stage(1)
        original=(self.folder/'oto.ini').read_bytes()
        w.begin_edit();w.edit_boundary(2,1.7);w.finish_edit()
        self.assertEqual((self.folder/'oto.ini').read_bytes(),original)
        saved=json.loads((self.folder/'auto-vcv/labels/か.json').read_text(encoding='utf-8'))
        self.assertAlmostEqual(saved['intervals'][2][0],1.7)
        w.set_stage(2)
        self.assertTrue(w.table.isVisible())
        self.assertNotIn('音素検討',w.files.item(0).text())

    def test_keyboard_left_to_right_edit_persists_and_undoes(self):
        w=self.window;w.set_stage(2);APP.processEvents()
        row=w.report['entries'][0];before=deepcopy(row)
        marker=w.wave.ordered_markers()[1]
        spans=deepcopy(w.current_record['intervals'])
        w.wave.pointer_x=w.wave.time_x(1.2)
        w.wave.setFocus()
        QTest.keyPress(w.wave,Qt.Key_2);QTest.keyRelease(w.wave,Qt.Key_2)
        self.assertAlmostEqual(w.report['entries'][0]['absolute'][marker],1.2)
        self.assertEqual(w.current_record['intervals'],spans)
        self.assertTrue(w.report['entries'][0]['manual_oto'])
        saved=json.loads((self.folder/'auto-vcv/report.json').read_text(encoding='utf-8'))
        self.assertAlmostEqual(saved['entries'][0]['absolute'][marker],1.2)
        w.load_report();w.set_stage(2)
        self.assertAlmostEqual(w.report['entries'][0]['absolute'][marker],1.2)
        # A second edit can be undone independently after reload.
        snapshot=deepcopy(w.report['entries'][0]['absolute'])
        w.begin_edit();w.edit_oto(2,2.2);w.finish_edit();w.undo_edit()
        self.assertEqual(w.report['entries'][0]['absolute'],snapshot)

    def test_second_stage_drag_moves_oto_only(self):
        w=self.window;w.set_stage(2);APP.processEvents()
        wave=w.wave;spans=deepcopy(w.current_record['intervals'])
        row=w.report['entries'][0];before=list(row['absolute'])
        marker=wave.ordered_markers()[0]
        y=int(wave.plot_rects()[0].center().y())
        x=int(wave.time_x(before[marker]));target=int(wave.time_x(before[marker]+.15))
        QTest.mousePress(wave,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
        QTest.mouseMove(wave,QPoint(target,y))
        QTest.mouseRelease(wave,Qt.LeftButton,Qt.NoModifier,QPoint(target,y))
        self.assertGreater(w.report['entries'][0]['absolute'][marker],before[marker]+.1)
        self.assertEqual(w.current_record['intervals'],spans)

    def test_preutterance_moves_all_markers_with_fixed_spacing(self):
        row={'alias':'a k','absolute':[.2,.3,.5,.7,.9],'values':[]}
        original=list(row['absolute'])
        self.assertAlmostEqual(edit_oto_marker(row,2,.7,2),.7)
        for old,new in zip(original,row['absolute']):self.assertAlmostEqual(new-old,.2)
        self.assertEqual(row['alias'],'a k')
        self.assertTrue(row['manual_oto'])
        self.assertAlmostEqual(row['values'][1],500)
        self.assertAlmostEqual(row['values'][3],300)

    def test_preutterance_translation_stops_at_wav_edges(self):
        row={'alias':'a','absolute':[.2,.3,.5,.7,.9],'values':[]}
        edit_oto_marker(row,2,5,1)
        for actual,wanted in zip(row['absolute'],[.3,.4,.6,.8,1.]):self.assertAlmostEqual(actual,wanted)
        edit_oto_marker(row,2,-5,1)
        for actual,wanted in zip(row['absolute'],[0.,.1,.3,.5,.7]):self.assertAlmostEqual(actual,wanted)

    def test_preutterance_group_edit_is_saved_and_undoable(self):
        w=self.window;w.set_stage(2)
        old=list(w.report['entries'][0]['absolute'])
        intervals=deepcopy(w.current_record['intervals'])
        w.begin_edit();w.edit_oto(2,old[2]+.05);w.finish_edit()
        after=list(w.report['entries'][0]['absolute'])
        for a,b in zip(old,after):self.assertAlmostEqual(b-a,.05)
        saved=json.loads((self.folder/'auto-vcv/report.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['entries'][0]['absolute'],after)
        self.assertEqual(w.current_record['intervals'],intervals)
        w.undo_edit();self.assertEqual(w.report['entries'][0]['absolute'],old)

    def test_manual_values_preserve_absolute_positions_and_alias(self):
        row=deepcopy(self.report['entries'][0]);before=deepcopy(row)
        edit_oto_marker(row,0,.2,5)
        self.assertEqual(row['absolute'][1:],before['absolute'][1:])
        self.assertEqual(row['alias'],before['alias'])
        self.assertAlmostEqual(row['values'][2],-(row['absolute'][4]-.2)*1000)

if __name__=='__main__':unittest.main()
