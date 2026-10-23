"""Build hashed format catalogs from locally obtained reference materials.

No original recording lists or oto timing values are redistributed.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,zipfile
from format_detection import fingerprint

ROOT=Path(__file__).resolve().parent

def build(coc,cbnn,cmpx):
    sources={'ko_coc':[], 'ko_cbnn':[], 'ko_cmpx':[]}
    with zipfile.ZipFile(coc) as archive:
        for item in archive.infolist():
            if item.filename.endswith('/oto.ini'):
                sources['ko_coc'].append((item.filename,archive.read(item)))
    for mode,folder in [('ko_cbnn',cbnn),('ko_cmpx',cmpx)]:
        for path in sorted(Path(folder).rglob('*.ini')):
            if path.name=='oto_full.ini':continue
            sources[mode].append((path.relative_to(folder).as_posix(),path.read_bytes()))
    catalog={};signatures=json.loads((ROOT/'assets/reclist-signatures.json').read_text(encoding='utf-8'));provenance={}
    for mode,files in sources.items():
        recordings={}
        for _,raw in files:
            for line in raw.decode('utf-8-sig').splitlines():
                if '.wav=' not in line:continue
                stem,right=line.split('.wav=',1);alias=right.rsplit(',',5)[0]
                aliases=recordings.setdefault(stem,[])
                if alias not in aliases:aliases.append(alias)
        if not recordings:raise ValueError('No reference oto rows: '+mode)
        catalog[mode]={'recordings':{fingerprint(s):a for s,a in recordings.items()}}
        signatures[mode]={'stems':sorted(fingerprint(s) for s in recordings),'aliases':sorted({fingerprint(a) for rows in recordings.values() for a in rows})}
        provenance[mode]={'recordings':len(recordings),'aliases':sum(map(len,recordings.values())),
                          'source_sha256':[hashlib.sha256(raw).hexdigest() for _,raw in files]}
    (ROOT/'assets/korean-combined-catalog.json.gz').write_bytes(gzip.compress(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    (ROOT/'assets/reclist-signatures.json').write_text(json.dumps(signatures,separators=(',',':')),encoding='utf-8')
    return provenance

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--coc-zip',required=True,type=Path)
    parser.add_argument('--cbnn-dir',required=True,type=Path)
    parser.add_argument('--cmpx-dir',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.coc_zip,args.cbnn_dir,args.cmpx_dir),indent=2))
