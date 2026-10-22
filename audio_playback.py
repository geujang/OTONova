"""WAV playback without shipping FFmpeg; keep decoded fallback audio in memory."""
import io
import soundfile as sf
from PySide6.QtCore import QBuffer, QIODevice, QUrl


def set_wav_source(player, path, parent=None):
    if sf.info(path).subtype in {'PCM_U8', 'PCM_16', 'PCM_24', 'PCM_32', 'FLOAT'}:
        player.setSource(QUrl.fromLocalFile(str(path)))
        return None
    # Media Foundation does not support every WAV encoding (notably float64).
    # Decode using the existing libsndfile, at the same float32 precision used
    # by waveform display and model input. Never rewrite the source recording.
    audio, rate = sf.read(path, dtype='float32')
    stream = io.BytesIO()
    sf.write(stream, audio, rate, format='WAV', subtype='FLOAT')
    buffer = QBuffer(parent)
    buffer.setData(stream.getvalue())
    buffer.open(QIODevice.ReadOnly)
    player.setSourceDevice(buffer, QUrl('decoded.wav'))
    return buffer


def set_wav_segment_source(player, path, begin, end, parent=None):
    """Use a frame-exact, stereo-preserving clip so playback cannot overshoot."""
    with sf.SoundFile(path) as source:
        first=max(0,min(len(source),round(begin*source.samplerate)))
        last=max(first,min(len(source),round(end*source.samplerate)))
        if last<=first:raise ValueError('Empty playback segment')
        source.seek(first)
        audio=source.read(last-first,dtype='float32',always_2d=True)
        rate=source.samplerate
    stream=io.BytesIO()
    sf.write(stream,audio,rate,format='WAV',subtype='FLOAT')
    buffer=QBuffer(parent)
    buffer.setData(stream.getvalue());buffer.open(QIODevice.ReadOnly)
    player.setSourceDevice(buffer,QUrl('segment.wav'))
    return buffer
