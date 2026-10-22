"""Windowless entry point using the same bundled runtime as model inference."""
from pathlib import Path
import os
import runpy
import sys
import traceback

ROOT = Path(__file__).resolve().parent
os.environ['QT_MEDIA_BACKEND'] = 'windows'
if sys.platform == 'win32':
    import ctypes
    set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    set_app_id.argtypes = [ctypes.c_wchar_p]
    set_app_id.restype = ctypes.c_long
    set_app_id('OTONova.Desktop')
sys.dont_write_bytecode = True
with (ROOT / 'wfl-gui.log').open('a', encoding='utf-8', buffering=1) as log:
    sys.stdout = sys.stderr = log
    try:
        runpy.run_path(str(ROOT / 'vcv_gui.py'), run_name='__main__')
    except Exception:
        traceback.print_exc()
        raise
