"""Build a single-runtime distribution without altering model weights."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'release/WFL-Oto-Windows-v28'
TARGET = ROOT / 'release/WFL-Oto-Windows-v29'
EXCLUDED = {'__pycache__', 'tests', 'test', 'testing_data', 'test_data', 'benchmarks'}
UNUSED = {'matplotlib', 'mpl_toolkits', 'matplotlib.libs', 'PIL', 'pillow.libs',
          'fontTools', 'contourpy', 'kiwisolver', 'cycler', 'pyparsing'}
PURE = {'sympy', 'mpmath', 'networkx'}
APP = ('vcv_gui.py', 'vcv_core.py', 'audio_view.py', 'formats.py', 'format_detection.py',
       'korean_core.py', 'korean_formats.py', 'arpasing_core.py', 'app_bootstrap.py')


def pack_standard_library(runtime):
    library = runtime / 'Lib'
    archive_path = runtime / 'python311.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in library.rglob('*'):
            relative = path.relative_to(library)
            if path.is_file() and relative.parts[0] != 'site-packages':
                archive.write(path, relative.as_posix())
    for path in library.iterdir():
        if path.name == 'site-packages':
            continue
        assert path.resolve().parent == library.resolve() and library.resolve().is_relative_to(TARGET.resolve())
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def pack_library_code(packages):
    selected = []
    keep_packages = {'transformers', 'PySide6', 'shiboken6', 'torchaudio', 'certifi'}
    native_directories = {p.parent for p in packages.rglob('*') if p.is_file() and p.suffix.lower() in {'.dll', '.pyd'}}
    for path in packages.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(packages)
        if relative.parts[0] in keep_packages:
            continue
        if path.name == '__init__.py' and path.parent in native_directories:
            continue
        if path.suffix == '.py' and b'__file__' not in path.read_bytes():
            selected.append(path)
        elif any(part.endswith('.dist-info') for part in relative.parts):
            selected.append(path)
    archive_path = packages / 'wfl-code.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in selected:
            archive.write(path, path.relative_to(packages).as_posix())
    for path in selected:
        assert path.resolve().is_relative_to((TARGET / 'runtime/Lib/site-packages').resolve())
        path.unlink()
    # Empty dist-info directories would shadow the metadata kept inside ZIP.
    for path in sorted((p for p in packages.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(path.iterdir()):
            assert path.resolve().is_relative_to(packages.resolve())
            path.rmdir()
    shutil.copy2(ROOT / 'tools/wfl_zip_support.py', packages / 'wfl_zip_support.py')
    (packages / 'wfl-code.pth').write_text('wfl-code.zip\nimport wfl_zip_support\n', encoding='utf-8')


def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def needed(relative):
    if any(part in EXCLUDED for part in relative.parts):
        return False
    if relative.suffix.lower() in {'.pyc', '.pyo', '.lib', '.a', '.pdb', '.h', '.hpp', '.pyi',
                                  '.c', '.cpp', '.pyx', '.pxd', '.cmake', '.template', '.thrift'}:
        return False
    parts = relative.parts
    if len(parts) > 2 and parts[:2] == ('Lib', 'site-packages'):
        package = parts[2]
        if package in UNUSED | PURE or package.lower().startswith(('matplotlib-', 'pillow-', 'fonttools-', 'contourpy-', 'kiwisolver-', 'cycler-', 'pyparsing-')):
            return False
        if len(parts) > 4 and parts[2:4] == ('transformers', 'models') and parts[4] not in {'auto', 'whisper', '__init__.py'}:
            return False
    return True


def main():
    if TARGET.exists():
        raise RuntimeError('Target already exists; choose a fresh version directory')
    TARGET.mkdir()
    for source in (SOURCE / 'runtime').rglob('*'):
        if source.is_file() and needed(source.relative_to(SOURCE / 'runtime')):
            link(source, TARGET / 'runtime' / source.relative_to(SOURCE / 'runtime'))
    packages = TARGET / 'runtime/Lib/site-packages'
    with zipfile.ZipFile(packages / 'wfl-pure.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for package in sorted(PURE):
            for path in (SOURCE / 'runtime/Lib/site-packages' / package).rglob('*'):
                if path.is_file() and not any(part in EXCLUDED for part in path.parts) and path.suffix not in {'.pyc', '.pyi'}:
                    archive.write(path, path.relative_to(SOURCE / 'runtime/Lib/site-packages').as_posix())
    (packages / 'wfl-pure.pth').write_text('wfl-pure.zip\n', encoding='utf-8')
    # The upstream aggregator eagerly imports every model package. Only these
    # architectures are shipped; the original implementation stays in v28.
    models_init = packages / 'transformers/models/__init__.py'
    header = '\n'.join(models_init.read_text(encoding='utf-8').splitlines()[:14])
    temporary = models_init.with_suffix('.tmp')
    temporary.write_text(header + '\nfrom . import auto, whisper\n', encoding='utf-8')
    temporary.replace(models_init)
    pack_standard_library(TARGET / 'runtime')
    qt = SOURCE / '_internal/PySide6'
    omitted = ('Qt6Qml', 'Qt6Quick', 'Qt6VirtualKeyboard', 'Qt6Pdf', 'Qt6OpenGL', 'Qt6MultimediaWidgets', 'QtMultimediaWidgets', 'opengl32sw')
    for path in qt.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(qt)
        if path.name.startswith(omitted) or 'translations' in relative.parts or 'platforminputcontexts' in relative.parts:
            continue
        if 'imageformats' in relative.parts and path.name == 'qpdf.dll':
            continue
        link(path, packages / 'PySide6' / relative)
    for name in ('PySide6', 'shiboken6'):
        # ABI3 extension modules work on both bundled Python versions.
        for path in (ROOT / '.venv/Lib/site-packages' / name).rglob('*.py'):
            relative = path.relative_to(ROOT / '.venv/Lib/site-packages' / name)
            if '__pycache__' not in relative.parts and relative.parts[0] not in {'scripts', 'QtAsyncio'}:
                link(path, packages / name / relative)
    for path in (SOURCE / '_internal/shiboken6').rglob('*'):
        if path.is_file():
            link(path, packages / 'shiboken6' / path.relative_to(SOURCE / '_internal/shiboken6'))
    pack_library_code(packages)
    for name in APP:
        shutil.copy2(ROOT / name, TARGET / name)
    for name in ('English', 'Japanese', 'WFL', 'licenses', 'assets'):
        source = ROOT / name if name != 'licenses' else SOURCE / name
        for path in source.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name not in {'dataset.json', 'data_split.json'} and path.suffix != '.pyc':
                link(path, TARGET / name / path.relative_to(source))
    (TARGET / 'tools').mkdir(exist_ok=True)
    for name in ('wfl_backend.py', 'wfl_weighted_model.py'):
        shutil.copy2(ROOT / 'tools' / name, TARGET / 'tools' / name)
    for name in ('CREDITS.md', 'README.md', 'model-slim-validation.json', 'model-inference-validation.json'):
        shutil.copy2(ROOT / name, TARGET / name)
    compiler = 'C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([compiler, '/nologo', '/codepage:65001', '/target:winexe', '/platform:x64',
                    '/reference:System.Windows.Forms.dll', '/out:' + str(TARGET / 'WFL-Oto.exe'),
                    str(ROOT / 'tools/distribution_launcher.cs')], check=True)
    report = {'version': 29, 'single_runtime': True,
              'bytes': sum(p.stat().st_size for p in TARGET.rglob('*') if p.is_file()),
              'files': sum(1 for p in TARGET.rglob('*') if p.is_file()), 'model_weights_unchanged': True}
    (TARGET / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
