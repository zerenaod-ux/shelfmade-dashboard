"""Durable background-loop diagnostics. Store safe categories, never exception text."""
from pathlib import Path
import sqlite3,time
BASE=Path(__file__).resolve().parent;DB=BASE/'decisions.sqlite3'
LAST={}
def category(error):
 text=str(error).lower()
 if 'daily' in text and ('limit' in text or 'attempt' in text):return 'attempt_limit'
 if 'locked' in text:return 'database_busy'
 if any(w in text for w in ('footage','pexels')):return 'footage'
 if any(w in text for w in ('source','summary','script','narration')):return 'source'
 return 'worker_error'
def record(worker,error=None):
 now=time.time();code=category(error) if error else None
 if LAST.get(worker)==(code,int(now//20)):return
 with sqlite3.connect(DB,timeout=10) as c:
  c.execute('CREATE TABLE IF NOT EXISTS worker_health(worker TEXT PRIMARY KEY,last_seen REAL NOT NULL,error_code TEXT,error_at REAL)')
  c.execute('INSERT INTO worker_health VALUES (?,?,?,?) ON CONFLICT(worker) DO UPDATE SET last_seen=excluded.last_seen,error_code=excluded.error_code,error_at=excluded.error_at',(worker,now,code,now if code else None))
 LAST[worker]=(code,int(now//20))

def heartbeat(worker):
 now=time.time();key='beat:'+worker
 if LAST.get(key)==int(now//20):return
 with sqlite3.connect(DB,timeout=10) as c:
  c.execute('CREATE TABLE IF NOT EXISTS worker_health(worker TEXT PRIMARY KEY,last_seen REAL NOT NULL,error_code TEXT,error_at REAL)')
  c.execute('INSERT INTO worker_health(worker,last_seen) VALUES (?,?) ON CONFLICT(worker) DO UPDATE SET last_seen=excluded.last_seen',(worker,now))
 LAST[key]=int(now//20)
