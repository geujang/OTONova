import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest,time,json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from external_files import snapshot,changes
from project_store import scan_folder
from vcv_gui import Window,ExternalReload
import audio_cache

APP=QApplication.instance() or QApplication([])

def finish(window):
    end=time.monotonic()+10
    while any(w and w.isRunning() for w in [window.asset_worker,window.reload_worker,window.file_scanner])+bool(window.wave._load_jobs):
        APP.processEvents();time.sleep(.01)
        if time.monotonic()>end:raise AssertionError('Background operation timeout')
    APP.processEvents()

class ExternalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.wav=self.root/'a.wav'
        sf.write(self.wav,np.zeros(16000,dtype='float32'),16000)
        self.oto=self.root/'oto.ini';self.oto.write_text('a.wav=a,0,100,-800,50,20\n')
        self.window=Window();self.window.open_folder(self.root);finish(self.window);self.window.file_timer.stop()
    def tearDown(self):finish(self.window);self.window.close();APP.processEvents();self.tmp.cleanup()

    def feed(self):
        self.window.external_snapshot(str(self.root),self.window._file_revision,snapshot(self.root))

    def test_help_and_feedback_dialog_available(self):
        w=self.window
        self.assertIn(w.credits_action,w.help_menu.actions())
        self.assertIn(w.generate,w.work_menu.actions())
        self.assertFalse(w.stop.isEnabled())
        self.assertTrue(w.feedback_action.isEnabled())
        self.assertTrue(w.update_action.isEnabled())
        self.assertTrue(w.github_action.isEnabled())

    def test_language_must_precede_format_selection(self):
        from PySide6.QtWidgets import QComboBox,QDialogButtonBox
        from PySide6.QtCore import QTimer
        errors=[]
        def inspect():
            dialog=APP.activeModalWidget()
            try:
                language=dialog.findChild(QComboBox,'voicebank_language')
                formats=dialog.findChild(QComboBox,'voicebank_format')
                ok=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok)
                self.assertFalse(formats.isEnabled());self.assertFalse(ok.isEnabled())
                from formats import PUBLIC_FORMATS
                for code in ['ko','ja','en']:
                    language.setCurrentIndex(language.findData(code))
                    self.assertTrue(formats.isEnabled());self.assertFalse(ok.isEnabled())
                    keys=[formats.itemData(i) for i in range(1,formats.count())]
                    self.assertEqual(keys,[k for k,v in PUBLIC_FORMATS.items() if v[1]==code])
                    formats.setCurrentIndex(1);self.assertTrue(ok.isEnabled())
                language.setCurrentIndex(0)
                self.assertFalse(formats.isEnabled());self.assertFalse(ok.isEnabled())
            except BaseException as error:errors.append(error)
            finally:dialog.reject()
        QTimer.singleShot(0,inspect)
        self.assertFalse(self.window.choose_mode())
        if errors:raise errors[0]

    def test_update_reply_compares_public_version_without_installing(self):
        from PySide6.QtNetwork import QNetworkReply
        class Reply:
            def error(self):return QNetworkReply.NoError
            def readAll(self):return b'{"tag_name":"v1.0.0"}'
            def deleteLater(self):pass
        with patch('vcv_gui.QMessageBox.information') as info,patch('vcv_gui.QDesktopServices.openUrl') as open_url:
            self.window.update_reply(Reply());info.assert_called_once();open_url.assert_not_called()

    def test_cancel_preserves_cached_audio_and_oto_and_does_not_repeat(self):
        w=self.window;old=audio_cache.get(self.wav,self.root/'.otonova-cache');sig=w.inventory['a.wav']['signature']
        old_rows=json.dumps(w.report['entries'])
        sf.write(self.wav,np.ones(16000,dtype='float32')*.4,16000)
        self.oto.write_text('a.wav=new,0,100,-700,40,20\n')
        with patch.object(w,'confirm_external_reload',return_value=False) as ask:
            self.feed();self.assertEqual([c.args[0] for c in ask.call_args_list],['wav','oto'])
            self.feed();self.assertEqual(ask.call_count,2)
        self.assertEqual(json.dumps(w.report['entries']),old_rows)
        self.assertEqual(w.inventory['a.wav']['signature'],sig)
        np.testing.assert_array_equal(audio_cache.get(self.wav,self.root/'.otonova-cache',sig)['samples'],old['samples'])

    def test_approve_reloads_audio_and_raw_oto_without_alignment(self):
        w=self.window
        # A stale cached report must not take priority over the changed oto.ini.
        cache=self.root/'auto-vcv';cache.mkdir(exist_ok=True)
        (cache/'report.json').write_text(json.dumps(w.report))
        sf.write(self.wav,np.ones(8000,dtype='float32')*.25,16000)
        self.oto.write_text('a.wav=changed,10,100,-300,60,30\n')
        with patch.object(w,'confirm_external_reload',return_value=True),patch('vcv_gui.run_folder',side_effect=AssertionError('no automatic alignment')):
            self.feed();finish(w)
        self.assertAlmostEqual(w.inventory['a.wav']['duration'],.5)
        self.assertEqual([r['alias'] for r in w.report['entries']],['changed'])
        self.assertEqual(w.report['entries'][0]['values'],[10.,100.,-300.,60.,30.])
        self.assertFalse(w.pending_external_wavs)

    def test_own_oto_save_is_not_reported_as_external_change(self):
        w=self.window;self.oto.write_text('a.wav=a,20,100,-500,70,20\n');w.acknowledge_oto_writes()
        with patch.object(w,'confirm_external_reload') as ask:self.feed();ask.assert_not_called()

    def test_cancel_is_reconsidered_when_project_is_reopened(self):
        w=self.window;self.oto.write_text('a.wav=new,10,100,-500,60,20\n')
        with patch.object(w,'confirm_external_reload',return_value=False):self.feed()
        w.save_project_snapshot();project=w.project_path
        w.restore_project(project);finish(w);w.file_timer.stop()
        with patch.object(w,'confirm_external_reload',return_value=False) as ask:
            self.feed();self.assertEqual(ask.call_args.args[0],'oto')

    def test_addition_and_deletion_classified(self):
        before=snapshot(self.root);self.wav.unlink()
        other=self.root/'sub';other.mkdir();(other/'oto.ini').write_text('')
        delta=changes(before,snapshot(self.root))
        self.assertEqual(delta['wav'],['a.wav']);self.assertEqual(delta['oto'],['sub/oto.ini'])

if __name__=='__main__':unittest.main()
