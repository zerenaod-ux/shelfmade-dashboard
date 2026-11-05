"""Never block on iCloud cloud-only (dataless) files: reading them raises OSError instead of hanging."""
import os,builtins,pathlib
_SF=0x40000000
def _bad(p):
    try:
        if isinstance(p,int):return False
        return bool(os.stat(p).st_flags&_SF)
    except Exception:return False
def readable(p):
    """False when the file is a cloud-only iCloud placeholder (reading it would fail)."""
    return not _bad(p)
def _readmode(m):return not any(c in m for c in 'wax+') if m else True
_ro,_rb,_pop,_bop=pathlib.Path.read_text,pathlib.Path.read_bytes,pathlib.Path.open,builtins.open
def _err(p):return OSError(11,'cloud-only file not downloaded (iCloud)',str(p))
def read_text(self,*a,**k):
    if _bad(self):raise _err(self)
    return _ro(self,*a,**k)
def read_bytes(self,*a,**k):
    if _bad(self):raise _err(self)
    return _rb(self,*a,**k)
def popen(self,mode='r',*a,**k):
    if _readmode(mode) and _bad(self):raise _err(self)
    return _pop(self,mode,*a,**k)
def bopen(f,mode='r',*a,**k):
    if _readmode(mode) and _bad(f):raise _err(f)
    return _bop(f,mode,*a,**k)
pathlib.Path.read_text=read_text;pathlib.Path.read_bytes=read_bytes;pathlib.Path.open=popen;builtins.open=bopen
