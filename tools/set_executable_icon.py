"""Replace a Windows executable icon without changing its program code."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct

def replace_icon(executable, icon):
    raw=Path(icon).read_bytes()
    reserved,kind,count=struct.unpack_from('<HHH',raw)
    if reserved or kind!=1 or not count:raise ValueError('Invalid ICO')
    entries=[]
    for i in range(count):
        width,height,colors,zero,planes,bits,length,offset=struct.unpack_from('<BBBBHHII',raw,6+16*i)
        image=raw[offset:offset+length]
        if len(image)!=length:raise ValueError('Truncated ICO')
        entries.append((struct.pack('<BBBBHHIH',width,height,colors,zero,planes,bits,length,i+1),image))
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.BeginUpdateResourceW.argtypes=[wintypes.LPCWSTR,wintypes.BOOL];api.BeginUpdateResourceW.restype=wintypes.HANDLE
    api.UpdateResourceW.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,wintypes.WORD,ctypes.c_void_p,wintypes.DWORD];api.UpdateResourceW.restype=wintypes.BOOL
    api.EndUpdateResourceW.argtypes=[wintypes.HANDLE,wintypes.BOOL];api.EndUpdateResourceW.restype=wintypes.BOOL
    handle=api.BeginUpdateResourceW(str(Path(executable).resolve()),False)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        for i,(_,data) in enumerate(entries,1):
            if not api.UpdateResourceW(handle,3,i,0,ctypes.create_string_buffer(data),len(data)):raise ctypes.WinError(ctypes.get_last_error())
        group=struct.pack('<HHH',0,1,count)+b''.join(e[0] for e in entries)
        if not api.UpdateResourceW(handle,14,1,0,ctypes.create_string_buffer(group),len(group)):raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        api.EndUpdateResourceW(handle,True);raise
    if not api.EndUpdateResourceW(handle,False):raise ctypes.WinError(ctypes.get_last_error())

if __name__=='__main__':
    import sys
    replace_icon(sys.argv[1],sys.argv[2])
