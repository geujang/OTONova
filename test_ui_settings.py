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
