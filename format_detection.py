"""Recognize a recording list using fingerprints, without shipping source templates."""
from pathlib import Path
import hashlib,json,re,sys
from formats import FORMATS

def fingerprint(text):
    return hashlib.sha256(text.strip().lstrip('_-').encode()).hexdigest()[:24]

def stem_variants(stem):
    yield stem
    yield re.sub(r'(?:[_ -]?[A-G][#b]?[0-9])$','',stem)
    # Bank prefixes/suffixes are often separated from the actual lyrics by '_'.
    parts=stem.split('_')
    for i in range(len(parts)):
        for j in range(i+1,len(parts)+1):yield '_'.join(parts[i:j])

def resolve_mode(folder,mode,template=None):
    if mode=='en_vccv':
        from english_vccv import detect
        return mode,detect(folder,template)
    if mode=='en_cvvc':
        from english_cvvc import detect
        return mode,detect(folder,template)
    if mode=='en_arpasing':
        from arpasing_core import ArpasingResolver
        return mode,ArpasingResolver(folder).summary()
    if not mode.startswith('ko_auto_'):return mode,None
    folder=Path(folder)
    resource=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    signatures=json.loads((resource/'assets/reclist-signatures.json').read_text(encoding='utf-8'))
    kind=FORMATS[mode][2]
    stems=[p.stem for p in folder.glob('*.wav')]
    # A supplied recording list can identify a partial bank as well.
    lists=[]
    for path in folder.glob('*.txt'):
        if not any(t in path.stem.casefold() for t in ['reclist','list','리스트','녹음']):continue
        for encoding in ['utf-8-sig','cp949','shift_jis']:
            try:lists.extend(path.read_text(encoding=encoding).splitlines());break
            except UnicodeError:continue
    observed=[{fingerprint(s) for s in stem_variants(stem)} for stem in stems]
    list_hashes={fingerprint(s) for s in lists if s.strip()}
    aliases={fingerprint(r['alias']) for r in (template or [])}
    ranked=[]
    for profile,data in signatures.items():
        if FORMATS[profile][2]!=kind:continue
        known=set(data['stems']);matches=sum(bool(v&known) for v in observed)
        list_matches=len(list_hashes&known)
        alias_matches=len(aliases&set(data['aliases']))
        # Coverage of the actual bank dominates; list and aliases break ties.
        score=(matches/max(1,len(stems)),list_matches/max(1,len(list_hashes)),
               alias_matches/max(1,len(aliases)),matches/max(1,len(known)))
        ranked.append((score,profile,matches,list_matches,alias_matches))
    ranked.sort(reverse=True)
    score,profile,matches,list_matches,alias_matches=ranked[0]
    reliable=matches>0 or list_matches>0 or alias_matches>0
    tied=len(ranked)>1 and ranked[1][0]==score
    if not reliable:
        # All new Korean profiles share the filename parser and timing rules.
        profile={'cvvc':'ko_cvvc_malcha','cvc':'ko_cvc_zetty','vcv':'ko_vcv_diko'}[kind]
    warning=('녹음 리스트를 확정하지 못해 공통 규칙으로 처리합니다. 경계와 에일리어스를 확인해주세요.'
             if not reliable else ('녹음 리스트 후보가 겹칩니다. 경계와 에일리어스를 확인해주세요.' if tied else ''))
    if reliable and stems and matches/len(stems)<.5:
        warning='일부 파일만 녹음 리스트와 일치합니다. 혼합·변형 리스트인지 확인해주세요.'
    return profile,{'selected_mode':mode,'profile':profile,'matched_files':matches,
                    'files':len(stems),'list_matches':list_matches,'alias_matches':alias_matches,
                    'warning':warning}
