"""Validate CORE filenames, model tokens and VCCV geometry against the supplied ZIP."""
from pathlib import Path
import argparse,json,tempfile,zipfile
from english_vccv import VccvResolver,create_oto
from arpasing_core import PHONES

ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);args=parser.parse_args()
    errors=[];counts={};entries=0;inferred=0
    with tempfile.TemporaryDirectory() as folder,zipfile.ZipFile(args.archive) as z:
        resolver=VccvResolver(folder)
        for name in z.namelist():
            if not name.startswith('CORE') or not name.endswith('.txt'):continue
            section=name.rsplit('/',1)[-1].split(' ',1)[0];counts[section]=0
            for stem in dict.fromkeys(s.strip() for s in z.read(name).decode('utf-8-sig').splitlines() if s.strip()):
                try:
                    record=resolver.metadata(Path(folder)/section/(stem+'.wav'))
                    assert set(record['phones'])<=PHONES
                    record.update(language='en',duration=len(record['phones'])*.2,
                        intervals=[[i*.2,(i+1)*.2,p] for i,p in enumerate(record['phones'])])
                    rows=create_oto(record)
                    assert rows and len(rows)==len(record['vccv_aliases'])
                    for row in rows:
                        assert abs(row['values'][4]-row['values'][3]/2)<1e-7
                        assert 0<=row['absolute'][0]<=row['absolute'][2]<=row['absolute'][3]<=row['absolute'][4]<=record['duration']
                    entries+=len(rows);inferred+=len(record['vccv_inferred_aliases']);counts[section]+=1
                except Exception as exc:errors.append(dict(section=section,stem=stem,error=str(exc)))
    result=dict(sections=counts,files=sum(counts.values()),entries=entries,inferred_aliases=inferred,errors=errors,
        scope='Structural validation with synthetic intervals; not an acoustic accuracy score.')
    out=ROOT/'build/vccv-core-validation.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not errors,errors[:5]
    print(result['files'],'recordings /',entries,'aliases / overlap=preutterance/2 verified; inferred',inferred)

if __name__=='__main__':main()
