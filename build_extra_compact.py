"""Apply v30 lossless compression and explicitly audited runtime exclusions."""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'release/WFL-Oto-Windows-v29'
TARGET = ROOT / 'release/WFL-Oto-Windows-v30'
MODELS = ('English/last.ckpt', 'Japanese/last.ckpt',
          'WFL/Archivoice/korean/last.ckpt', 'WFL/encoder/encoder.pt')
FFMPEG = ('avcodec-61.dll', 'avformat-61.dll', 'avutil-59.dll', 'swresample-5.dll', 'swscale-8.dll')


def main():
    if TARGET.exists():
        raise RuntimeError('Target already exists; use a fresh distribution folder')
    shutil.copytree(SOURCE, TARGET, ignore=shutil.ignore_patterns('__pycache__', '*.pyc',
                    'wfl-runtime.log', 'wfl-gui.log', 'gui-preview.png'))
    packages = TARGET / 'runtime/Lib/site-packages'
    # These native modules are unrelated to STFT or polyphase resampling. They
    # were not imported by the complete app dependency set in the v29 audit.
    unused_scipy = (
        'io/_fast_matrix_market/_fmm_core.cp311-win_amd64.pyd',
        'stats/_unuran/unuran_wrapper.cp311-win_amd64.pyd',
        'odr/__odrpack.cp311-win_amd64.pyd',
        'cluster/_hierarchy.cp311-win_amd64.pyd',
        'io/matlab/_mio5_utils.cp311-win_amd64.pyd',
        'cluster/_optimal_leaf_ordering.cp311-win_amd64.pyd',
        'fftpack/convolve.cp311-win_amd64.pyd',
        'io/matlab/_streams.cp311-win_amd64.pyd',
        'linalg/_matfuncs_sqrtm_triu.cp311-win_amd64.pyd',
        'cluster/_vq.cp311-win_amd64.pyd',
        'special/_test_internal.cp311-win_amd64.pyd',
        'optimize/cython_optimize/_zeros.cp311-win_amd64.pyd',
        'ndimage/_cytest.cp311-win_amd64.pyd',
        '_lib/_test_ccallback.cp311-win_amd64.pyd',
        'io/matlab/_mio_utils.cp311-win_amd64.pyd',
    )
    removed = []
    def remove(path):
        assert path.resolve().is_relative_to(TARGET.resolve())
        if path.exists():
            removed.append({'path': str(path.relative_to(TARGET)), 'bytes': path.stat().st_size})
            path.unlink()
    for name in unused_scipy:
        remove(packages / 'scipy' / name)
    remove(packages / 'torch/bin/protoc.exe')
    for name in FFMPEG:
        remove(packages / 'PySide6' / name)
    remove(packages / 'PySide6/plugins/multimedia/ffmpegmediaplugin.dll')
    tokenizers = packages / 'tokenizers'
    assert tokenizers.resolve().parent == packages.resolve()
    for path in tokenizers.rglob('*'):
        if path.is_file():
            removed.append({'path': str(path.relative_to(TARGET)), 'bytes': path.stat().st_size})
    shutil.rmtree(tokenizers)
    # Remove optional tokenizer code and installation metadata together so
    # Transformers selects its supported no-tokenizers import path.
    archive = packages / 'wfl-code.zip'
    temporary = archive.with_suffix('.tmp')
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name in source.namelist():
            top = name.split('/')[0]
            if top == 'tokenizers' or top.startswith('tokenizers-') and top.endswith('.dist-info'):
                continue
            output.writestr(name, source.read(name))
    temporary.replace(archive)
    # GGUF is not used by WFL. Defer this optional tokenizer-dependent import
    # until an actual GGUF file is requested, as modeling_utils already does.
    config = packages / 'transformers/configuration_utils.py'
    text = config.read_text(encoding='utf-8')
    eager = 'from .modeling_gguf_pytorch_utils import load_gguf_checkpoint\n'
    assert text.count(eager) == 1 and text.count('            if gguf_file:\n') == 1
    text = text.replace(eager, '', 1).replace('            if gguf_file:\n',
        '            if gguf_file:\n                from .modeling_gguf_pytorch_utils import load_gguf_checkpoint\n', 1)
    config.write_text(text, encoding='utf-8')
    models = {}
    for name in MODELS:
        path = TARGET / name
        original = path.read_bytes()
        digest = hashlib.sha256(original).digest()
        compressed = b'WFLZLIB1' + struct.pack('<Q', len(original)) + digest + zlib.compress(original, 6)
        assert zlib.decompress(compressed[48:]) == original
        path.write_bytes(compressed)
        models[name] = {'original_bytes': len(original), 'compressed_bytes': len(compressed),
                        'original_sha256': digest.hex(), 'roundtrip_exact': True}
    shutil.copy2(ROOT / 'tools/wfl_backend.py', TARGET / 'tools/wfl_backend.py')
    shutil.copy2(ROOT / 'app_bootstrap.py', TARGET / 'app_bootstrap.py')
    for name in ('vcv_gui.py', 'audio_playback.py'):
        shutil.copy2(ROOT / name, TARGET / name)
    shutil.copy2(ROOT / 'README.md', TARGET / 'README.md')
    report = {'version': 30, 'model_compression': models, 'removed': removed,
              'media_backend': 'windows', 'precision_changed': False,
              'source_backup_tag': 'before-extra-slim-v30'}
    (TARGET / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Compressed model savings:', sum(v['original_bytes'] - v['compressed_bytes'] for v in models.values()), flush=True)
    print('Removed runtime files:', sum(v['bytes'] for v in removed), flush=True)


if __name__ == '__main__':
    main()
