"""One nonblocking heavy-render slot across both brands; never consumes attempts while busy."""
from pathlib import Path
from contextlib import contextmanager
from functools import wraps
import fcntl,os,threading
LOCAL=threading.local()
def inherited_fds():
 value=getattr(LOCAL,"fd",None)
 return (value,) if value is not None else ()
BASE=Path(__file__).resolve().parent
LOCK=BASE.parent/'content-empire-studio/state/shared-render.lock'
def path_for(database):
 database=Path(database)
 return LOCK if database.resolve()==(BASE/'decisions.sqlite3').resolve() else database.parent/'shared-render.lock'
@contextmanager
def claim(path=None):
 p=Path(path or LOCK)
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.is_symlink():raise ValueError('Unsafe render lock')
 fd=os.open(p,os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:yield False;return
  previous=getattr(LOCAL,"fd",None);LOCAL.fd=handle.fileno()
  try:yield True
  finally:
   LOCAL.fd=previous;fcntl.flock(handle,fcntl.LOCK_UN)
def guarded(database):
 def decorate(function):
  @wraps(function)
  def invoke(*args,**kwargs):
   with claim(path_for(database())) as acquired:
    if not acquired:return False
    if Path(database()).resolve()==(BASE/'decisions.sqlite3').resolve():
     import footage_budget,media_runtime
     media_runtime.require_ready()
     if not footage_budget.available():return False
    return function(*args,**kwargs)
  return invoke
 return decorate

def worker_deadline(seconds):
 """Child-owned deadline still applies if its dashboard parent disappears."""
 import signal
 def expired(signum,frame):
  if os.getpgrp()==os.getpid():os.killpg(os.getpgrp(),signal.SIGTERM)
  os._exit(124)
 signal.signal(signal.SIGALRM,expired);signal.alarm(seconds)
