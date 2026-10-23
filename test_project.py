import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,tempfile,unittest,shutil,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from vcv_core import create_oto,parse_name,RULES_VERSION,save_record
from project_store import scan_folder,save_project,open_project,signature
from vcv_gui import Window
import audio_cache

APP=QApplication.instance() or QApplication([])

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.path=self.root/'か.wav';sf.write(self.path,np.zeros(16000*3,dtype='float32'),16000)
        self.record={'wav':'か.wav','language':'ja','phones':['pau','k','a','pau'],
                     'intervals':[[0,.3,'pau'],[.3,.5,'k'],[.5,2.5,'a'],[2.5,3,'pau']], 'duration':3}
        rows=create_oto('か.wav',parse_name('か'),self.record['intervals'],3)
        self.report=dict(mode='vcv',rules_version=RULES_VERSION,entries=rows,files=1,successful_files=1,failures=[],duplicates_removed=0)
        self.project=self.root/'OTONova.otonova';self.inventory={'か.wav':{'signature':signature(self.path)}}
        save_project(self.project,self.root,self.report,{'か.wav':self.record},self.inventory,2,'か.wav')
    def tearDown(self):self.tmp.cleanup()

    def test_self_contained_and_portable_project(self):
        copy=self.root/'moved';copy.mkdir();shutil.copy2(self.path,copy/self.path.name);shutil.copy2(self.project,copy/self.project.name)
        loaded=open_project(copy/self.project.name)
        self.assertEqual(loaded['changed_files'],[])
        self.assertEqual(loaded['records']['か.wav']['intervals'],self.record['intervals'])
        self.assertEqual(loaded['report']['entries'],self.report['entries'])

    def test_changed_audio_does_not_reuse_boundaries(self):
        sf.write(self.path,np.ones(16000,dtype='float32')*.1,16000)
        loaded=open_project(self.project)
        self.assertEqual(loaded['changed_files'],['か.wav']);self.assertFalse(loaded['records'])
        self.assertTrue(loaded['report']['entries'][0]['warnings'])

    def test_inventory_loads_uppercase_wav_and_nested_oto(self):
        nested=self.root/'pitch';nested.mkdir();sf.write(nested/'a.WAV',np.zeros(8000),8000)
        (nested/'oto.ini').write_text('a.wav=a,100,200,-500,150,50\n',encoding='utf-8')
        inventory,report,_=scan_folder(self.root)
        self.assertEqual(len(inventory),2)
        row=report['entries'][0];self.assertEqual(row['wav'],'pitch/a.WAV')
        np.testing.assert_allclose(row['absolute'],[.1,.15,.25,.3,.6])

    def test_disk_cache_reuses_spectrum_and_invalidates_changed_file(self):
        cache=self.root/'cache';first=audio_cache.get(self.path,cache)
        with audio_cache._guard:audio_cache._memory.clear();audio_cache._bytes=0
        with patch('audio_view.spectrum_levels',side_effect=AssertionError('unnecessary recompute')):
            second=audio_cache.get(self.path,cache)
        np.testing.assert_array_equal(first['levels'],second['levels'])
        previous=audio_cache.key(self.path);sf.write(self.path,np.zeros(4000),16000)
        self.assertNotEqual(previous,audio_cache.key(self.path))
        self.assertEqual(len(audio_cache.get(self.path,cache)['samples']),4000)

    def test_gui_restore_without_inference_or_external_label_cache(self):
        window=Window()
        try:
            with patch('vcv_gui.run_folder',side_effect=AssertionError('must not align on open')):
                window.restore_project(self.project)
                until=time.monotonic()+10
                while (window.asset_worker.isRunning() or window.wave._load_jobs) and time.monotonic()<until:APP.processEvents();time.sleep(.01)
                APP.processEvents()
                self.assertEqual(window.current_record['intervals'],self.record['intervals'])
                self.assertEqual(window.stage,2)
                self.assertIsNotNone(window.wave.samples)
                window.set_stage(1);window.begin_edit();window.edit_boundary(2,.65);window.finish_edit()
                saved=open_project(self.project)
                self.assertAlmostEqual(saved['records']['か.wav']['intervals'][2][0],.65)
        finally:window.close();APP.processEvents()

    def test_legacy_label_only_folder_opens_without_inference(self):
        self.project.unlink()
        cache=self.root/'auto-ko_cvvc/labels';cache.mkdir(parents=True)
        (cache/'か.json').write_text(json.dumps(self.record),encoding='utf-8')
        window=Window()
        try:
            with patch('vcv_gui.run_folder',side_effect=AssertionError('must not align')):
                window.open_folder(self.root)
                until=time.monotonic()+10
                while (window.asset_worker.isRunning() or window.wave._load_jobs) and time.monotonic()<until:APP.processEvents();time.sleep(.01)
                APP.processEvents()
                self.assertEqual(window.current_record['intervals'],self.record['intervals'])
                self.assertEqual(window.stage,1)
                self.assertEqual(window.report['entries'],[])
                window.begin_edit();window.edit_boundary(2,.65);window.finish_edit()
                self.assertAlmostEqual(open_project(self.project)['records']['か.wav']['intervals'][2][0],.65)
        finally:window.close();APP.processEvents()

    def test_legacy_cache_hash_mismatch_is_ignored(self):
        cache=self.root/'auto-vcv/labels';cache.mkdir(parents=True)
        record=dict(self.record,sha256='0'*64)
        (cache/'か.json').write_text(json.dumps(record),encoding='utf-8')
        self.assertFalse(scan_folder(self.root)[2])

    def test_existing_oto_opens_in_oto_stage_and_overrides_old_report(self):
        self.project.unlink()
        values=[100,200,-900,150,50]
        (self.root/'oto.ini').write_text('か.wav=original_alias,100,200,-900,150,50\n',encoding='utf-8')
        old=self.root/'auto-vcv';old.mkdir()
        (old/'report.json').write_text(json.dumps(self.report),encoding='utf-8')
        window=Window()
        try:
            with patch('vcv_gui.run_folder',side_effect=AssertionError('must not align')):
                window.open_folder(self.root)
                until=time.monotonic()+10
                while (window.asset_worker.isRunning() or window.wave._load_jobs) and time.monotonic()<until:APP.processEvents();time.sleep(.01)
                APP.processEvents()
                self.assertEqual(window.stage,2)
                self.assertFalse(window.table.isHidden())
                self.assertEqual(window.wave.row['alias'],'original_alias')
                self.assertEqual(window.wave.row['values'],values)
                self.assertIsNotNone(window.wave.samples)
                np.testing.assert_allclose(window.wave.row['absolute'],[.1,.15,.25,.3,1.0])
                self.assertEqual(open_project(self.project)['stage'],2)
        finally:window.close();APP.processEvents()

    def test_single_wav_alignment_keeps_other_rows(self):
        from vcv_core import run_folder
        from copy import deepcopy
        from unittest.mock import MagicMock
        other=deepcopy(self.report['entries'][0]);other['wav']='other.wav';other['alias']='keep'
        previous=deepcopy(self.report);previous['entries'].append(other);previous['files']=2
        engine=MagicMock();engine.analyze.return_value=(self.report['entries'],deepcopy(self.record))
        with patch('vcv_core.Engine',return_value=engine):
            result=run_folder(self.root,only_files=['か.wav'],base_report=previous)
        self.assertEqual(engine.analyze.call_count,1)
        self.assertEqual(engine.analyze.call_args.args[0],self.path)
        self.assertEqual([r for r in result['entries'] if r['wav']=='other.wav'],[other])
        self.assertEqual(result['processed_files'],['か.wav'])
        self.assertEqual(result['files'],2)

    def test_single_wav_failure_preserves_previous_rows(self):
        from vcv_core import run_folder
        from unittest.mock import MagicMock
        engine=MagicMock();engine.analyze.side_effect=ValueError('test failure')
        with patch('vcv_core.Engine',return_value=engine):
            result=run_folder(self.root,only_files=['か.wav'],base_report=self.report)
        self.assertEqual(result['entries'],self.report['entries'])
        self.assertEqual(len(result['failures']),1)

    def test_start_always_asks_for_format_and_cancel_does_not_run(self):
        window=Window();window.mode_chosen=True
        try:
            with patch.object(window,'choose_mode',return_value=False) as chooser,patch('vcv_gui.Worker') as worker:
                window.start();chooser.assert_called_once();worker.assert_not_called()
        finally:window.close();APP.processEvents()

if __name__=='__main__':unittest.main()
