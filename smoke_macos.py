"""Real model loading/alignment smoke test for source and frozen Mac builds."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile
import numpy as np
import soundfile as sf
from platform_support import resources,backend_command,workspace

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--app',type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary);wav=folder/'smoke.wav'
        audio=np.zeros(16000,dtype=np.float32);audio[1600:14400]=.1*np.sin(np.arange(12800)*2*np.pi*220/16000)
        sf.write(wav,audio,16000)
        for language,relative,phone in [('en','English','aa'),('ja','Japanese','a'),('ko','WFL/Archivoice/korean','a')]:
            base=workspace();resource=resources()
            if args.app:
                # Bundle data lives in Resources (PyInstaller links Frameworks data to it).
                base=args.app/'Contents/Resources';resource=base
                command=[str(args.app/'Contents/MacOS/OTONova'),'--wfl-backend',str(base/'WFL'),str(base/relative)]
            else:command=backend_command(base,resource,base/'WFL',base/relative)
            request=json.dumps({'wav':str(wav),'phones':['SP',phone,'SP']})+'\n'+json.dumps({'close':True})+'\n'
            result=subprocess.run(command,input=request,text=True,encoding='utf-8',capture_output=True,timeout=180)
            if result.returncode:raise RuntimeError(language+': '+result.stderr[-8000:])
            lines=[json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            assert lines[0].get('ready'),lines
            response=lines[1]
            assert 'error' not in response,response
            assert [r[2] for r in response['intervals']]==['SP',phone,'SP'],response
            assert all(0<=r[0]<r[1]<=1.01 for r in response['intervals']),response
            print(language+': model load and constrained alignment passed',flush=True)
if __name__=='__main__':main()
