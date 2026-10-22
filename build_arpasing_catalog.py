"""Generate credited filename/index mappings from the reviewed public sources."""
from pathlib import Path
import csv,gzip,json

ROOT=Path(__file__).resolve().parent
RESEARCH=ROOT/'tools/research/arpasing'

def read(path):
    for encoding in ['utf-8-sig','cp932','cp1252']:
        try:return path.read_bytes().decode(encoding)
        except UnicodeError:continue
    raise ValueError(str(path))

def build():
    manifest={r['id']:r for r in json.loads((RESEARCH/'download-results.json').read_text(encoding='utf-8'))}
    profiles=[]
    def add(identifier,pattern,compact=False,dx=False):
        for path in sorted(RESEARCH.glob(pattern)):
            if '__MACOSX' in path.parts or path.name.startswith('._'):continue
            pairs=[];raw=read(path)
            if path.suffix.lower()=='.csv':
                delimiter=';' if raw.splitlines()[0].count(';')>raw.splitlines()[0].count(',') else ','
                pairs=[(r[0],r[1]) for r in csv.reader(raw.splitlines(),delimiter=delimiter) if len(r)>1 and r[0]]
            else:pairs=[(s.strip(),s.strip()) for s in raw.splitlines() if s.strip()]
            entries={};overrides={};duplicates=0
            for name,sequence in pairs:
                if name in entries:duplicates+=1
                entries[name]=sequence
                if dx:overrides[name]=sequence.replace('_d_','_dx_')
            source=manifest[identifier]
            profiles.append(dict(id=str(identifier)+'-'+str(len(profiles)),author=source['writer'],url=source['url'],
                source=str(path.relative_to(RESEARCH)),entries=entries,overrides=overrides,compact=compact,duplicates=duplicates))
    add(1,'01/extracted/**/index.csv')
    add(2,'02/extracted/**/BiggityB_Arpasing.txt')
    add(3,'03/extracted/*/reclist.txt')
    add(4,'04/*/3 mora (588)/index.csv');add(4,'04/*/6 mora (348)/index.csv')
    add(4,'04/*/3 mora (588)/dr, kr, st, tr*/reclist.txt')
    add(5,'05/extracted/**/CMU_Arctic_index.csv')
    add(7,'07/index.csv');add(7,'07/additional pitches/index.csv');add(7,'07/dx append list/index.csv',dx=True)
    add(9,'09/extracted/**/index.csv');add(10,'10/extracted/**/reclist.txt')
    add(11,'11/extracted/**/index.csv');add(12,'12/extracted/**/reclist.txt')
    add(13,'13/extracted/index.csv');add(14,'14/extracted/**/reclist.txt')
    add(15,'15/extracted/**/index.csv')
    add(17,'17/*.txt',compact=True)
    add(19,'19/extracted/**/dx.txt')
    for name in ['CVVC (6 mora).txt','CC (3 mora).txt','Long tone vowels.txt','Tapped r.txt',
                 '3-mora FULL.txt','6-mora FULL.txt','3-mora LIGHT.txt']:
        add(20,'20/extracted/**/'+name)
    add(21,'21/extracted/**/index.csv')
    add(22,'22/extracted/yukilist verklad.txt');add(22,'22/extracted/dx/yukilist verklad dx.txt')
    add(23,'23/extracted/index.csv');add(24,'24/extracted/index.csv');add(25,'25/extracted/index_Ag_4_5.csv')
    assert {int(p['id'].split('-')[0]) for p in profiles}==set(range(1,26))-{6,8,16,18}
    result={'version':1,'directory':'https://arpasing.tubs.wtf/en/directories/reclists','profiles':profiles,
        'excluded':{'6':'Liverpool 별도 음소 체계','8':'ix 미지원 음소','16':'VCCV 변환 자료','18':'배포 링크 사용 불가'}}
    target=ROOT/'assets/arpasing-catalog.json.gz'
    target.write_bytes(gzip.compress(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    print(len(profiles),'profiles;',len({p['id'].split('-')[0] for p in profiles}),'directory entries;',target.stat().st_size,'bytes')

if __name__=='__main__':build()
