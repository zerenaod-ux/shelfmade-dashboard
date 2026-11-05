"""Shared media-tool health and app-local dependency environment. No downloads."""
from pathlib import Path
import os,subprocess,time,threading,json,hashlib
BASE=Path(__file__).resolve().parent
LIB=BASE/'runtime/video/lib';RECEIPT=LIB.parent/'repair-receipt.json'
CACHE=None;CHECKED=0;LOCK=threading.Lock()
class MediaRuntimeError(ValueError):pass

def environment():
 env=os.environ.copy();library=LIB/'libx265.216.dylib'
 if library.is_file():
  if LIB.is_symlink() or library.is_symlink() or RECEIPT.is_symlink():raise MediaRuntimeError('Video tools need repair: unsafe local dependency path.')
  try:expected=json.loads(RECEIPT.read_text())['sha256']
  except (OSError,ValueError,KeyError):raise MediaRuntimeError('Video tools need repair: local dependency receipt missing.') from None
  if hashlib.sha256(library.read_bytes()).hexdigest()!=expected:raise MediaRuntimeError('Video tools need repair: local dependency changed.')
  env['DYLD_LIBRARY_PATH']=os.pathsep.join(dict.fromkeys([str(LIB)]+[p for p in env.get('DYLD_LIBRARY_PATH','').split(os.pathsep) if p]))
 return env

def health(force=False):
 global CACHE,CHECKED
 with LOCK:
  if not force and CACHE and time.monotonic()-CHECKED<30:return dict(CACHE)
  try:
   env=environment()
   for tool in ('ffmpeg','ffprobe'):
    r=subprocess.run([tool,'-version'],env=env,capture_output=True,text=True,timeout=10)
    if r.returncode:raise MediaRuntimeError('Video tools need repair: '+tool+' cannot start. No new video should be approved or downloaded until repaired.')
   result={'ready':True,'message':'Video tools checked. Open each draft for its own media and review checks.'}
  except (OSError,subprocess.SubprocessError,MediaRuntimeError) as error:
   result={'ready':False,'message':str(error) if isinstance(error,MediaRuntimeError) else 'Video tools need repair: FFmpeg/FFprobe are unavailable. Draft generation is paused before footage downloads.'}
  CACHE=result;CHECKED=time.monotonic();return dict(result)

def require_ready():
 status=health()
 if not status['ready']:raise MediaRuntimeError(status['message'])

def enable():
 """Apply only inside this application process, inherited by its workers."""
 try:env=environment()
 except MediaRuntimeError:return False
 if 'DYLD_LIBRARY_PATH' in env:os.environ['DYLD_LIBRARY_PATH']=env['DYLD_LIBRARY_PATH']
 return True
