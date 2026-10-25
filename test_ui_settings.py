import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
import ui_settings as ui
from vcv_gui import Window
APP=QApplication.instance() or QApplication([])
APP.setFont(QFont('Malgun Gothic',10))
class PreferencesTests(unittest.TestCase):
 def test_display_language_default_and_user_override(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   for detected in ['ko','ja','en','zh']:
    settings=QSettings(str(Path(folder)/(detected+'.ini')),QSettings.IniFormat)
    with patch('ui_settings.system_language',return_value=detected):
     window=Window(settings)
     try:self.assertEqual(ui.language,detected)
     finally:window.close()
     settings.setValue('language','ja')
     with patch('ui_settings.system_language',return_value='ko'):
      window=Window(settings)
      try:self.assertEqual(ui.language,'ja')
      finally:window.close()
   settings.setValue('language','fr')
   window=Window(settings)
   try:self.assertEqual(ui.language,'en')
   finally:window.close();ui.language='ko'
 def test_regional_tags_and_unsupported_language(self):
  for tag,wanted in [('ko-KR','ko'),('ja-JP','ja'),('en-GB','en'),('zh-TW','zh'),('zh-Hans-CN','zh'),('fr-FR','en'),('de_DE','en'),('','en')]:
   self.assertEqual(ui.language_from_tag(tag),wanted)
 def test_frequency_setting_default_and_persistence(self):
  previous=ui.spectrum_max_hz
  with tempfile.TemporaryDirectory() as folder:
   settings=QSettings(str(Path(folder)/'frequency.ini'),QSettings.IniFormat)
   window=Window(settings)
   try:
    self.assertEqual(ui.spectrum_max_hz,10000)
    window.set_preferences('en','dark','fire',22000)
    self.assertEqual(settings.value('spectrum_max_hz'),22000)
   finally:window.close()
   restored=Window(settings)
   try:self.assertEqual(ui.spectrum_max_hz,22000)
   finally:restored.close();ui.spectrum_max_hz=previous
 def test_languages_themes_and_persistence(self):
  with tempfile.TemporaryDirectory() as folder:
   settings=QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat)
   window=Window(settings);window.show();APP.processEvents()
   try:
    for language in ui.LANGUAGES:
     for theme in ('dark','light'):
      window.set_preferences(language,theme);APP.processEvents()
      self.assertEqual(window.settings_button.text(),ui.translate('설정'))
      self.assertEqual(window.table.horizontalHeaderItem(1).text(),ui.translate('에일리어스'))
      self.assertEqual(settings.value('theme'),theme)
    window.set_preferences('en','light','fire')
    window.close()
    restored=Window(QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat))
    self.assertEqual(restored.settings_button.text(),'Settings')
    self.assertEqual(ui.theme,'light')
    self.assertEqual(ui.spectrum_palette,'fire')
    restored.close()
   finally:
    window.close();ui.language='ko';ui.theme='dark';ui.spectrum_palette='classic'
 def test_theme_changes_reuse_spectrum_and_drag_reuses_background(self):
  import numpy as np
  import soundfile as sf
  from audio_view import AudioEditor
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'audio.wav';sf.write(path,np.sin(np.arange(16000)*0.2)*0.1,16000)
   editor=AudioEditor();editor.resize(800,500)
   spans=[[0,0.3,'pau'],[0.3,0.6,'a'],[0.6,1,'pau']]
   editor.load(path,spans,None);editor.show();APP.processEvents()
   image=editor.image;count=editor.background_builds
   editor.spans[1][0]=0.31;editor.update();APP.processEvents()
   self.assertEqual(editor.background_builds,count)
   ui.theme='light';editor.update();APP.processEvents()
   self.assertEqual(editor.background_builds,count+1)
   self.assertIs(editor.image,image)
   editor.close();ui.theme='dark'
 def test_warning_translation_is_reversible(self):
  from PySide6.QtWidgets import QTableWidgetItem
  item=QTableWidgetItem('original')
  ui.language='en';ui.set_text(item,'검토');self.assertEqual(item.text(),'Review')
  ui.language='ja';ui.refresh();self.assertEqual(item.text(),'要確認')
  ui.language='ko';ui.refresh()
if __name__=='__main__':unittest.main()
