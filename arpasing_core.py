"""Strict ARPAsing input resolution, English WFL alignment and diphone oto rules."""
from pathlib import Path
from functools import lru_cache
from copy import deepcopy
import csv,gzip,hashlib,json,re,sys

PHONES=set('aa ae ah ao aw ax ay b ch d dh dr dx eh en er ey f g hh ih iy jh k l m mlem n ng ow oy p q r rx s sh t th tr uh uw v vf w y z zh'.split())|{'SP','AP','EP'}
VOWELS=set('aa ae ah ao aw ax ay eh en er ey ih iy ow oy uh uw'.split())
PAUSES={'SP','AP','EP'}
COMPOUNDS={'kr':['k','r'],'st':['s','t']}
NON_ARPABET={'ix','rr','aar','aor','ehr','ihr','uhr','x','a','e','o','h','i','j'}
AUDITED_JOINED={'aed','soy','tch','erst','lt','lz','nz','ff','mah','paa','siy','sk','zher','ll'}
VERSION=1

def normalize_name(name):
    text=name.replace('\\','/').strip()
    if text.lower().endswith('.wav'):text=text[:-4]
    return text.casefold()

def read_text(path):
    for encoding in ['utf-8-sig','cp932','cp1252']:
        try:return Path(path).read_bytes().decode(encoding)
        except UnicodeError:continue
    raise ValueError('텍스트 인코딩을 해석할 수 없습니다: '+str(path))

def canonical(token):
    if token.upper() in PAUSES:return token.upper()
    return token.lower()

def split_compact(text):
    """Only concatenate known ARPAbet tokens; never translate other alphabets."""
    alphabet=sorted(PHONES-PAUSES,key=lambda p:(-len(p),p))
    @lru_cache(None)
    def visit(pos):
        if pos==len(text):return ()
        choices=[]
        for phone in alphabet:
            if text.startswith(phone,pos):
                rest=visit(pos+len(phone))
                if rest is not None:choices.append((phone,)+rest)
        return min(choices,key=lambda p:(len(p),p)) if choices else None
    return visit(0)

def parse_sequence(text,compact=False):
    if not re.fullmatch(r'[A-Za-z0-2_\s-]+',text):
        raise ValueError('ARPAsing 이외 기호 또는 스타일 표기: '+text)
    units=[];notes=[]
    for raw in filter(None,re.split(r'[_\s-]+',text.strip('_- '))):
        phone=canonical(raw)
        stress=re.fullmatch(r'([a-z]+)[012]',phone)
        if stress and stress[1] in VOWELS:phone=stress[1]
        if phone in PHONES:units.append({'phone':phone,'model':[phone]});continue
        if phone in COMPOUNDS:
            units.append({'phone':phone,'model':COMPOUNDS[phone]})
            notes.append(phone+' 결합 표기는 '+'+'.join(COMPOUNDS[phone])+'로 정렬')
            continue
        if phone in NON_ARPABET:raise ValueError('다른 음소 체계 또는 미지원 기호: '+raw)
        if not compact and phone not in AUDITED_JOINED:raise ValueError('ARPAsing 미지원 기호: '+raw)
        pieces=split_compact(phone)
        if not pieces:raise ValueError('모델에 없는 ARPAsing 음소: '+raw+' (다른 음소로 대체하지 않음)')
        units.extend({'phone':p,'model':[p]} for p in pieces)
        if not compact:notes.append(raw+' 결합 표기를 '+'+'.join(pieces)+'로 분리: 원본 표기 검토')
    if not units:raise ValueError('확정할 ARPAsing 음소가 없습니다.')
    return units,list(dict.fromkeys(notes))

@lru_cache(None)
def catalog():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    return json.loads(gzip.decompress((root/'assets/arpasing-catalog.json.gz').read_bytes()))

def wav_files(folder):
    root=Path(folder)
    return sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower()=='.wav'
        and not any(s.startswith('auto-') for s in p.relative_to(root).parts[:-1])),key=lambda p:str(p).casefold())

def name_candidates(stem):
    from format_detection import stem_variants
    yield normalize_name(stem)
    base=re.sub(r'(?:[_ -]?[A-G][#b]?[0-9])$','',stem)
    for name in stem_variants(base):
        candidate=normalize_name(name)
        at=normalize_name(base).find(candidate)
        if at<0:continue
        removed=(normalize_name(base)[:at]+'_'+normalize_name(base)[at+len(candidate):]).strip('_- ')
        if any(canonical(p) in PHONES|set(COMPOUNDS)|NON_ARPABET for p in re.split(r'[_ -]+',removed) if p):continue
        yield candidate

class ArpasingResolver:
    def __init__(self,folder):
        self.folder=Path(folder).resolve();self.index_cache={};self.profile_cache={}
        self.files=wav_files(self.folder)
        self.profiles=[]
        for profile in catalog()['profiles']:
            item=dict(profile)
            item['lookup']={normalize_name(k):(k,v) for k,v in profile['entries'].items()}
            self.profiles.append(item)

    def indexes(self,directory):
        directory=Path(directory)
        if directory in self.index_cache:return self.index_cache[directory]
        found={}
        for path in sorted(directory.glob('*.csv')):
            if 'index' not in path.stem.lower():continue
            # Alternate phoneme transcripts are deliberately not read as indices.
            if any(s in path.stem.lower() for s in ['ipa','sampa','vocaloid','vccv']):continue
            text=read_text(path)
            if not text.strip():continue
            first=text.splitlines()[0];delimiter=';' if first.count(';')>first.count(',') else ','
            for row in csv.reader(text.splitlines(),delimiter=delimiter):
                if len(row)<2 or not row[0].strip() or not row[1].strip():continue
                if row[0].strip().lower() in ['filename','file','wav']:continue
                key=normalize_name(row[0]);value=(row[1].strip(),str(path.relative_to(self.folder)))
                if key in found and found[key][0]!=value[0]:
                    found[key]=(None,'중복 인덱스가 서로 다른 음소열을 지정: '+key)
                else:found[key]=value
        self.index_cache[directory]=found
        return found

    def local(self,path):
        directory=path.parent
        while directory.is_relative_to(self.folder):
            index=self.indexes(directory)
            relative=path.relative_to(directory).as_posix()
            exact=[index[k] for k in dict.fromkeys([normalize_name(relative),normalize_name(path.name)]) if k in index]
            if exact:
                if len(set(exact))>1:raise ValueError('인덱스의 경로·파일명 항목이 서로 다릅니다: '+path.name)
                value,source=exact[0]
                if value is None:raise ValueError(source)
                return value,source
            keys=list(dict.fromkeys([normalize_name(relative),*name_candidates(path.stem)]))
            matches={index[k] for k in keys if k in index}
            if len(matches)>1:raise ValueError('접두사/접미사 제거 후 여러 인덱스 항목과 일치: '+path.name)
            if matches:
                value,source=next(iter(matches))
                if value is None:raise ValueError(source)
                return value,source
            if directory==self.folder:break
            directory=directory.parent
        return None

    def ranked_profiles(self,directory):
        if directory not in self.profile_cache:
            names=[set(name_candidates(p.stem)) for p in self.files if p.parent==directory]
            scored=[]
            for profile in self.profiles:
                lookup=set(profile['lookup']);count=sum(bool(lookup&name) for name in names)
                if count:scored.append((count/max(1,len(names)),count/max(1,len(profile['lookup'])),profile))
            scored.sort(key=lambda p:p[:2],reverse=True)
            # A full known bank outranks incidental filename collisions.
            best=scored[0][:2] if scored else None
            self.profile_cache[directory]=[p[2] for p in scored if p[0]==best[0]] if best else []
        return self.profile_cache[directory]

    def metadata(self,path):
        path=Path(path).resolve();relative=path.relative_to(self.folder).as_posix()
        if '_en-lvrpl_' in path.stem.lower():raise ValueError('Liverpool 전용 음소 리스트는 ARPAsing 표준 모드에서 제외됩니다.')
        selected=self.local(path);notes=[];profile_ids=[];compact=False
        if selected:
            sequence,source=selected
            # Only the explicitly documented dx append entries may override d.
            for profile in self.profiles:
                if not profile['overrides'] and not profile['compact']:continue
                candidates=name_candidates(path.stem) if 'dx(ex)' in path.stem.lower() else [normalize_name(path.name)]
                for candidate in candidates:
                    item=profile['lookup'].get(candidate)
                    if item and item[1]==sequence and profile['compact']:
                        compact=True;profile_ids.append(profile['id'])
                    if item and item[1]==sequence and item[0] in profile['overrides']:
                        sequence=profile['overrides'][item[0]]
                        notes.append('등록된 dx 부록: 호환용 index의 d 대신 원본 dx 발음을 사용')
                        profile_ids.append(profile['id']);break
        else:
            if any('vocal fr' in p.lower() for p in path.relative_to(self.folder).parts[:-1]):
                raise ValueError('fry 부록에는 vf 위치가 명시된 ARPAsing index가 필요합니다.')
            # A complete phonetic filename outranks substring matches in another list.
            raw=path.stem.strip('_- ')
            direct=None
            try:
                _,direct_notes=parse_sequence(raw)
                if (any(s in raw for s in ['_','-',' ']) or canonical(raw) in PHONES) and not any('분리:' in n for n in direct_notes):direct=raw
            except ValueError:
                if "'" in raw or any(canonical(p) in NON_ARPABET for p in re.split(r'[_ -]+',raw)):raise
            matches=[]
            for profile in ([] if direct is not None else self.ranked_profiles(path.parent)):
                for candidate in name_candidates(path.stem):
                    if candidate in profile['lookup']:
                        name,value=profile['lookup'][candidate]
                        matches.append((profile['overrides'].get(name,value),profile));break
            sequences={re.sub(r'[_\s-]+','_',p[0].lower()) for p in matches}
            if len(sequences)>1:raise ValueError('숫자·단어 파일명이 여러 리스트와 일치합니다. 해당 음원의 ARPAsing index.csv를 넣어주세요.')
            if direct is not None:sequence=direct;source='filename'
            elif matches:
                sequence,profile=matches[0];source='catalog:'+profile['id'];compact=profile['compact']
                profile_ids=[p['id'] for _,p in matches]
            else:
                source='filename';sequence=path.stem.strip('_- ')
                # Word-based filenames are never guessed through compact splitting.
                if not any(s in sequence for s in ['_','-',' ']) and canonical(sequence) not in PHONES:
                    raise ValueError('단어·번호 파일명의 발음은 추측하지 않습니다. ARPAsing index.csv가 필요합니다: '+path.name)
        units,parse_notes=parse_sequence(sequence,compact)
        # Reject non-phonetic decorations on a raw filename rather than treating a word as a cluster.
        if source=='filename' and any('분리:' in n for n in parse_notes):raise ValueError('파일명 음소 표기가 불명확합니다. ARPAsing index가 필요합니다: '+sequence)
        phones=['SP'];mapped=[]
        for unit in units:
            indices=list(range(len(phones),len(phones)+len(unit['model'])))
            phones.extend(unit['model']);mapped.append(dict(phone=unit['phone'],indices=indices))
        phones.append('SP')
        return dict(wav=relative,phones=phones,arpasing_units=mapped,format='en_arpasing',
            input_source=source,arpasing_profiles=profile_ids,label_warnings=list(dict.fromkeys(notes+parse_notes)))

    def summary(self):
        valid=0;invalid=[];sources=set();profiles=set()
        for path in self.files:
            try:
                data=self.metadata(path);valid+=1;sources.add(data['input_source']);profiles.update(data['arpasing_profiles'])
            except ValueError as exc:invalid.append({'wav':path.relative_to(self.folder).as_posix(),'error':str(exc)})
        return dict(selected_mode='en_arpasing',recognized_files=valid,files=len(self.files),
            profiles=sorted(profiles),sources=sorted(sources),input_failures=invalid,
            warning=(str(len(invalid))+'개 파일의 ARPAsing 표기·인덱스를 확인해주세요.' if invalid else ''))

def create_oto(record):
    from vcv_core import make_entry,two_thirds
    spans=record['intervals'];duration=record['duration'];wav=record['wav'];rows=[]
    units=[]
    for unit in record['arpasing_units']:
        ids=unit['indices'];units.append((spans[ids[0]][0],spans[ids[-1]][1],unit['phone']))
    def add(alias,off,over,pre,cut,lead,kind):
        row=make_entry(wav,alias,off,over,pre,cut-lead,cut,duration,[],fixed_lead=lead,allow_negative_overlap=True)
        row.update(entry_kind=kind,source_index=len(rows));rows.append(row)
    for i,unit in enumerate(units):
        s,e,p=unit
        if p in PAUSES:continue
        if i==0 or units[i-1][2] in PAUSES:
            add('- '+p,s-.3,s,s,s+(e-s)*2/3,.07,'start')
        if i+1<len(units) and units[i+1][2] not in PAUSES:
            right=units[i+1];pre=right[0];q=right[2]
            if p in VOWELS and q in VOWELS:
                off=two_thirds(unit);over=e;cut=two_thirds(right);lead=.04;kind='vv'
            elif q in VOWELS:
                off=s+(e-s)/3;over=(off+pre)/2;cut=two_thirds(right);lead=.07;kind='cv'
            else:
                off=s+(e-s)*.8;over=off+(pre-off)*2/3;cut=right[0]+(right[1]-right[0])/2;lead=.015;kind='vc' if p in VOWELS else 'cc'
            add(p+' '+q,off,over,pre,cut,lead,kind)
        if i+1==len(units) or units[i+1][2] in PAUSES:
            pre=units[i+1][0] if i+1<len(units) else spans[-1][0]
            off=two_thirds(unit)
            if p in VOWELS:fixed=pre+.5;cut=fixed+.2;lead=.2
            else:
                pause_end=units[i+1][1] if i+1<len(units) else spans[-1][1]
                fixed=pre+(pause_end-pre)/3;cut=fixed+.02;lead=.02
            add(p+' -',off,off+(pre-off)*.75,pre,cut,lead,'tail')
    return rows

def match_template(template,generated,durations,records,key_function=None):
    from vcv_core import anchor_markers
    def key(value):return re.sub(r'(?<=[a-z])\d+$','',re.sub(r'\s+',' ',value.strip().lower()))
    if key_function is not None:key=key_function
    durations={normalize_name(k):v for k,v in durations.items()}
    records={normalize_name(k):v for k,v in records.items()}
    grouped={}
    for row in generated:grouped.setdefault(normalize_name(row['wav']),[]).append(row)
    def common(strings):
        import os
        return os.path.commonprefix(strings) if strings else ''
    def score(left,right,entries):
        return sum(any(key(r['alias'][left:len(r['alias'])-right if right else None])==key(c['alias']) for c in grouped.get(normalize_name(r['wav']),[])) for r in entries)
    def offsets(entries):
        aliases=[r['alias'] for r in entries]
        prefix=common(aliases);suffix=common([s[::-1] for s in aliases])[::-1]
        best=(score(0,0,entries),0,0)
        if len(set(aliases))>1:
            for left in range(len(prefix)+1):
                for right in range(len(suffix)+1):
                    count=score(left,right,entries)
                    if count>best[0]:best=(count,left,right)
        return best
    best=offsets(template);original_groups={};per_file={}
    for row in template:original_groups.setdefault(normalize_name(row['wav']),[]).append(row)
    for name,entries in original_groups.items():
        local=offsets(entries);global_count=score(best[1],best[2],entries)
        per_file[name]=local if local[0]>global_count else (global_count,best[1],best[2])
    result=[]
    for original in template:
        name=normalize_name(original['wav']);_,left,right=per_file[name]
        sound=key(original['alias'][left:len(original['alias'])-right if right else None])
        candidates=[r for r in grouped.get(name,[]) if key(r['alias'])==sound]
        if candidates:
            target=(original['values'][0]+original['values'][3])/1000
            row=deepcopy(min(candidates,key=lambda r:abs(r['absolute'][2]-target)))
            row.update(wav=original['wav'],alias=original['alias'],preserve_alias=True)
        else:
            row=deepcopy(original);off,fixed,cut,pre,over=[v/1000 for v in row['values']]
            duration=durations.get(name,max(off,off-cut));end=off-cut if cut<0 else duration-cut
            row.update(source_index=-1,unmapped_template=True,preserve_alias=True,
                absolute=[off,off+over,off+pre,off+fixed,end],warnings=['ARPAsing 별칭 대응 불가: 기존 값 유지'])
            record=records.get(name)
            if record:row['boundary_anchors']=anchor_markers(row['absolute'],record['intervals'])
        result.append(row)
    return result

class EnglishEngine:
    def __init__(self,folder,progress=lambda _:None):
        from vcv_core import WORKSPACE
        self.resolver=ArpasingResolver(folder);self.progress=progress;self.backend=None
        self.oto_factory=create_oto
        model=WORKSPACE/'English';self.signature=str((model/'last.ckpt').stat().st_mtime_ns)
        self.model=model
        self.known={line[2:] for line in (model/'phonemes.txt').read_text(encoding='utf-8').splitlines() if line.startswith('B-')}
    def analyze(self,path,cache_dir,mode='en_arpasing'):
        from vcv_core import atomic_write
        metadata=self.resolver.metadata(path);expected=metadata['phones']
        missing=set(expected)-self.known
        if missing:raise ValueError('영어 모델 미지원 음소: '+', '.join(sorted(missing)))
        fingerprint=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        cache=Path(cache_dir)/Path(metadata['wav']).with_suffix('.json')
        if cache.exists():
            record=json.loads(cache.read_text(encoding='utf-8'))
            if record.get('language')=='en' and record.get('sha256')==fingerprint and record.get('phones')==expected and (record.get('manually_edited') or record.get('model_signature')==self.signature and record.get('alignment_version')==VERSION):
                record.update(metadata);atomic_write(cache,json.dumps(record,ensure_ascii=False,indent=2).encode());return self.oto_factory(record),record
        if self.backend is None:
            from korean_core import KoreanEngine
            self.backend=KoreanEngine(progress=self.progress,model_dir=self.model,language='en')
        self.progress(('영어 VCCV' if mode=='en_vccv' else '영어 CVVC' if mode=='en_cvvc' else 'ARPAsing')+' 확정 음소열로 경계 추정: '+metadata['wav'])
        response=self.backend.request(path,expected);spans=response['intervals'];duration=response['duration']
        if [s[2] for s in spans]!=expected:raise ValueError('확정 음소열과 추정 결과가 다릅니다.')
        boundaries=[0]+[(spans[i-1][1]+spans[i][0])/2 for i in range(1,len(spans))]+[duration]
        if any(b<=a for a,b in zip(boundaries,boundaries[1:])):raise ValueError('영어 추정 경계가 역전되었습니다.')
        record=dict(metadata,sha256=fingerprint,intervals=[[boundaries[i],boundaries[i+1],p] for i,p in enumerate(expected)],
            duration=duration,language='en',model='WFL-ASR-English',model_signature=self.signature,alignment_version=VERSION)
        cache.parent.mkdir(parents=True,exist_ok=True);atomic_write(cache,json.dumps(record,ensure_ascii=False,indent=2).encode())
        return self.oto_factory(record),record
    def close(self):
        if self.backend:self.backend.close()
