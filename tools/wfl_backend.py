"""Local WFL JSON-lines server. Never writes beside the original model or WAV."""
import os,sys,json,contextlib,traceback
from pathlib import Path
root=Path(sys.argv[1]);os.chdir(root);sys.path.insert(0,str(root))
os.environ['HF_HUB_OFFLINE']='1'
os.environ['MPLCONFIGDIR']=str(Path(__file__).resolve().parent/'wfl-matplotlib-cache')
with contextlib.redirect_stdout(sys.stderr):
    import torch,numpy as np,soundfile as sf,yaml
    from scipy.signal import resample_poly
    from math import gcd
    from model import BIOPhonemeTagger
    from infer import constrained_decode
    from utils import decode_bio_tags,forced_align_bio
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    folder=Path(sys.argv[2]) if len(sys.argv)>2 else root/'Archivoice/korean'
    def load_checkpoint(path,weights_only=False):
        import hashlib,io,struct,zlib
        path=Path(path)
        with path.open('rb') as stream:
            magic=stream.read(8)
            if magic==b'WFLZLIB1':
                header=stream.read(40)
                if len(header)!=40:raise ValueError('Truncated compressed checkpoint header')
                size=struct.unpack('<Q',header[:8])[0]
                raw=zlib.decompress(stream.read())
                checksum=hashlib.sha256(raw).digest()
                if len(raw)!=size or checksum!=header[8:]:raise ValueError('Compressed checkpoint checksum mismatch')
                return torch.load(io.BytesIO(raw),map_location='cpu',weights_only=weights_only),checksum.hex()
        with path.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
        return torch.load(path,map_location='cpu',weights_only=weights_only),checksum
    shared_encoders={}
    def shared_encoder(data,folder):
        from transformers import WhisperConfig,WhisperModel
        path=(folder/data['encoder_ref']).resolve()
        if path not in shared_encoders:
            weights,checksum=load_checkpoint(path,weights_only=True)
            if weights.get('format')!='wfl-shared-encoder-v1':raise ValueError('Unknown encoder format')
            encoder=WhisperModel(WhisperConfig.from_pretrained(root/'encoder')).encoder
            encoder.load_state_dict(weights['state_dict'],strict=True)
            shared_encoders[path]=(encoder,weights['state_dict'],checksum)
        encoder,weights,checksum=shared_encoders[path]
        if checksum!=data['encoder_sha256']:raise ValueError('Shared encoder checksum mismatch')
        return encoder,weights
    def load_network(folder):
        config=yaml.safe_load((folder/'config.yaml').read_text(encoding='utf-8'))
        labels=(folder/'phonemes.txt').read_text(encoding='utf-8').splitlines()
        data,_=load_checkpoint(folder/'last.ckpt')
        state=data.get('state_dict',data)
        state={k.removeprefix('model.'):v for k,v in state.items()}
        constructor=BIOPhonemeTagger
        if 'layer_weights' in state:
            import importlib.util
            spec=importlib.util.spec_from_file_location('wfl_weighted_model',Path(__file__).with_name('wfl_weighted_model.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            constructor=module.BIOPhonemeTagger
        if data.get('format')=='wfl-shared-encoder-v1':
            from unittest.mock import patch
            from types import SimpleNamespace
            from transformers import WhisperModel
            encoder,encoder_weights=shared_encoder(data,folder)
            # Both historical model classes use this factory only for their encoder.
            with patch.object(WhisperModel,'from_pretrained',return_value=SimpleNamespace(encoder=encoder)):
                model=constructor(config,labels)
            state.update({'encoder.'+k:v for k,v in encoder_weights.items()})
        else:model=constructor(config,labels)
        if 'layer_weights' in state:
            if any(k.startswith('envelope_head.') for k in state):
                hidden=model.encoder.config.d_model
                model.envelope_head=torch.nn.Sequential(torch.nn.Linear(hidden,hidden//2),torch.nn.GELU(),
                    torch.nn.Linear(hidden//2,config['model'].get('envelope_dim',20)))
        missing,unexpected=model.load_state_dict(state,strict=False)
        critical=[k for k in missing if not k.startswith('envelope_head.')]
        if critical or unexpected:raise RuntimeError(f'Checkpoint mismatch: {critical}, {unexpected}')
        model.eval()
        return model,labels
    model,labels=load_network(folder)
aux_networks={}
aux_scores={}
cache={}
print(json.dumps({'ready':True,'phones':[l[2:] for l in labels if l.startswith('B-')]}),flush=True)
def auxiliary_prediction(path,wav):
    path=str(Path(path).resolve())
    if path not in aux_networks:
        with contextlib.redirect_stdout(sys.stderr):aux_networks[path]=load_network(Path(path))
    network,names=aux_networks[path]
    key=(path,wav)
    if key not in aux_scores:
        audio,sr=sf.read(wav,dtype='float32');audio=audio.mean(axis=1) if audio.ndim>1 else audio
        if sr!=16000:
            factor=gcd(sr,16000);audio=resample_poly(audio,16000//factor,sr//factor)
        audio=audio/(np.max(np.abs(audio))+1e-8)
        scores=[];offsets=[]
        for start in range(0,len(audio),28*16000):
            chunk=audio[start:start+28*16000]
            with torch.inference_mode():out=network(torch.from_numpy(chunk.copy()).unsqueeze(0),torch.tensor([0]))
            frames=max(1,int(np.ceil(len(chunk)/16000/.02)))
            scores.append(out[0][0,:frames].cpu());offsets.append(out[1][0,:frames].cpu())
        # Keep only the current recording's auxiliary logits in memory.
        for old in list(aux_scores):
            if old[1]!=wav:del aux_scores[old]
        aux_scores[key]=(torch.cat(scores),torch.cat(offsets))
    return names,*aux_scores[key]

for line in sys.stdin:
    try:
        request=json.loads(line)
        if request.get('close'):break
        wav=request['wav']
        disk=Path(request['cache']) if request.get('cache') else None
        key=request.get('sha256','')+str((folder/'last.ckpt').stat().st_mtime_ns)
        if wav not in cache and disk and disk.exists():
            with np.load(disk,allow_pickle=False) as saved:
                if str(saved['key'])==key:
                    cache.clear();cache[wav]=(torch.from_numpy(saved['logits'].copy()),torch.from_numpy(saved['offsets'].copy()),float(saved['duration']))
        if wav not in cache:
            audio,sr=sf.read(wav,dtype='float32');audio=audio.mean(axis=1) if audio.ndim>1 else audio
            duration=len(audio)/sr
            if sr!=16000:
                factor=gcd(sr,16000);audio=resample_poly(audio,16000//factor,sr//factor)
            audio=audio/(np.max(np.abs(audio))+1e-8)
            logits_list=[];offset_list=[]
            for start in range(0,len(audio),28*16000):
                chunk=audio[start:start+28*16000]
                with torch.inference_mode():
                    output=model(torch.from_numpy(chunk.copy()).unsqueeze(0),torch.tensor([0]))
                    logits,offsets=output[:2]
                frames=max(1,int(np.ceil(len(chunk)/16000/.02)))
                logits_list.append(logits[0,:frames].cpu());offset_list.append(offsets[0,:frames].cpu())
            cache.clear();cache[wav]=(torch.cat(logits_list),torch.cat(offset_list),duration)
            if disk:
                disk.parent.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(disk,key=key,logits=cache[wav][0].numpy(),offsets=cache[wav][1].numpy(),duration=duration)
        logits,offsets,duration=cache[wav]
        phones=request.get('phones')
        warnings=[];sources={};offset_choices={}
        id2label=model.id2label
        decode_logits=logits
        if phones:
            extra=sorted(set(phones)-{p[2:] for p in labels if p.startswith('B-')})
            if extra:
                columns=[torch.log_softmax(logits,dim=-1)];combined=list(labels)
                for phone in extra:
                    route=request.get('aux_routes',{}).get(phone)
                    if not route:raise ValueError('모델 미지원 음소: '+phone)
                    try:
                        names,other,other_offsets=auxiliary_prediction(route['path'],wav)
                        if len(other)!=len(logits):raise ValueError('보조 모델 프레임 수 불일치')
                        bi=[names.index('B-'+route['phone']),names.index('I-'+route['phone'])]
                        columns.append(torch.log_softmax(other,dim=-1)[:,bi])
                        offset_choices[phone]=other_offsets
                        sources[phone]=route['language']+'/'+route['phone']
                    except Exception as exc:
                        fallback=route['fallback'];bi=[labels.index('B-'+fallback),labels.index('I-'+fallback)]
                        columns.append(torch.log_softmax(logits,dim=-1)[:,bi])
                        warnings.append(phone+' 보조 모델 사용 불가: 한국어 '+fallback+'로 대체 ('+str(exc)+')')
                        sources[phone]='ko/'+fallback+' (fallback)'
                    combined.extend(['B-'+phone,'I-'+phone])
                decode_logits=torch.cat(columns,dim=-1);id2label=dict(enumerate(combined))
            tags=forced_align_bio(decode_logits,id2label,phones,allow_end_in_last_phone=False)
        else:tags=constrained_decode(logits,model.id2label)
        selected_offsets=offsets.clone()
        for t,tag in enumerate(tags):
            if tag[2:] in offset_choices:selected_offsets[t]=offset_choices[tag[2:]][t]
        segments=decode_bio_tags(tags,.02,selected_offsets)
        segments=[[max(0,float(s)),min(duration,float(e)),p] for s,e,p in segments if s<duration and e>s]
        if phones and [r[2] for r in segments]!=phones:
            raise ValueError('확정 음소열 전체를 정렬하지 못했습니다. 음소열을 검토해주세요.')
        print(json.dumps({'intervals':segments,'duration':duration,'alignment_warnings':warnings,'alignment_sources':sources}),flush=True)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({'error':str(exc)}),flush=True)
