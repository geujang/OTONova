"""Exercise Media Foundation WAV playback without changing source recordings."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['QT_MEDIA_BACKEND'] = 'windows'
import numpy as np
import soundfile as sf
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from audio_playback import set_wav_source


@unittest.skipUnless(sys.platform == 'win32', 'Windows Media Foundation test')
class PlaybackTests(unittest.TestCase):
    def test_wav_encodings_load_without_modifying_originals(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as folder:
            for subtype in ('PCM_U8', 'PCM_16', 'PCM_24', 'PCM_32', 'FLOAT',
                            'DOUBLE', 'ULAW', 'ALAW', 'IMA_ADPCM', 'MS_ADPCM'):
                with self.subTest(subtype=subtype):
                    path = Path(folder) / (subtype + '.wav')
                    sf.write(path, np.zeros((4410, 2), dtype='float32'), 44100, subtype=subtype)
                    original = path.read_bytes()
                    player = QMediaPlayer()
                    output = QAudioOutput()
                    output.setMuted(True)
                    player.setAudioOutput(output)
                    loop = QEventLoop()
                    timer = QTimer()
                    timer.setSingleShot(True)
                    timer.timeout.connect(loop.quit)
                    state = {'loaded': False}
                    def ready(status):
                        if status == QMediaPlayer.LoadedMedia:
                            state['loaded'] = True
                            loop.quit()
                    player.mediaStatusChanged.connect(ready)
                    player.errorOccurred.connect(lambda *args: loop.quit())
                    buffer = set_wav_source(player, path, player)
                    timer.start(5000)
                    if not state['loaded']:
                        loop.exec()
                    timer.stop()
                    self.assertTrue(state['loaded'], player.errorString())
                    self.assertEqual(path.read_bytes(), original)
                    player.setSource(QUrl())
                    player.deleteLater()
                    app.processEvents()


if __name__ == '__main__':
    unittest.main()
