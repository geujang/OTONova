import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import tempfile
import json
import shutil
from copy import deepcopy
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QPoint,QTimer
from vcv_gui import Window
from vcv_core import ROOT,create_oto,deduplicate,persist_report,save_record,install_oto,move_boundary,Engine
from audio_view import make_spectrogram
BANK=next((p for p in ROOT.iterdir() if p.is_dir() and (p/'ああいあうえあ.wav').is_file()),ROOT/'Natural')

APP=QApplication.instance() or QApplication([])

class EditorTests(unittest.TestCase):
    def test_combined_mode_selection(self):
        w=self.window
        def choose():
            modal=APP.activeModalWidget()
            next(b for b in modal.buttons() if b.text()=='VCV & CVVC').click()
        QTimer.singleShot(0,choose)
        self.assertTrue(w.choose_mode())
        self.assertEqual(w.mode,'vcv_cvvc')
        self.assertEqual(w.generate.text(),'VCV & CVVC 원설 생성')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.wav='ああいあうえあ.wav'
        shutil.copyfile(BANK/self.wav,self.folder/self.wav)
        cached=BANK/'auto-vcv/labels'/Path(self.wav).with_suffix('.json')
        if cached.exists():
            self.record=json.loads(cached.read_text(encoding='utf-8'))
        else:
            # Analyze the temporary copy when the user has removed bank caches.
            _,self.record=Engine().analyze(self.folder/self.wav,self.folder/'auto-vcv/labels')
        from vcv_core import parse_name
        entries,removed=deduplicate(create_oto(self.wav,parse_name(Path(self.wav).stem),self.record['intervals'],self.record['duration']))
        report={'rules_version':18,'files':1,'successful_files':1,'entries':entries,'duplicates_removed':removed,'failures':[]}
        save_record(self.folder,self.record)
        persist_report(self.folder,report)
        install_oto(self.folder)
        self.window=Window()
        self.window.folder.setText(str(self.folder))
        self.window.load_report()
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.close()
        APP.processEvents()
        self.temp.cleanup()

    def test_unmapped_warning_row_updates_live_and_saves(self):
        from vcv_core import apply_oto_template
        w=self.window
        original=deepcopy(w.report['entries'][0])
        original['alias']='custom-error-alias'
        entries=apply_oto_template([original],[],{self.wav:self.record['duration']},
                                   {self.wav:self.record})
        report=dict(w.report,entries=entries)
        persist_report(self.folder,report)
        install_oto(self.folder)
        w.load_report()
        before=deepcopy(w.report['entries'][0]['values'])
        w.begin_edit()
        w.edit_boundary(2,w.current_record['intervals'][2][0]+.1)
        self.assertNotEqual(w.report['entries'][0]['values'],before)
        self.assertEqual(w.table.item(0,1).text(),'custom-error-alias')
        w.finish_edit()
        saved=json.loads((self.folder/'auto-vcv/report.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['entries'],w.report['entries'])
        w.undo_edit()
        for actual,want in zip(w.report['entries'][0]['values'],before):
            self.assertAlmostEqual(actual,want)

    def test_real_mouse_drag_live_recompute_persist_and_undo(self):
        w=self.window
        wave=w.wave
        before=deepcopy(w.current_record['intervals'])
        model_before=deepcopy(w.current_record.get('model_intervals',before))
        original=(self.folder/'oto.ini').read_bytes()
        prior_table=w.table.item(0,3).text()
        y=int(wave.plot_rects()[0].center().y())
        x=int(wave.time_x(before[2][0]))
        target=int(wave.time_x(before[2][0]+.1))
        QTest.mousePress(wave,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
        QTest.mouseMove(wave,QPoint(target,y))
        APP.processEvents()
        self.assertNotEqual(w.table.item(0,3).text(),prior_table)
        self.assertGreater(w.current_record['intervals'][2][0]-before[2][0],.08)
        self.assertEqual(w.current_record['intervals'][1][1],w.current_record['intervals'][2][0])
        self.assertEqual((self.folder/'oto.ini').read_bytes(),original)
        QTest.mouseRelease(wave,Qt.LeftButton,Qt.NoModifier,QPoint(target,y))
        APP.processEvents()
        self.assertNotEqual((self.folder/'oto.ini').read_bytes(),original)
        saved=json.loads((self.folder/'auto-vcv/labels'/Path(self.wav).with_suffix('.json')).read_text(encoding='utf-8'))
        self.assertEqual(saved['intervals'],w.current_record['intervals'])
        self.assertEqual(saved['model_intervals'],model_before)
        lab=(self.folder/'auto-vcv/labels'/Path(self.wav).with_suffix('.lab')).read_text().splitlines()
        self.assertEqual(lab[1].split()[1],lab[2].split()[0])
        self.assertEqual(len(list(self.folder.glob('oto.backup.*.ini'))),1)
        # A fresh GUI must show the saved manual boundary.
        persisted=deepcopy(w.current_record['intervals'])
        other=Window()
        other.folder.setText(str(self.folder))
        other.load_report()
        self.assertEqual(other.current_record['intervals'],persisted)
        other.close()
        w.undo_edit()
        self.assertEqual(w.current_record['intervals'],before)
        self.assertEqual((self.folder/'oto.ini').read_bytes(),original)

    def test_zoom_preserved_between_aliases_of_same_wav(self):
        self.window.wave.zoom(3)
        view=(self.window.wave.start,self.window.wave.length)
        image_key=self.window.wave.image.cacheKey()
        self.window.table.selectRow(1)
        APP.processEvents()
        self.assertEqual((self.window.wave.start,self.window.wave.length),view)
        self.assertEqual(self.window.wave.image.cacheKey(),image_key)
        self.assertLessEqual(self.window.wave.high_hz,15000)

    def test_manual_labels_survive_batch_regeneration(self):
        record=deepcopy(self.record)
        move_boundary(record,2,record['intervals'][2][0]+.1)
        save_record(self.folder,record)
        from unittest.mock import patch
        with patch('pyshiro.forced_align_2pass',side_effect=AssertionError('manual cache must be retained')):
            _,cached=Engine().analyze(self.folder/self.wav,self.folder/'auto-vcv/labels')
        self.assertEqual(cached['intervals'],record['intervals'])

    def test_spectrogram_frequency_limit_and_known_tone(self):
        sr=48000
        t=np.arange(sr)/sr
        audio=np.sin(2*np.pi*6000*t)+np.sin(2*np.pi*22000*t)
        rgb,high,times=make_spectrogram(audio,sr)
        self.assertLessEqual(high,15000)
        self.assertGreaterEqual(rgb.shape[0],1200)
        self.assertGreaterEqual(rgb.shape[1],375)
        energy=rgb[:,5:-5].astype(float).mean(axis=(1,2))
        strongest=high*(1-np.argmax(energy)/(len(energy)-1))
        self.assertAlmostEqual(strongest,6000,delta=30)

    def test_drag_reuses_background_and_spectrogram(self):
        w=self.window
        wave=w.wave
        wave.repaint()
        APP.processEvents()
        initial=wave.background_builds
        image_key=wave.image.cacheKey()
        from unittest.mock import patch
        seconds=w.current_record['intervals'][2][0]
        with patch('audio_view.make_spectrogram',side_effect=AssertionError('STFT must not run while dragging')):
            w.begin_edit()
            for i in range(20):
                w.edit_boundary(2,seconds+.002*i)
                wave.repaint()
                APP.processEvents()
        self.assertEqual(wave.background_builds,initial)
        self.assertEqual(wave.image.cacheKey(),image_key)
        wave.zoom(2)
        wave.repaint()
        APP.processEvents()
        self.assertEqual(wave.background_builds,initial+1)

    def test_folder_mode_prompt_and_cvvc_drag_save_reopen(self):
        from unittest.mock import patch
        from vcv_core import parse_name
        entries,removed=deduplicate(create_oto(self.wav,parse_name(Path(self.wav).stem),
            self.record['intervals'],self.record['duration'],'cvvc'))
        report={'mode':'cvvc','rules_version':18,'files':1,'successful_files':1,'entries':entries,
                'duplicates_removed':removed,'failures':[]}
        persist_report(self.folder,report)
        install_oto(self.folder,'cvvc')
        vcv_before=(self.folder/'auto-vcv/oto.preview.ini').read_bytes()
        w=self.window
        def select_cvvc():
            modal=APP.activeModalWidget()
            self.assertIsInstance(modal,QMessageBox)
            next(button for button in modal.buttons() if button.text()=='CVVC').click()
        with patch.object(QFileDialog,'getExistingDirectory',return_value=str(self.folder)):
            QTimer.singleShot(0,select_cvvc)
            w.browse()
        self.assertEqual(w.mode,'cvvc')
        self.assertEqual(w.report['mode'],'cvvc')
        self.assertEqual(w.generate.text(),'CVVC 원설 생성')
        before=deepcopy(w.current_record['intervals'])
        wave=w.wave
        y=int(wave.plot_rects()[0].center().y())
        x=int(wave.time_x(before[2][0]))
        target=int(wave.time_x(before[2][0]+.1))
        original=(self.folder/'oto.ini').read_bytes()
        QTest.mousePress(wave,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
        QTest.mouseMove(wave,QPoint(target,y))
        APP.processEvents()
        self.assertGreater(w.current_record['intervals'][2][0],before[2][0]+.08)
        self.assertEqual((self.folder/'oto.ini').read_bytes(),original)
        QTest.mouseRelease(wave,Qt.LeftButton,Qt.NoModifier,QPoint(target,y))
        APP.processEvents()
        self.assertEqual((self.folder/'oto.ini').read_bytes(),(self.folder/'auto-cvvc/oto.preview.ini').read_bytes())
        self.assertEqual((self.folder/'auto-vcv/oto.preview.ini').read_bytes(),vcv_before)
        other=Window()
        other.folder.setText(str(self.folder))
        other.set_mode('cvvc')
        self.assertEqual(other.current_record['intervals'],w.current_record['intervals'])
        self.assertEqual(other.report['entries'],w.report['entries'])
        other.close()
        w.undo_edit()
        self.assertEqual(w.current_record['intervals'],before)
        # Switching back uses the same manual boundary cache with VCV formulas.
        w.set_mode('vcv')
        self.assertEqual(w.mode,'vcv')
        self.assertEqual(w.current_record['intervals'],before)

    def test_old_cvvc_report_upgrades_with_manual_boundaries_preserved(self):
        from unittest.mock import patch
        record=deepcopy(self.record)
        move_boundary(record,2,record['intervals'][2][0]+.1)
        save_record(self.folder,record)
        old={'mode':'cvvc','files':1,'successful_files':1,'entries':[],
             'duplicates_removed':0,'failures':[]}
        persist_report(self.folder,old)
        with patch('pyshiro.forced_align_2pass',side_effect=AssertionError('manual cache must be retained')):
            self.window.set_mode('cvvc')
        self.assertEqual(self.window.report['rules_version'],18)
        self.assertIn('a い',[r['alias'] for r in self.window.report['entries']])
        self.assertEqual(self.window.current_record['intervals'],record['intervals'])

    def test_existing_alias_template_keeps_order_duplicates_and_live_edits(self):
        from vcv_core import run_folder
        # Keep original katakana, an unsupported custom alias, and a duplicate.
        first=self.window.report['entries'][0]
        identities=['-ア','사용자별칭','-ア']
        lines=[self.wav+'='+alias+','+','.join(str(v) for v in first['values']) for alias in identities]
        (self.folder/'oto.ini').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
        w=self.window
        w.set_mode('cvvc')
        report=run_folder(self.folder,mode='cvvc')
        self.assertTrue(report['uses_existing_oto'])
        self.assertEqual(report['oto_encoding'],'utf-8-sig')
        self.assertEqual([r['alias'] for r in report['entries']],identities)
        self.assertEqual(report['entries'][1]['values'],first['values'])
        self.assertTrue(report['entries'][1]['unmapped_template'])
        self.assertAlmostEqual(report['entries'][0]['absolute'][4]-report['entries'][0]['absolute'][3],.07)
        w.done(report)
        before=report['entries'][0]['values'][:]
        w.begin_edit()
        w.edit_boundary(2,w.current_record['intervals'][2][0]+.1)
        w.finish_edit()
        self.assertNotEqual(w.report['entries'][0]['values'],before)
        self.assertEqual([r['alias'] for r in w.report['entries']],identities)
        saved=(self.folder/'oto.ini').read_text(encoding='utf-8-sig').splitlines()
        self.assertEqual([line.split('=',1)[1].split(',')[0] for line in saved],identities)
        self.assertTrue((self.folder/'oto.ini').read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_original_consonant_tail_alias_live_rule(self):
        from vcv_core import run_folder
        wav='かかきかくけか.wav'
        shutil.copyfile(BANK/wav,self.folder/wav)
        (self.folder/'oto.ini').write_text(wav+'=k -,1000,200,-1000,50,20\n',encoding='cp932')
        w=self.window
        w.set_mode('cvvc')
        report=run_folder(self.folder,mode='cvvc')
        w.done(report)
        row=report['entries'][0]
        self.assertEqual(row['alias'],'k -')
        self.assertTrue(row['consonant_only'])
        self.assertEqual(row['absolute'][2],w.current_record['intervals'][-1][0])
        self.assertAlmostEqual(row['absolute'][4]-row['absolute'][3],.02)
        index=row['consonant_interval_index']+1
        before=row['values'][:]
        w.begin_edit()
        w.edit_boundary(index,w.current_record['intervals'][index][0]+.02)
        w.finish_edit()
        self.assertNotEqual(w.report['entries'][0]['values'],before)
        saved=(self.folder/'oto.ini').read_text(encoding='cp932')
        self.assertEqual(saved.split('=',1)[1].split(',')[0],'k -')
        self.assertAlmostEqual(w.report['entries'][0]['absolute'][4]-w.report['entries'][0]['absolute'][3],.02)

if __name__=='__main__':unittest.main()
