import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest,QSignalSpy
import ui_settings as ui
from audio_view import AudioEditor,rms_energy,colorize_spectrum,SPECTRUM_PALETTES
from audio_playback import set_wav_segment_source
APP=QApplication.instance() or QApplication([])
class AudioReviewTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'audio.wav'
  self.samples=np.stack([np.linspace(-.8,.8,16000),np.full(16000,.25)],axis=1).astype(np.float32)
  sf.write(self.path,self.samples,16000,subtype='FLOAT')
  self.editor=AudioEditor();self.editor.resize(900,650)
  self.editor.load(self.path,[[0,.2,'pau'],[.2,.7,'a'],[.7,1.,'pau']],None)
  self.editor.show();APP.processEvents()
 def tearDown(self):
  self.editor.close();self.temp.cleanup();ui.spectrum_palette='classic'
 def test_right_click_uses_visible_stage_labels_without_editing(self):
  spy=QSignalSpy(self.editor.segmentRequested);edit=QSignalSpy(self.editor.editStarted)
  wave,spec=self.editor.plot_rects()
  QTest.mouseClick(self.editor,Qt.RightButton,pos=QPoint(round(self.editor.time_x(.4)),round(wave.center().y())))
  self.assertEqual(spy.at(0),[.2,.7]);self.assertEqual(edit.count(),0)
  self.editor.row={'absolute':[.1,.3,.5,.8,.9]};self.editor.set_stage(2)
  QTest.mouseClick(self.editor,Qt.RightButton,pos=QPoint(round(self.editor.time_x(.4)),round(spec.center().y())))
  self.assertEqual(spy.at(1),[.3,.5]);self.assertEqual(edit.count(),0)
 def test_clip_is_frame_exact_stereo_and_original_is_unchanged(self):
  class Player:
   def setSourceDevice(self,device,url):self.device=device
  original=self.path.read_bytes();player=Player()
  buffer=set_wav_segment_source(player,self.path,.2,.7)
  clip,rate=sf.read(io.BytesIO(bytes(buffer.data())),dtype='float32',always_2d=True)
  self.assertEqual(rate,16000);np.testing.assert_array_equal(clip,self.samples[3200:11200])
  self.assertEqual(self.path.read_bytes(),original)
 def test_energy_absolute_dbfs_and_silence_are_finite(self):
  times,db=rms_energy(np.full(16000,.5),16000)
  np.testing.assert_allclose(db,20*np.log10(.5),atol=1e-6)
  self.assertTrue(np.all(np.diff(times)>0))
  _,db=rms_energy(np.zeros(16000),16000);self.assertTrue(np.all(np.isfinite(db)))
 def test_palette_change_does_not_recompute_spectrum_or_energy(self):
  levels=self.editor.spectrum_levels;energy=self.editor.energy_db
  old=self.editor.image.copy()
  with patch('audio_view.spectrum_levels',side_effect=AssertionError('Unexpected STFT')):
   for palette in SPECTRUM_PALETTES:
    ui.spectrum_palette=palette;self.editor.update_spectrum_palette();APP.processEvents()
    self.assertIs(self.editor.spectrum_levels,levels);self.assertIs(self.editor.energy_db,energy)
  self.assertNotEqual(self.editor.image,old)
  # A second file must replace the image even when the palette stays the same.
  second=Path(self.temp.name)/'second.wav';sf.write(second,np.zeros(32000),16000)
  self.editor.load(second,[],None);self.assertEqual(self.editor.duration,2)
if __name__=='__main__':unittest.main()
