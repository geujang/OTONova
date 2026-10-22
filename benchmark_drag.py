"""Measure actual GUI updates/repaints using a temporary copy of the supplied voicebank."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import sys
import time
import math
from pathlib import Path
import numpy as np
from test_gui import EditorTests,APP

case=EditorTests('test_zoom_preserved_between_aliases_of_same_wav')
case.setUp()
try:
    window=case.window
    wave=window.wave
    original=window.current_record['intervals'][2][0]
    timings=[]
    window.begin_edit()
    for i in range(150):
        start=time.perf_counter()
        window.edit_boundary(2,original+.03*math.sin(i*.2))
        wave.repaint()
        APP.processEvents()
        timings.append((time.perf_counter()-start)*1000)
    result={'iterations':len(timings),'mean_ms':float(np.mean(timings)),
            'median_ms':float(np.median(timings)),'p95_ms':float(np.percentile(timings,95))}
    print(json.dumps(result,indent=2))
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result,indent=2),encoding='utf-8')
finally:
    case.tearDown()
