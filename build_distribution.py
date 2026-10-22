"""Build a single, verifiable Windows self-extracting distribution EXE."""
from pathlib import Path
import hashlib,struct,subprocess,zipfile,shutil
import argparse

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--version',default='1.0');args=parser.parse_args()
    schema_version=36 if args.version=='1.0' else int(args.version)
    version='V1.0' if args.version=='1.0' else 'v'+str(args.version)
    brand='OTONova' if args.version=='1.0' else ('OtoNova' if schema_version>=31 else 'WFL-Oto')
    source=ROOT/('release/'+brand+'-Windows-'+version)
    build=ROOT/('build/distribution-'+version);build.mkdir(parents=True,exist_ok=True)
    stub=build/'installer.exe'
    installer_source=build/'installer.cs'
    code=(ROOT/'tools/distribution_installer.cs').read_text(encoding='utf-8').replace('const string Version="v27";','const string Version="'+version+'";')
    if (source/'app_bootstrap.py').exists():
        code=code.replace('_internal/assets/','assets/')
        code=code.replace('"WFL-Oto.exe","runtime/python.exe"','"WFL-Oto.exe","runtime/python.exe","runtime/pythonw.exe","app_bootstrap.py","vcv_gui.py","runtime/python311.zip","runtime/Lib/site-packages/wfl-code.zip","runtime/Lib/site-packages/wfl-pure.zip","runtime/Lib/site-packages/wfl_zip_support.py","runtime/Lib/site-packages/PySide6/QtWidgets.pyd"')
    if (source/'audio_playback.py').exists():
        code=code.replace('"WFL-Oto.exe",','"WFL-Oto.exe","audio_playback.py",',1)
    if brand in ('OtoNova','OTONova'):
        code=code.replace('WFL-Oto',brand).replace('약 2.5GB 필요','약 900MB 필요')
        code=code.replace('영어 보조 모델','영어 모델')
        code=code.replace('var intro=new Label','form.Icon=Icon.ExtractAssociatedIcon(Self);\n        var intro=new Label')
        code=code.replace('"'+brand+'.exe",','"'+brand+'.exe","english_cvvc.py","assets/otonova.ico","assets/otonova-logo.png","assets/salem-cvvc-catalog.json.gz",',1)
        if schema_version>=32:code=code.replace('"english_cvvc.py",','"english_cvvc.py","assets/english-cvvc-catalog.json.gz",',1)
        if schema_version>=34:code=code.replace('"english_cvvc.py",','"english_cvvc.py","ui_settings.py",',1)
        if schema_version>=33:code=code.replace('"english_cvvc.py",','"english_cvvc.py","english_vccv.py","assets/vccv-core-catalog.json.gz","assets/vccv-core-terms.rtf",',1)
    installer_source.write_text(code,encoding='utf-8-sig')
    compiler=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64',
        '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
        '/reference:System.IO.Compression.dll',
        *(['/win32icon:'+str(ROOT/'assets/otonova.ico')] if brand in ('OtoNova','OTONova') else []),
        '/out:'+str(stub),str(installer_source)],check=True)
    payload=build/'payload.zip'
    with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
        for path in source.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or 'wfl-matplotlib-cache' in path.parts or path.suffix=='.pyc' or path.name in {'wfl-runtime.log','wfl-gui.log','gui-preview.png'}:continue
            archive.write(path,path.relative_to(source).as_posix())
    print('Payload compressed',payload.stat().st_size,flush=True)
    target=ROOT/('release/'+brand+'-'+version+'-Setup.exe')
    digest=hashlib.sha256()
    with target.open('wb') as output:
        output.write(stub.read_bytes());start=output.tell()
        with payload.open('rb') as content:
            while chunk:=content.read(1024*1024):digest.update(chunk);output.write(chunk)
        output.write(digest.digest());output.write(struct.pack('<q',start));output.write(b'WFLOTO26')
    subprocess.run([str(target),'/verify'],check=True,timeout=180)
    print('Installer verified:',target,target.stat().st_size,flush=True)

if __name__=='__main__':main()
