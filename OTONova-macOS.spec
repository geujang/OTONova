# Build on macOS with a Python matching the desired CPU architecture.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files
root=Path(SPECPATH)
datas=[(str(root/'assets'),'assets')]
for folder in ('English','Japanese','WFL/Archivoice/korean','WFL/encoder'):
    for path in (root/folder).iterdir():
        if path.name in {'last.ckpt','encoder.pt','config.yaml','config.json','preprocessor_config.json','phonemes.txt','langs.txt','lang_phonemes.json'}:
            datas.append((str(path),folder))
for name in ('model.py','infer.py','utils.py'):datas.append((str(root/'WFL'/name),'WFL'))
for name in ('wfl_backend.py','wfl_weighted_model.py'):datas.append((str(root/'tools'/name),'tools'))
for name in ('README.md','CREDITS.md','MODEL_COMPRESSION.md','SUPPORTED_FORMATS.md','THIRD_PARTY_NOTICES.md','MACOS.md'):
    datas.append((str(root/name),'.'))
datas+=collect_data_files('transformers')
a=Analysis([str(root/'mac_entry.py')],pathex=[str(root)],datas=datas,binaries=[],
    hiddenimports=['app_bootstrap','torch','torchaudio','yaml','click','librosa','scipy.signal',
        'transformers.models.whisper.modeling_whisper','transformers.models.whisper.feature_extraction_whisper'],
    excludes=['tkinter','matplotlib','pytest'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='OTONova',console=False,
    argv_emulation=False,target_arch=None,codesign_identity=os.environ.get('OTONOVA_CODESIGN_IDENTITY'))
coll=COLLECT(exe,a.binaries,a.datas,name='OTONova')
app=BUNDLE(coll,name='OTONova.app',icon=str(root/'build/otonova.icns'),bundle_identifier='io.github.geujang.otonova',
    info_plist={'CFBundleShortVersionString':'1.0.1','CFBundleVersion':'1.0.1','NSHighResolutionCapable':True,
               'NSHumanReadableCopyright':'OTONova — KURO / geujang; third-party credits included.'})
