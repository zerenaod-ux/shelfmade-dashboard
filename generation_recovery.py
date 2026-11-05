"""Bounded generation-only retries. No publication functions are imported."""
import json, time, urllib.error, socket

class RecoverableGenerationError(ValueError):
 def __init__(self,message,code):
  if code not in ('footage_shortage','provider_unavailable'):raise ValueError('Unknown recovery reason')
  super().__init__(message);self.code=code

def transient(error):
 if isinstance(error,RecoverableGenerationError):return True
 if isinstance(error, urllib.error.HTTPError):return error.code in (408, 500, 502, 503, 504)
 if isinstance(error, urllib.error.URLError):return isinstance(error.reason,(TimeoutError,ConnectionError,socket.gaierror))
 return isinstance(error,(TimeoutError,ConnectionError))

def migrate(c, table):
 columns={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
 for name, definition in [('retry_count','INTEGER DEFAULT 0'),('retry_at','REAL'),('worker_pid','INTEGER'),('attempts','INTEGER DEFAULT 0')]:
  if name not in columns:c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
 c.commit()

def failure(c, table, row, folder, message, now=None):
 now=time.time() if now is None else now
 try:temporary=json.loads((folder/'failure.json').read_text()).get('temporary') is True
 except (OSError,ValueError):temporary=False
 count=row['retry_count'] or 0
 if temporary and count<2:
  due=now+(60 if count==0 else 300)
  c.execute('UPDATE '+table+" SET state='retry_wait',retry_count=?,retry_at=?,worker_pid=NULL,error=?,updated=CURRENT_TIMESTAMP WHERE id=?",(count+1,due,'Recoverable generation stopped. Completed work is saved; recovery waits for its timer and daily capacity.',row['id']))
 else:
  c.execute('UPDATE '+table+" SET state='failed',retry_at=NULL,worker_pid=NULL,error=?,updated=CURRENT_TIMESTAMP WHERE id=?",(('Automatic retries exhausted. ' if temporary else '')+message,row['id']))

def promote(c,table,capacity,now=None):
 # Caller holds BEGIN IMMEDIATE: timer/capacity checks and queue transition are atomic.
 if capacity<=0:return
 now=time.time() if now is None else now
 rows=c.execute('SELECT id FROM '+table+" WHERE state='retry_wait' AND retry_at<=? ORDER BY retry_at LIMIT ?",(now,capacity)).fetchall()
 for row in rows:c.execute('UPDATE '+table+" SET state='queued',retry_at=NULL,error='Retry queued within daily capacity.' WHERE id=?",(row['id'],))

def interrupted(c,table):
 # A detached child may still render after a dashboard restart. Never start a second copy.
 c.execute('UPDATE '+table+" SET state='failed',retry_at=NULL,error='Interrupted by restart. A previous worker may still be running. Check its log and process before manually retrying.',updated=CURRENT_TIMESTAMP WHERE state='running'")
