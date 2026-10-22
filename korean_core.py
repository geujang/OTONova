"""Korean filename phonemes and direct constrained WFL alignment."""
from pathlib import Path
import json,re,sys,subprocess,hashlib,unicodedata

MODEL_ROOT=Path(__file__).resolve().parent/'WFL'
VOWELS={'a','e','eo','eu','i','o','u'}
CODAS={'K','T','P','N','NG','M','L'}
KNOWN={'AP','SP','a','axh','b','ch','cl','d','e','eo','eu','exh','g','h','i','j','jj','k','kk','m','mlem','n','o','p','pp','r','s','sh','ss','t','tt','u','vf','w','y'}|CODAS
PHONE_SUBSTITUTIONS={'f':'h','v':'s','z':'s','rr':'L','H':'axh','th':'h','l':'L'}
ALIGNMENT_VERSION=3
AUXILIARY={'dh':('en','dh','d'),'ts':('ja','ts','ch'),'er':('en','r','L'),'@r':('en','r','L')}
ROMAN=sorted(KNOWN|{'f','v','z','th','rr','H','l'},key=len,reverse=True)

def legacy_filename_phones(stem):
    stem=unicodedata.normalize('NFC',stem)
    text=re.sub(r'\(([^)]+)\)',r' \1 ',stem)
    if text.casefold()=='breath':return ['SP','AP','SP']
    result=[];pos=0
    onset=['g','kk','n','d','tt','r','m','b','pp','s','ss','','j','jj','ch','k','t','p','h']
    vowel=[['a'],['e'],['y','a'],['y','e'],['eo'],['e'],['y','eo'],['y','e'],['o'],['w','a'],['w','e'],['w','i'],['y','o'],['u'],['w','eo'],['w','e'],['w','i'],['y','u'],['eu'],['eu','i'],['i']]
    coda=['','K','K','K','N','N','N','T','L','K','M','P','L','T','P','L','M','P','P','T','T','NG','T','T','K','T','P','T']
    while pos<len(text):
        char=text[pos]
        if char in "_ '-\t":pos+=1;continue
        if '가'<=char<='힣':
            value=ord(char)-0xac00
            result.extend(([onset[value//588]] if onset[value//588] else [])+vowel[value//28%21]+([coda[value%28]] if coda[value%28] else []))
            pos+=1;continue
        match=next((p for p in ROMAN if text.startswith(p,pos)),None)
        if not match:raise ValueError('해석할 수 없는 가사 표기: '+text[pos:])
        result.append(match);pos+=len(match)
    return ['SP']+[PHONE_SUBSTITUTIONS.get(p,p) for p in result]+['SP']

def filename_phones(stem,mode='ko_cvvc'):
    if mode=='ko_cvvc':return legacy_filename_phones(stem)
    from korean_formats import transcribe
    return transcribe(stem,mode)[0]


def create_oto(record,mode='ko_cvvc'):
    if mode!='ko_cvvc':
        from korean_formats import create_oto as create_profile_oto
        return create_profile_oto(record,mode)
    from vcv_core import make_entry,two_thirds
    spans=record['intervals'];duration=record['duration'];wav=record['wav'];rows=[]
    def add(alias,off,overlap,pre,end,lead,kind):
        rows.append(make_entry(wav,alias,off,overlap,pre,end-lead,end,duration,[],
                              fixed_lead=lead,allow_negative_overlap=True))
        rows[-1]['entry_kind']=kind
    previous=None
    for i,span in enumerate(spans):
        start,end,phone=span
        if phone not in VOWELS:continue
        j=i-1
        while j>=0 and (spans[j][2] not in VOWELS|CODAS|{'SP','AP','pau'} or j in record.get('onset_indices',[])):j-=1
        onset=spans[j+1:i]
        cv=''.join(p for _,_,p in onset)+phone
        target=two_thirds(span)
        if previous is None:
            begin=onset[0][0] if onset else start
            add('- '+cv,begin-.3,begin,start,target,.07,'start')
        if onset:
            off=onset[0][0]+(start-onset[0][0])/3
            add(cv,off,(off+start)/2,start,target,.07,'cv')
        else:add(phone,start,start,start,target,.07,'cv')
        if previous is not None and not onset and spans[i-1][2] in VOWELS:
            off=two_thirds(previous)
            add(previous[2]+' '+phone,off,previous[1],start,target,.04,'vv')
        # Both onset VC and coda VC use the same VC rule.
        if i+1<len(spans) and spans[i+1][2] not in VOWELS|{'SP','AP','pau'}:
            following=spans[i+1];end_c=following[1]
            k=i+2
            is_onset=following[2] not in CODAS or i+1 in record.get('onset_indices',[])
            if is_onset:
                while k<len(spans) and spans[k][2] not in VOWELS|CODAS|{'SP','AP','pau'}:
                    end_c=spans[k][1];k+=1
            name=''.join(s[2] for s in spans[i+1:k]) if is_onset else following[2]
            off=start+(end-start)*.8;pre=following[0]
            add(phone+' '+name,off,off+(pre-off)*2/3,pre,pre+(end_c-pre)/2,.015,'vc')
        previous=span
        if i+1<len(spans) and spans[i+1][2] in {'SP','pau'}:
            pre=spans[i+1][0];off=two_thirds(span)
            add(phone+' -',off,off+(pre-off)*.75,pre,pre+.7,.2,'tail')
    for i,row in enumerate(rows):row['source_index']=i
    return rows

def match_existing_template(template,generated,durations,records):
    from vcv_core import apply_oto_template,hiragana,KANA
    from copy import deepcopy
    # Numeric duplicate markers may follow a shared bank suffix, e.g. _NU/_NU1.
    tails=[re.search(r'(_[^_]+)$',r['alias']) for r in template]
    common_suffix=(all(tails) and len({re.sub(r'\d+$','',t.group(1)) for t in tails})==1)
    shadow=[]
    for original,tail in zip(template,tails):
        alias=original['alias'][:tail.start()] if common_suffix else original['alias']
        converted=[]
        for part in hiragana(alias).split():
            if part=='-':converted.append(part);continue
            if part in KANA:part=''.join(KANA[part])
            try:part=''.join(filename_phones(part)[1:-1])
            except ValueError:pass
            converted.append(part)
        shadow.append(dict(original,alias=' '.join(converted)))
    matched=apply_oto_template(shadow,generated,durations,records)
    for original,row in zip(template,matched):row['alias']=original['alias']
    for index,(original,row) in enumerate(zip(template,matched)):
        if not row.get('unmapped_template'):continue
        candidates=[r for r in generated if r['wav'].casefold()==row['wav'].casefold()]
        if not candidates:continue
        # Existing UTAU banks may use kana CV aliases for Korean recordings.
        parts=hiragana(original['alias']).split()
        kind='cv'
        if parts and parts[0]=='-':kind='start'
        elif len(parts)>1:
            second=parts[1].split('_')[0]
            phones=KANA.get(second,[])
            kind='tail' if second=='-' else ('vv' if second in VOWELS or (len(phones)==1 and phones[0] in VOWELS) else 'vc')
        candidates=[r for r in candidates if r['entry_kind']==kind]
        if not candidates:continue
        target=(original['values'][0]+original['values'][3])/1000
        replacement=deepcopy(min(candidates,key=lambda r:abs(r['absolute'][2]-target)))
        replacement.update(wav=original['wav'],alias=original['alias'],preserve_alias=True,
            mapping_warning='기존 에일리어스는 시간 위치·원설 종류로 대응: 청음 검토 필요')
        replacement['warnings'].append(replacement['mapping_warning'])
        matched[index]=replacement
    return matched

class KoreanEngine:
    def __init__(self,review=None,progress=lambda _:None,model_dir=None,language='ko'):
        from vcv_core import ROOT,RESOURCE_ROOT,WORKSPACE
        self.review=review;self.progress=progress;self.language=language
        workspace=WORKSPACE
        self.workspace=workspace
        self.aux_signature='|'.join(str((workspace/name/'last.ckpt').stat().st_mtime_ns) if (workspace/name/'last.ckpt').exists() else 'missing' for name in ['English','Japanese'])
        model_root=workspace/'WFL' if (workspace/'WFL/model.py').exists() else MODEL_ROOT
        from platform_support import backend_command,log_path
        command=backend_command(workspace,RESOURCE_ROOT,model_root,model_dir or model_root/'Archivoice/korean')
        runtime_log=log_path('wfl-runtime.log')
        with runtime_log.open('w',encoding='utf-8') as error_log:
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error_log,
                text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0)
        ready=self.process.stdout.readline()
        if not ready:
            self.process.wait(timeout=5)
            raise RuntimeError('WFL 모델 로드 실패: '+str(runtime_log))
        json.loads(ready)
    def request(self,path,phones=None):
        self.process.stdin.write(json.dumps({'wav':str(path.resolve()),'phones':phones,
            'cache':str((path.parent/('auto-ko_cvvc/logits' if self.language=='ko' else 'auto-wfl-en/logits' if self.language=='en' else 'auto-wfl-ja/logits')/(path.stem+'.npz')).resolve()),
            'aux_routes':{p:{'language':lang,'phone':phone,'fallback':fallback,'path':str(self.workspace/('English' if lang=='en' else 'Japanese'))} for p,(lang,phone,fallback) in AUXILIARY.items()} if self.language=='ko' else {},
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('WFL 프로세스가 종료되었습니다.')
        response=json.loads(line)
        if 'error' in response:raise ValueError(response['error'])
        return response
    def analyze(self,path,cache_dir,mode='ko_cvvc'):
        from vcv_core import atomic_write
        path=Path(path);metadata={}
        if mode!='ko_cvvc':
            from korean_formats import make_record_metadata
            metadata=make_record_metadata(path.stem,mode)
        expected=metadata.get('phones') or filename_phones(path.stem)
        fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
        cache=Path(cache_dir)/(path.stem+'.json')
        if cache.exists():
            record=json.loads(cache.read_text(encoding='utf-8'))
            if record.get('language')=='ko' and record.get('sha256')==fingerprint and (record.get('manually_edited') or (record.get('alignment_version')==ALIGNMENT_VERSION and record.get('aux_signature')==self.aux_signature)) and record.get('phones')==expected:
                record.update(metadata)
                if metadata:atomic_write(cache,json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8'))
                return create_oto(record,mode),record
        unsupported=sorted(set(expected)-(KNOWN|set(AUXILIARY)))
        if unsupported:raise ValueError('모델 미지원 파일명 음소: '+', '.join(unsupported))
        approved=expected
        self.progress('파일명 음소열로 경계 추정: '+path.name)
        final=self.request(path,approved)
        spans=final['intervals'];duration=final['duration']
        # One shared boundary between consecutive confirmed labels; no invented phones.
        boundaries=[0]+[(spans[i-1][1]+spans[i][0])/2 for i in range(1,len(spans))]+[duration]
        if any(b<=a for a,b in zip(boundaries,boundaries[1:])):raise ValueError('최종 정렬 경계가 역전되었습니다.')
        intervals=[[boundaries[i],boundaries[i+1],p] for i,p in enumerate(approved)]
        record={'wav':path.name,'sha256':fingerprint,'phones':approved,'intervals':intervals,
                'duration':duration,'language':'ko','model':'WFL-ASR-korean','alignment_version':ALIGNMENT_VERSION,'aux_signature':self.aux_signature}
        onset_indices=[];position=1
        for part in ([] if metadata else re.split(r"[_' ]+",path.stem.strip('_'))):
            if not part:continue
            chunk=filename_phones(part)[1:-1]
            for offset,phone in enumerate(chunk):
                if phone in VOWELS:break
                if phone in CODAS:onset_indices.append(position+offset)
            position+=len(chunk)
        record['onset_indices']=onset_indices
        record.update(metadata)
        record['label_warnings']=final.get('alignment_warnings',[])
        record['alignment_sources']=final.get('alignment_sources',{})
        cache.parent.mkdir(parents=True,exist_ok=True)
        atomic_write(cache,json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8'))
        return create_oto(record,mode),record
    def close(self):
        if getattr(self,'process',None) and self.process.poll() is None:
            try:self.process.stdin.write('{"close":true}\n');self.process.stdin.flush()
            except (OSError,ValueError):pass
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.terminate()
    def __del__(self):self.close()
