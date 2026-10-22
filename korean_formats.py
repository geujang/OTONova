"""Parse reclist spellings without changing alias spellings to model symbols."""
import re

VOWELS={'a','i','u','e','o','eu','eo','er','@r'}
CODA={'n':'N','m':'M','ng':'NG','l':'L','k':'K','t':'T','p':'P'}
TOKENS=sorted(set(['gg','dd','bb','kk','tt','pp','jj','ss','ch','th','dh','ts','rr','ng',
                  'NG','N','M','L','K','T','P','H','R','br','vf','cl','axh','exh','mlem','sh',
                  'eo','eu','ae','oe','ui','eui','er','@r','l']+list('aiueogndrm bsjktphfvzwy'.replace(' ',''))),key=len,reverse=True)

def transcribe(stem,mode):
    from korean_core import PHONE_SUBSTITUTIONS,legacy_filename_phones
    text=stem
    if text in ['R','息']:
        return ['SP','AP','SP'],['SP',text,'SP'],['pause','breath','pause']
    both_style=re.search(r'\((vf|cl)\)$',text)
    both=both_style[1] if both_style else None
    if both:text=text[:both_style.start()]
    fry_start=text.endswith('_~E');fry_end=text.endswith('_E~')
    if fry_start or fry_end:text=text.rsplit('_',1)[0]
    if text.endswith('(H)'):text='_'.join(p+'H' for p in text[:-3].split('_') if p)
    text=text.replace('Long','').replace('+',"'")
    if re.fullmatch(r'(?:br|breath)\d*',text,re.I):
        return ['SP','AP','SP'],['SP',text,'SP'],['pause','breath','pause']
    # A separately written '-' or '_' mora in Malcha lists is an actual rest.
    text=text.replace("'_'",'|').replace('-', '|')
    pieces=re.split(r"[_'\s]+",text.strip('_'))
    raw=[]
    for chunk,piece in enumerate(pieces):
        if not piece:continue
        if piece in ['|','-']:
            raw.append(('SP',chunk));continue
        if re.fullmatch(r'br\d*',piece):
            raw.append((piece,chunk));continue
        if fry_start or both:raw.append((both or 'vf',chunk))
        for part_index,part in enumerate(piece.split('|')):
            if part_index:raw.append(('SP',chunk))
            if not part:
                raw.append(('SP',chunk));continue
            if any('가'<=c<='힣' for c in part):
                raw.extend((p,chunk) for p in legacy_filename_phones(part)[1:-1]);continue
            pos=0
            while pos<len(part):
                symbol=next((p for p in TOKENS if part.startswith(p,pos) and
                             not (p in ['ae','oe'] and mode!='ko_cv') and
                             not (p=='er' and pos>0 and pos+2<len(part) and part[pos+2] in 'aiueoyw' and part[pos-1] not in 'aiueo')),None)
                if symbol is None:raise ValueError('지원하지 않는 녹음 리스트 표기: '+part[pos:])
                pos+=len(symbol)
                expansions={'eui':['eu','i'],'ui':['eu','i'],'oe':['w','e'],'ae':['e']}
                raw.extend((p,chunk) for p in expansions.get(symbol,[symbol]))
        if fry_end or both:raw.append((both or 'vf',chunk))
    model=['SP'];source=['SP'];roles=['pause']
    for i,(phone,chunk) in enumerate(raw):
        if phone=='SP':
            if model[-1]!='SP':model.append('SP');source.append('SP');roles.append('pause')
            continue
        next_phone,next_chunk=raw[i+1] if i+1<len(raw) else ('',-1)
        previous=raw[i-1][0] if i else ''
        coda=(phone in {'K','T','P','N','M','NG','L'} or
              (phone in CODA and (previous in VOWELS or next_phone in ['H','R']) and (next_chunk!=chunk or next_phone not in VOWELS|{'y','w'})))
        role='vowel' if phone in VOWELS else ('coda' if coda else 'onset')
        if phone=='i' and previous=='eu' and i and raw[i-1][1]==chunk:role='vowel_continuation'
        mapped=CODA.get(phone,phone) if coda else {'gg':'kk','dd':'tt','bb':'pp'}.get(phone,phone)
        if phone=='ng':mapped='NG'
        mapped=PHONE_SUBSTITUTIONS.get(mapped,mapped)
        if phone.startswith('br') or phone=='R':mapped='AP';role='breath'
        if phone in ['H','axh','exh']:role='breath'
        if phone in ['vf','cl']:role='fry'
        model.append(mapped);source.append(phone);roles.append(role)
    if model[-1]!='SP':model.append('SP');source.append('SP');roles.append('pause')
    return model,source,roles

def make_record_metadata(stem,mode):
    phones,source,roles=transcribe(stem,mode)
    return {'phones':phones,'source_phones':source,'phone_roles':roles,
            'onset_indices':[i for i,r in enumerate(roles) if r=='onset'],
            'format':mode}


def create_oto(record,mode):
    from formats import FORMATS
    from vcv_core import make_entry,two_thirds
    kind=FORMATS[mode][2]
    spans=record['intervals'];duration=record['duration'];wav=record['wav']
    source=record['source_phones'];roles=record['phone_roles'];rows=[]
    cvc=kind=='cvc';vcv=kind=='vcv';single=kind=='cv'
    def spelling(value):
        if 'diko' in mode:value=value.replace('eui','ui')
        return value
    def add(alias,offset,overlap,pre,cut,lead,entry_kind,indices=(),notes=()):
        row=make_entry(wav,spelling(alias),offset,overlap,pre,cut-lead,cut,duration,list(notes),
                       fixed_lead=lead,allow_negative_overlap=True)
        row.update(entry_kind=entry_kind,phone_indices=list(indices))
        rows.append(row)
    def vc(left,right,end,alias,entry_kind='vc'):
        a,b,_=spans[left];pre=spans[right][0];off=a+(b-a)*.8
        add(alias,off,off+(pre-off)*2/3,pre,pre+(end-pre)/2,.015,entry_kind,[left,right])
    previous=None
    for i,role in enumerate(roles):
        if role in ['pause','breath']:previous=None;continue
        if role!='vowel':continue
        end_i=i
        while end_i+1<len(roles) and roles[end_i+1]=='vowel_continuation':end_i+=1
        j=i
        while j>0 and roles[j-1]=='onset':j-=1
        cv=''.join(source[j:end_i+1]);vowel=''.join(source[i:end_i+1])
        start=spans[i][0];end=two_thirds(spans[end_i]);begin=spans[j][0]
        before=roles[j-1] if j else 'pause'
        initial=before in ['pause','breath','fry'] or j<=1
        if 'tabi' in mode and j<i and source[j] in ['n','m','r','l','h','j','s','ss','th']:
            consonant=''.join(source[j:i]);cut=begin+(start-begin)*2/3
            add('- '+consonant,begin-.3,begin,begin,cut,.07,'start_consonant',range(j,i))
            if consonant[-1:] not in ['y','w'] and spans[i][2] in ['i','u','o']:
                suffix='y' if spans[i][2]=='i' else 'w'
                add('- '+consonant+suffix,begin-.3,begin,begin,cut,.07,'start_consonant',range(j,i))
                if mode.endswith('old') and suffix=='y' and consonant in ['s','ss']:
                    add('- '+consonant+'h',begin-.3,begin,begin,cut,.07,'start_consonant',range(j,i))
        if single:
            add(cv,begin-.3,begin,start,end,.07,'cv',range(j,end_i+1))
        elif vcv:
            if initial:add('- '+cv,begin-.3,begin,start,end,.04,'start',range(j,end_i+1))
            else:
                left=j-1
                add(source[left].lower()+' '+cv,two_thirds(spans[left]),spans[left][1],start,end,.04,
                    'vcv',range(left,end_i+1))
        else:
            if initial:add('- '+cv,begin-.3,begin,start,end,.07,'start',range(j,end_i+1))
            off=begin+(start-begin)/3
            add(cv,off,(off+start)/2,start,end,.07,'cv',range(j,end_i+1))
            rows[-1]['initial']=initial
            cluster=''.join(source[j:i])
            if cluster in ['kss','pss']:
                off_c=begin+(start-begin)*2/3
                fixed=start+(spans[i][1]-start)/3
                add(cluster,off_c,(off_c+start)/2,start,fixed+.02,.02,'consonant',range(j,i))
            if j>0 and roles[j-1]=='coda' and (j==i or all(p in ['y','w'] for p in source[j:i])):
                c=source[j-1].lower();left=spans[j-1][0];off=left+(start-left)/3
                add(c+cv,off,(off+start)/2,start,end,.07,'cv',range(j-1,end_i+1))
            if cvc and j<i and source[j]=='r' and j>0 and roles[j-1]=='coda' and spans[j-1][2]=='L':
                add('l'+''.join(source[j+1:end_i+1]),off,(off+start)/2,start,end,.07,'cv',range(j,end_i+1))
            if previous is not None and j==i and roles[i-1] in ['vowel','vowel_continuation']:
                add(source[i-1]+' '+cv,two_thirds(spans[i-1]),spans[i-1][1],start,end,.04,'vv',[i-1,i])
            elif previous is not None and j<i and all(p in ['y','w'] for p in source[j:i]) and roles[j-1] in ['vowel','vowel_continuation']:
                add(source[j-1]+' '+cv,two_thirds(spans[j-1]),spans[j-1][1],start,end,.04,'vv',range(j-1,end_i+1))
        if end_i+1<len(spans) and roles[end_i+1] in ['onset','coda']:
            right=end_i+1;k=right+1
            if roles[right]=='onset':
                while k<len(spans) and roles[k]=='onset':k+=1
            consonant=''.join(source[right:k])
            if roles[right]=='coda':
                alias=vowel+consonant.lower() if cvc or single else vowel+' '+consonant.lower()
                vc(end_i,right,spans[k-1][1],alias,'coda')
                # Uppercase batchim aliases used by Tabi distinguish them from onsets.
                if 'tabi' in mode:vc(end_i,right,spans[k-1][1],vowel+' '+consonant,'coda')
                if cvc:vc(end_i,right,spans[k-1][1],vowel+' '+consonant.lower(),'vc')
            elif not vcv and not single:
                vc(end_i,right,spans[k-1][1],vowel+' '+consonant)
                final={'g':'k','gg':'k','kk':'k','k':'k','d':'t','dd':'t','tt':'t','t':'t',
                       'b':'p','bb':'p','pp':'p','p':'p','n':'n','m':'m','ng':'ng','l':'l'}.get(consonant)
                if cvc and final:vc(end_i,right,spans[k-1][1],vowel+final,'coda')
        if end_i+1<len(spans) and roles[end_i+1] in ['pause','breath'] and not single:
            right=end_i+1;pre=spans[right][0];off=two_thirds(spans[end_i])
            alias=vowel+(' R' if roles[right]=='breath' else ' -')
            add(alias,off,off+(pre-off)*.75,pre,min(duration,pre+.7),.2,'tail',[end_i,right])
        previous=end_i
    # Coda -> onset connections, present in CVC and Tabi CVVC lists.
    for i in range(1,len(spans)-1):
        if roles[i]=='coda' and roles[i+1]=='onset' and not single and not vcv:
            k=i+2
            while k<len(spans) and roles[k]=='onset':k+=1
            vc(i,i+1,spans[k-1][1],source[i].lower()+' '+''.join(source[i+1:k]),'cc')
            if 'tabi' in mode:vc(i,i+1,spans[k-1][1],source[i]+' '+''.join(source[i+1:k]),'cc')
        if roles[i]=='breath' and (source[i].startswith('br') or not any(r=='vowel' for r in roles)):
            s,e,_=spans[i]
            add(source[i],s,s,s,e,.04,'breath',[i])
        if roles[i]=='coda' and roles[i+1]=='breath':
            vc(i,i+1,spans[i+1][1],source[i].lower()+' R','tail')
            vc(i,i+1,spans[i+1][1],source[i].lower()+' h','tail')
        if roles[i]=='coda' and roles[i+1]=='pause':
            pre=spans[i+1][0];off=two_thirds(spans[i])
            add(source[i].lower()+' -',off,off+(pre-off)*.75,pre,min(duration,pre+.7),.2,'tail',[i,i+1])
        if roles[i]=='fry':
            if i+1<len(spans) and roles[i+1] in ['onset','vowel','coda']:
                j=i+1
                while j<len(spans) and roles[j]=='onset':j+=1
                if j<len(spans) and roles[j] in ['vowel','coda']:
                    pre=spans[j][0];off=spans[i][0]+(pre-spans[i][0])/3
                    add("' "+''.join(source[i+1:j+1]),off,(off+pre)/2,pre,two_thirds(spans[j]),.07,'cv',range(i,j+1))
            elif roles[i-1] in ['vowel','vowel_continuation','coda']:vc(i-1,i,spans[i][1],source[i-1]+" '",'vc')
    if not any(r=='vowel' for r in roles):
        for i,role in enumerate(roles):
            if role not in ['onset','coda']:continue
            following=next((s for s,r in reversed(list(zip(spans,roles))) if r=='pause'),[duration,duration,'SP'])
            pre=following[0];off=two_thirds(spans[i]);fixed=following[0]+(following[1]-following[0])/3
            add(source[i],off,(off+pre)/2,pre,fixed+.02,.02,'consonant',[i])
    # A recording's final pause can also supply its aspirated-release alias.
    for row in list(rows):
        if row['alias'].endswith(' -'):
            from copy import deepcopy
            released=deepcopy(row);released['alias']=row['alias'][:-2]+' R';rows.append(released)
        if row['alias'].endswith(' R'):
            from copy import deepcopy
            released=deepcopy(row);released['alias']=row['alias'][:-2]+' h';rows.append(released)
        if row['entry_kind']=='cv' and not row['alias'].startswith(("'",'-')) and not single:
            indices=row['phone_indices']
            if indices:
                first=indices[0];v=next((i for i in indices if roles[i]=='vowel'),None)
                if v is not None:
                    add('- '+row['alias'],spans[first][0]-.3,spans[first][0],spans[v][0],row['absolute'][4],.07,'start',indices)
        if 'tabi' in mode and row['entry_kind'] in ['vc','cc']:
            indices=row['phone_indices'];right=indices[-1] if indices else -1
            k=right+1
            while k<len(spans) and roles[k]=='onset':k+=1
            if k<len(spans) and spans[k][2] in ['i','u','o'] and not row['alias'].endswith(('y','w')):
                from copy import deepcopy
                variant=deepcopy(row);variant['alias']+=('y' if spans[k][2]=='i' else 'w');rows.append(variant)
            if mode.endswith('tabi_old') and row['alias'].endswith(('y','w')):
                from copy import deepcopy
                variant=deepcopy(row);variant['alias']=variant['alias'][:-1];rows.append(variant)
        if mode=='ko_cvvc_malcha' and row['entry_kind']=='vc':
            left,_,right=row['alias'].partition(' ')
            if right in ['kk','tt','pp']:
                from copy import deepcopy
                variant=deepcopy(row);variant['alias']=left+' '+right[0]+'cl';rows.append(variant)
        if 'tabi' in mode and row['alias'].startswith("' "):
            from copy import deepcopy
            variant=deepcopy(row);variant['alias']='*'+row['alias'][2:];rows.append(variant)
            variant=deepcopy(row);variant['alias']=row['alias'].replace(' ','');rows.append(variant)
        if 'tabi' in mode and row['alias'].endswith(" '"):
            from copy import deepcopy
            variant=deepcopy(row);variant['alias']=row['alias'][:-1]+'*';rows.append(variant)
    # Repeated initial CVs in CVC lists reserve the connected occurrence for CV.
    connected={r['alias'] for r in rows if r['entry_kind']=='cv' and r.get('initial') is False}
    rows=[r for r in rows if not (r.get('initial') and r['alias'] in connected)]
    if cvc:
        from copy import deepcopy
        existing={r['alias'] for r in rows}
        for row in list(rows):
            vowel=row['alias']
            if row['entry_kind']=='cv' and vowel in VOWELS and vowel+' '+vowel not in existing:
                variant=deepcopy(row);variant['alias']=vowel+' '+vowel;variant['entry_kind']='vv'
                variant['warnings'].append('동일 모음 VV: 녹음된 지속 모음의 CV 구간 사용')
                rows.append(variant);existing.add(variant['alias'])
    if single and len(record['wav'].removesuffix('.wav'))==1:
        from pathlib import Path
        name=Path(record['wav']).stem
        if '가'<=name<='힣' and (ord(name)-0xac00)%28==0:
            from copy import deepcopy
            for row in list(rows):
                if row['entry_kind']=='cv':
                    variant=deepcopy(row);variant['alias']=name;rows.append(variant)
    for i,row in enumerate(rows):row['source_index']=i
    return rows


def match_template(template,generated,durations,records,mode):
    """Preserve the template exactly; make ambiguous derived aliases reviewable."""
    from copy import deepcopy
    from vcv_core import apply_oto_template,make_entry,two_thirds
    shadow=[dict(r,alias=re.sub(r'\([^)]*\)','',r['alias'])) for r in template]
    matched=apply_oto_template(shadow,generated,durations,records)
    by_wav={}
    for row in generated:by_wav.setdefault(row['wav'].casefold(),[]).append(row)
    for original,row in zip(template,matched):
        row['alias']=original['alias']
        if not row.get('unmapped_template'):continue
        record=records.get(row['wav'].casefold())
        if not record:continue
        candidates=by_wav.get(row['wav'].casefold(),[])
        sound=original['alias'].strip()
        if row.get('alias_prefix') and sound.startswith(row['alias_prefix']):sound=sound[len(row['alias_prefix']):]
        if row.get('alias_suffix') and sound.endswith(row['alias_suffix']):sound=sound[:-len(row['alias_suffix'])]
        parts=sound.split()
        replacement=None;note=None
        # Long vowels / self-VV aliases use the sustained vowel that is recorded.
        if len(parts)==2 and parts[0]==parts[1] and parts[0] in VOWELS:
            options=[r for r in candidates if r['alias']==parts[0] and r['entry_kind']=='cv']
            if options:
                replacement=deepcopy(options[0]);note='동일 모음 VV: 녹음된 지속 모음의 CV 구간 사용'
        elif len(parts)==2 and parts[0]=='-':
            phoneme=parts[1]
            for i,(a,b,p) in enumerate(record['intervals']):
                source=record['source_phones'][i]
                if record['phone_roles'][i]=='onset' and (source==phoneme or source==phoneme.rstrip('yw')):
                    cut=two_thirds(record['intervals'][i])
                    replacement=make_entry(record['wav'],sound,a-.3,a,a,cut-.07,cut,record['duration'],[],fixed_lead=.07,allow_negative_overlap=True)
                    replacement.update(entry_kind='start_consonant',phone_indices=[i],source_index=-3)
                    note='어두 자음: 시작음 규칙을 자음 구간에 적용';break
        if replacement is None:
            # Some supplied oto aliases intentionally reuse another vowel/transition.
            # Keep the nearest compatible kind, with an explicit phonetic mismatch warning.
            target_kind=('vcv' if len(parts)==2 and FORM_KIND(mode)=='vcv' else
                         ('vv' if len(parts)==2 and parts[0] in VOWELS and parts[1] in VOWELS else
                          ('coda' if len(parts)==1 and parts[0][-1:] in 'kmnptl' else None)))
            if target_kind:
                options=[r for r in candidates if r['entry_kind']==target_kind and
                         (r['alias'].split()[-1]==parts[-1] if len(parts)==2 else r['alias'].endswith(parts[0][-1:]))]
                if options:
                    pre=(original['values'][0]+original['values'][3])/1000
                    replacement=deepcopy(min(options,key=lambda r:abs(r['absolute'][2]-pre)))
                    note='원본 별칭과 파일명 음소열 차이: '+replacement['alias']+' 구간 사용, 청음 확인 필요'
        if replacement is None and candidates:
            if sound.endswith((' -',' R',' h')):kind='tail'
            elif len(parts)>1 and parts[0]=='-':kind='start'
            elif len(parts)>1 and parts[0] not in VOWELS:kind='cc'
            elif len(parts)>1:kind='vcv' if FORM_KIND(mode)=='vcv' else 'vc'
            else:kind='cv'
            options=[r for r in candidates if r['entry_kind']==kind]
            if not options:options=candidates
            pre=(original['values'][0]+original['values'][3])/1000
            replacement=deepcopy(min(options,key=lambda r:abs(r['absolute'][2]-pre)))
            note='별칭의 정확한 음소 대응 없음: '+replacement['alias']+' 시간에서 시작, 원설 직접 확인 필요'
        if replacement is not None:
            # Store a recipe so a boundary drag recomputes this row without losing its alias.
            replacement.update(wav=original['wav'],alias=original['alias'],preserve_alias=True,
                               mapping_warning=note,derived_profile=True,
                               template_alias=sound)
            replacement['warnings'].append(note)
            row.clear();row.update(replacement)
    return matched


def FORM_KIND(mode):
    from formats import FORMATS
    return FORMATS[mode][2]
