"""Persistent display features with a bounded shared memory cache."""
from pathlib import Path
from collections import OrderedDict
import hashlib,threading
import numpy as np
import soundfile as sf

_memory=OrderedDict();_guard=threading.RLock();_locks={};_bytes=0
MAX_BYTES=192*1024*1024
CACHE_VERSION=1

def key(path,expected_signature=None):
    path=Path(path).resolve()
    if expected_signature is None:
        s=path.stat();expected_signature=[s.st_size,s.st_mtime_ns]
    return hashlib.sha256(f'{CACHE_VERSION}|{path}|{expected_signature[0]}|{expected_signature[1]}'.encode()).hexdigest()

def peek(path,expected_signature=None):
    k=key(path,expected_signature)
    with _guard:
        value=_memory.get(k)
        if value is not None:_memory.move_to_end(k)
        return value

def get(path,cache_folder=None,expected_signature=None):
    global _bytes
    path=Path(path).resolve();k=key(path,expected_signature)
    with _guard:lock=_locks.setdefault(k,threading.Lock())
    with lock:
        ready=peek(path,expected_signature)
        if ready is not None:return ready
        cache=Path(cache_folder or path.parent/'.otonova-cache')/(k+'.npz')
        value=None
        try:
            with np.load(cache,allow_pickle=False) as data:
                value={name:data[name] for name in data.files}
                assert {'samples','sample_rate','levels','high_hz','energy_times','energy_db'}<=value.keys()
        except (OSError,ValueError,AssertionError,EOFError):pass
        if value is None:
            if expected_signature is not None and key(path)!=k:raise ValueError('WAV 변경 감지: 다시 로드를 승인해야 합니다.')
            from audio_view import spectrum_levels,rms_energy
            audio,sr=sf.read(path,always_2d=True,dtype='float32');audio=audio.mean(axis=1)
            if not len(audio):raise ValueError('Empty audio file')
            levels,hz,_=spectrum_levels(audio,sr);times,energy=rms_energy(audio,sr)
            value=dict(samples=audio,sample_rate=np.array(sr),levels=levels,high_hz=np.array(hz),energy_times=times,energy_db=energy)
            # A file changed during rendering must not be stored under the old signature.
            if key(path)!=k:raise ValueError('WAV changed while preparing display data')
            try:
                cache.parent.mkdir(parents=True,exist_ok=True)
                temp=cache.with_suffix('.tmp')
                with temp.open('wb') as stream:np.savez_compressed(stream,**value)
                temp.replace(cache)
            except OSError:pass # Read-only banks can still be rendered in memory.
        size=sum(v.nbytes for v in value.values())
        with _guard:
            while _memory and _bytes+size>MAX_BYTES:
                _,old=_memory.popitem(last=False);_bytes-=sum(v.nbytes for v in old.values())
            if size<=MAX_BYTES:_memory[k]=value;_bytes+=size
        return value
