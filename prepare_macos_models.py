"""Extract platform-independent weights from the verified Windows V1.0 release."""
from pathlib import Path
import argparse
import hashlib
import shutil
import struct
import tempfile
import urllib.request
import zipfile

URL='https://github.com/geujang/OTONova/releases/download/v1.0.0/OTONova-V1.0-Setup.exe'
SHA256='7e86b76bc7cbde23d49c95e0b361e9c8d3cff91a0f5bf388ac4bc9946b13cc3e'
WEIGHTS=('English/last.ckpt','Japanese/last.ckpt','WFL/Archivoice/korean/last.ckpt','WFL/encoder/encoder.pt')

def prepare(installer,destination,expected_sha256=SHA256):
    installer=Path(installer);destination=Path(destination).resolve()
    with installer.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected_sha256:raise ValueError('Installer SHA-256 mismatch')
        stream.seek(-48,2);footer=stream.read(48)
        start=struct.unpack('<Q',footer[32:40])[0]
        if footer[40:]!=b'WFLOTO26' or start>=installer.stat().st_size-48:raise ValueError('Invalid installer footer')
        size=installer.stat().st_size-start-48
        stream.seek(start)
        with tempfile.TemporaryFile() as payload:
            digest=hashlib.sha256();remaining=size
            while remaining:
                chunk=stream.read(min(1024*1024,remaining))
                if not chunk:raise ValueError('Truncated installer')
                payload.write(chunk);digest.update(chunk);remaining-=len(chunk)
            if digest.digest()!=footer[:32]:raise ValueError('Payload SHA-256 mismatch')
            payload.seek(0)
            with zipfile.ZipFile(payload) as archive:
                for name in WEIGHTS:
                    info=archive.getinfo(name)
                    if not 0<info.file_size<2_000_000_000:raise ValueError('Invalid model size')
                with tempfile.TemporaryDirectory() as staging:
                    for name in WEIGHTS:
                        target=Path(staging)/name;target.parent.mkdir(parents=True,exist_ok=True)
                        with archive.open(name) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
                    # Existing weights are never silently replaced.
                    for name in WEIGHTS:
                        target=destination/name
                        if target.exists():
                            with target.open('rb') as left,(Path(staging)/name).open('rb') as right:
                                if hashlib.file_digest(left,'sha256').digest()!=hashlib.file_digest(right,'sha256').digest():
                                    raise FileExistsError('Different model already exists: '+str(target))
                    for name in WEIGHTS:
                        target=destination/name
                        if not target.exists():
                            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(Path(staging)/name,target)
    return [destination/name for name in WEIGHTS]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--installer',type=Path);parser.add_argument('--destination',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    if args.installer:prepare(args.installer,args.destination)
    else:
        with tempfile.TemporaryDirectory() as folder:
            installer=Path(folder)/'OTONova-V1.0-Setup.exe'
            print('Downloading verified V1.0 model source...',flush=True)
            urllib.request.urlretrieve(URL,installer);prepare(installer,args.destination)
    print('Verified model weights ready. No Windows executable was run.',flush=True)
if __name__=='__main__':main()
