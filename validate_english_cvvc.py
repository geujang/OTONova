"""Check all downloaded official rows against the released notation parser."""
from pathlib import Path
import html,json,re,zipfile
from english_cvvc import catalog,parse_sequence,canonical,MAP
from arpasing_core import PHONES

ROOT=Path(__file__).resolve().parent
def main():
    profiles=catalog()['profiles'];counts={};errors=[];approximations=set()
    def check(key,lines):
        family=profiles[key]['family'];n=0
        for line in lines:
            if not line.strip():continue
            try:
                units,notes=parse_sequence(canonical(line.strip()),family,profiles[key]['section'])
                assert all(set(u['model'])<=PHONES for u in units)
                approximations.update(notes);n+=1
            except Exception as exc:errors.append(dict(profile=key,line=line,error=str(exc)))
        counts[key]=n
    for p in (ROOT/'tools/research/salem').glob('*.js'):
        for key,literal in re.findall(r'(\w+)\s*=\s*`([\s\S]*?)`\s*;',p.read_text(encoding='utf-8')):
            if key in profiles:check(key,[html.unescape(s) for s in re.sub(r'<br\s*/?>','\n',literal).splitlines()])
    for p in (ROOT/'tools/research/english-symbol-audit').glob('delta_eng_g*.zip'):
        with zipfile.ZipFile(p) as z:
            text=z.read(next(n for n in z.namelist() if n.endswith(p.stem+'.txt'))).decode('utf-8-sig')
        check(p.stem,text.splitlines())
    assert set(counts)==set(profiles),(set(profiles)-set(counts))
    result=dict(profiles=len(counts),rows=sum(counts.values()),counts=counts,errors=errors,
                approximation_warnings=sorted(approximations))
    out=ROOT/'build/english-cvvc-v32-validation.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not errors,errors[:10]
    print(result['profiles'],'profiles /',result['rows'],'rows / no parse or model-token failures')
if __name__=='__main__':main()
