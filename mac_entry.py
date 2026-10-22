"""Frozen macOS entry point; the same executable also hosts the WFL worker."""
import os
import runpy
import sys
from platform_support import resources

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--wfl-backend':
        for name,fd,mode in [('stdin',0,'r'),('stdout',1,'w'),('stderr',2,'w')]:
            if getattr(sys,name) is None:setattr(sys,name,os.fdopen(fd,mode,encoding='utf-8',closefd=False))
        script=resources()/'tools/wfl_backend.py'
        sys.argv=[str(script)]+sys.argv[2:]
        runpy.run_path(str(script),run_name='__main__')
    else:
        # Static imports let PyInstaller discover the dynamically launched GUI.
        import vcv_gui
        runpy.run_module('app_bootstrap',run_name='__main__')

if __name__=='__main__':main()
