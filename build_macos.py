"""Create a native .app on a Mac; Windows executables cannot be converted."""
from pathlib import Path
import argparse
import platform
import subprocess
import sys
from prepare_macos_models import WEIGHTS
ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--skip-model-check',action='store_true');args=parser.parse_args()
    if sys.platform!='darwin':raise SystemExit('Build this app on macOS using a native Python 3.11 environment.')
    if not args.skip_model_check:
        missing=[name for name in WEIGHTS if not (ROOT/name).is_file()]
        if missing:raise SystemExit('Run python prepare_macos_models.py first. Missing: '+', '.join(missing))
    iconset=ROOT/'build/otonova.iconset';iconset.mkdir(parents=True,exist_ok=True)
    for pixels,filename in [(16,'16x16'),(32,'16x16@2x'),(32,'32x32'),(64,'32x32@2x'),(128,'128x128'),(256,'128x128@2x'),(256,'256x256'),(512,'256x256@2x'),(512,'512x512'),(1024,'512x512@2x')]:
        subprocess.run(['sips','-z',str(pixels),str(pixels),str(ROOT/'assets/otonova-logo.png'),'--out',str(iconset/('icon_'+filename+'.png'))],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(ROOT/'build/otonova.icns')],check=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--clean','--noconfirm',str(ROOT/'OTONova-macOS.spec')],cwd=ROOT,check=True)
    output=ROOT/('dist/OTONova-macOS-V1.0-'+platform.machine()+'.zip')
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(ROOT/'dist/OTONova.app'),str(output)],check=True)
    print(output)
    from package_macos_dmg import package
    package(ROOT/'dist/OTONova.app', output.with_suffix('.dmg'))
if __name__=='__main__':main()
