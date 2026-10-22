"""Compile the supplied PaintedCz CORE archive; no audio/BGM is redistributed."""
from pathlib import Path
import argparse,gzip,hashlib,json,zipfile

ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);args=parser.parse_args()
    from english_vccv import fingerprint,parse_recording
    sections={};notes=[];lists={}
    with zipfile.ZipFile(args.archive) as z:
        for name in z.namelist():
            if name.startswith('CORE Reclist') and name.endswith('.txt'):
                section=name.rsplit('/',1)[-1].split(' ',1)[0]
                lists[section]=[s.strip() for s in z.read(name).decode('utf-8-sig').splitlines() if s.strip()]
        for name in z.namelist():
            if not name.endswith('/oto.ini'):continue
            section=name.split('/')[-2];entries={}
            for line in z.read(name).decode('utf-8-sig').splitlines():
                if '=' not in line:continue
                wav,rest=line.split('=',1);stem=wav[:-4];alias=rest.split(',',1)[0]
                info=entries.setdefault(stem,dict(aliases=[],empty_aliases=0,listed=stem in lists.get(section,[])))
                info['aliases'].append(alias)
                if not alias:info['empty_aliases']+=1
            for stem in lists.get(section,[]):
                if stem not in entries:entries[stem]=dict(aliases=[],empty_aliases=0,listed=True,warning='공식 리스트에 있으나 기본 oto 파일명이 일치하지 않음')
            for stem,info in entries.items():
                groups=parse_recording(stem,section)
                inferred=[]
                if section=='V' and info['empty_aliases']:
                    empty_slots=[i for i,a in enumerate(info['aliases']) if not a]
                    first=next((a[1:] for a in info['aliases'] if a.startswith('-')),stem.split('_')[0].strip('-'))
                    defaults=['-'+first,first,stem.split('_')[0].strip('-')+'-','_'+first]
                    info['aliases']=[a or defaults[i] for i,a in enumerate(info['aliases'])]
                    inferred=[defaults[i] for i in empty_slots]
                if section=='CV' and info['empty_aliases']:
                    vowel=next(u['symbol'] for u in groups[0] if u['kind']=='vowel')
                    consonant=groups[1][0]['symbol']
                    defaults=['-'+''.join(u['symbol'] for u in groups[0]),''.join(u['symbol'] for u in groups[1]),vowel+' '+consonant]
                    empty_slots=[i for i,a in enumerate(info['aliases']) if not a]
                    info['aliases']=[a or defaults[i] for i,a in enumerate(info['aliases'])]
                    inferred.extend(defaults[i] for i in empty_slots)
                if not info['aliases'] and section in ('CC-','CCV'):
                    group=groups[0];v=next(i for i,u in enumerate(group) if u['kind']=='vowel')
                    consonants=group[v+1:] if section=='CC-' else group[:v]
                    cluster=''.join(u['symbol'] for u in consonants)
                    info['aliases']=[cluster,cluster+'-'] if section=='CC-' else ['-'+cluster,cluster]
                    inferred+=info['aliases']
                info['inferred_aliases']=list(dict.fromkeys(inferred))
                if not info['listed']:info['warning']='기본 oto에는 있으나 녹음 리스트와 파일명이 다름: 원문 확인'
                if info.get('warning'):notes.append(dict(section=section,stem=stem,warning=info['warning']))
            sections[section]={fingerprint(stem):info for stem,info in entries.items()}
        # Preserve the author's complete supplied terms, including the 2023 update.
        (ROOT/'assets/vccv-core-terms.rtf').write_bytes(z.read('Terms Of Use.rtf'))
    result=dict(schema=1,creator='PaintedCz',archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                source='CORE American English VCCV.zip (user supplied)',sections=sections)
    (ROOT/'assets/vccv-core-catalog.json.gz').write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0))
    out=ROOT/'build/vccv-catalog-source-issues.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')
    print('sections',len(sections),'recordings',sum(len(e) for e in sections.values()),
          'nonempty aliases',sum(len(i['aliases']) for e in sections.values() for i in e.values()),'source mismatches',len(notes))

if __name__=='__main__':main()
