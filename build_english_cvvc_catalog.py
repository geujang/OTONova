"""Build DELTA + Salem fingerprints; retain source downloads under ignored research/."""
from pathlib import Path
import gzip,hashlib,html,json,re,zipfile
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent
DELTA_KEYS=['o1f04ji5z324n0u','vewutsa6t10k7ob','2e8qozvoop1bt7t','idh8avm28zr1ci1',
            'qfgybyesln9858p','ne0gy9qr01dmx6f','0o1d2x5sexuvhq1','ks9751rlaurx6ae']

def main():
    data=json.loads(gzip.decompress((ROOT/'assets/salem-cvvc-catalog.json.gz').read_bytes()))
    data['schema']=2;data['family']='DELTA / Salem'
    for p in data['profiles'].values():p['family']='Salem'
    research=ROOT/'tools/research/english-symbol-audit';research.mkdir(parents=True,exist_ok=True)
    for i,key in enumerate(DELTA_KEYS):
        name=f'delta_eng_g{i:02}';path=research/(name+'.zip')
        if not path.exists():
            page=urlopen('https://www.mediafire.com/?'+key,timeout=30).read().decode()
            url=html.unescape(re.search(r'href="(https://download[^"]+)"[^>]*id="downloadButton"',page)[1])
            path.write_bytes(urlopen(url,timeout=40).read())
        with zipfile.ZipFile(path) as z:
            text=z.read(next(n for n in z.namelist() if n.endswith(name+'.txt'))).decode('utf-8-sig')
        lines=[s.strip() for s in text.splitlines() if s.strip()]
        data['profiles'][name]=dict(family='DELTA',edition=name,beats=0,section='core',
            source='https://tl.tubs.wtf/2020/11/09/delta-eng',lines=len(lines),
            fingerprints=sorted({hashlib.sha256(s.lstrip('_+').encode()).hexdigest()[:24] for s in lines}))
    target=ROOT/'assets/english-cvvc-catalog.json.gz'
    target.write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    print(len(data['profiles']),'profiles:',target)

if __name__=='__main__':main()
