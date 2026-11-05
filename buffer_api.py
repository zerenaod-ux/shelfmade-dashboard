"""Buffer API transport. Credentials remain server-side."""
import json,urllib.request,urllib.error,datetime
from pathlib import Path
BASE=Path(__file__).resolve().parent
PRIVATE=BASE/'private-buffer'
class NotSubmittedError(ValueError):
 """The request was rejected locally before any network submission."""
class BudgetError(NotSubmittedError):pass
import sqlite3,time,uuid,threading,contextlib
_ACTIVE=threading.local()

def budget_db():
 PRIVATE.mkdir(mode=0o700,exist_ok=True)
 path=PRIVATE/'request-budget.sqlite3';c=sqlite3.connect(path,timeout=20);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS usage(day TEXT PRIMARY KEY,requests INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS budget_holds(id TEXT PRIMARY KEY,day TEXT,remaining INTEGER,expires REAL)')
 path.chmod(0o600)
 return c

def budget_status():
 day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 with budget_db() as c:
  row=c.execute('SELECT requests FROM usage WHERE day=?',(day,)).fetchone()
  held=c.execute('SELECT COALESCE(SUM(remaining),0) FROM budget_holds WHERE day=? AND expires>?',(day,time.time())).fetchone()[0]
 used=row[0] if row else 0
 return {'used':used,'reserved':held,'limit':90,'available':max(0,90-used-held),'analytics_paused':used+held>=65,'window':'UTC day','refresh_minutes':360}

def reserve_publish(count):
 day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 with budget_db() as c:
  c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM budget_holds WHERE expires<=?',(time.time(),))
  row=c.execute('SELECT requests FROM usage WHERE day=?',(day,)).fetchone();used=row[0] if row else 0
  held=c.execute('SELECT COALESCE(SUM(remaining),0) FROM budget_holds WHERE day=?',(day,)).fetchone()[0]
  if used+held+count>90:raise BudgetError('Publishing paused before submission: not enough API allowance for all selected platforms. Try after the daily reset.')
  id=uuid.uuid4().hex;c.execute('INSERT INTO budget_holds VALUES(?,?,?,?)',(id,day,count,time.time()+1800))
 return id

def release_publish(id):
 if not id:return
 with budget_db() as c:c.execute('DELETE FROM budget_holds WHERE id=?',(id,))

@contextlib.contextmanager
def allocated(id,release=True):
 previous=getattr(_ACTIVE,'reservation',None);_ACTIVE.reservation=id
 try:yield
 finally:
  _ACTIVE.reservation=previous
  if release:release_publish(id)

def reserve_request():
 day=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 with budget_db() as c:
  c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM budget_holds WHERE expires<=?',(time.time(),))
  row=c.execute('SELECT requests FROM usage WHERE day=?',(day,)).fetchone();used=row[0] if row else 0
  id=getattr(_ACTIVE,'reservation',None)
  hold=c.execute('SELECT * FROM budget_holds WHERE id=?',(id,)).fetchone() if id else None
  held=c.execute('SELECT COALESCE(SUM(remaining),0) FROM budget_holds WHERE day=?',(day,)).fetchone()[0]
  if hold and hold['remaining']>0:
   if used>=90:raise BudgetError('Daily publishing allowance reached before submission.')
   c.execute('UPDATE budget_holds SET remaining=remaining-1 WHERE id=?',(id,))
  elif used+held>=65:raise BudgetError('Analytics refresh paused to preserve publishing allowance. Cached statistics remain available.')
  c.execute('INSERT INTO usage VALUES(?,1) ON CONFLICT(day) DO UPDATE SET requests=requests+1',(day,))

def query(document,variables=None):
 try:token=json.loads((PRIVATE/'credentials.json').read_text())['token']
 except (OSError,KeyError,ValueError):raise NotSubmittedError('Connect the Buffer API key first.')
 reserve_request()
 req=urllib.request.Request('https://api.buffer.com',json.dumps({'query':document,'variables':variables or {}}).encode(),{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as response:data=json.load(response)
 except urllib.error.HTTPError as e:
  error=NotSubmittedError if e.code in (400,401,403,404,429) else ValueError
  raise error('Buffer API request failed (HTTP '+str(e.code)+').') from None
 if data.get('errors'):raise ValueError('; '.join(e.get('message','Buffer error') for e in data['errors']))
 return data.get('data',{})
def verify():
 organizations=query('{account {organizations {id}}}')['account']['organizations']
 channels=[]
 for organization in organizations:
  channels.extend(query('{channels(input:{organizationId:'+json.dumps(organization['id'])+'}){id name displayName service isQueuePaused isDisconnected isLocked}}')['channels'])
 temp=PRIVATE/'channels.pending'
 temp.write_text(json.dumps({'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'channels':channels}));temp.chmod(0o600);temp.replace(PRIVATE/'channels.json')
 return channels

def connect(token):
 import os,re
 if not isinstance(token,str) or not re.fullmatch(r'[!-~]{20,512}',token.strip()):raise ValueError('Paste the actual API key, not its masked display.')
 token=token.strip()
 # Validate before replacing the saved credential.
 document='{account {organizations {id}}}'
 reserve_request()
 req=urllib.request.Request('https://api.buffer.com',json.dumps({'query':document}).encode(),{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=60) as response:result=json.load(response)
 except urllib.error.HTTPError as error:raise ValueError('Buffer rejected the key (HTTP '+str(error.code)+').') from None
 if result.get('errors'):raise ValueError('Buffer could not verify this key. Check its account-read permission.')
 if not result.get('data',{}).get('account',{}).get('organizations'):raise ValueError('No Buffer organization found.')
 PRIVATE.mkdir(mode=0o700,exist_ok=True)
 temp=PRIVATE/'credentials.pending'
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as file:json.dump({'token':token},file)
 temp.replace(PRIVATE/'credentials.json')
 return {'verified':True}
