import render_capacity
"""Free, durable full-video visual drafts from the existing local book summaries.
Source summaries are editorial inputs, not newly verified book quotations.
No paid legacy generator is imported. Nothing publishes automatically.
"""
import json,sqlite3,uuid,subprocess,sys,os,signal
from jobs import attempt_window
import worker_health
import generation_recovery
from pathlib import Path
BASE=Path(__file__).resolve().parent;DB=BASE/'decisions.sqlite3';ROOT=BASE/'full-generated'
DAILY_ATTEMPT_LIMIT=2 # One initial render plus one bounded recovery attempt (per full video).
def per_day():
 """Full videos allowed today: 1 normally, more after the owner clicks 'Make N more full videos' (that choice lasts for that Chicago day only)."""
 try:
  import datetime
  from zoneinfo import ZoneInfo
  x=json.loads((BASE/'cinematic-settings.json').read_text()).get('full_extra') or {}
  return 1+max(0,min(int(x.get('n',0)),6)) if x.get('day')==datetime.datetime.now(ZoneInfo('America/Chicago')).date().isoformat() else 1
 except Exception:return 1
def attempt_limit():return DAILY_ATTEMPT_LIMIT*per_day()
SUMMARY=Path.home()/'Documents'/'ContentEmpire-Studio'/'PRODUCTS'/'ebook_content.json'
def connect():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS full_jobs(id TEXT PRIMARY KEY,book TEXT NOT NULL,state TEXT NOT NULL,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP)')
 if 'version' not in {r[1] for r in c.execute('PRAGMA table_info(full_jobs)')}:c.execute("ALTER TABLE full_jobs ADD COLUMN version TEXT DEFAULT 'legacy'");c.commit()
 generation_recovery.migrate(c,'full_jobs')
 c.execute('CREATE TABLE IF NOT EXISTS full_generation_attempts(job TEXT,started TEXT DEFAULT CURRENT_TIMESTAMP)');c.commit();return c

def script_for(book):
 import cinematic_content,visual_admission
 script=cinematic_content.build(book)
 visual_admission.require(script)
 return script

def list_jobs():
 with connect() as c:
  rows=[dict(r) for r in c.execute('SELECT * FROM full_jobs ORDER BY created DESC')]
  present={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  recoveries={r['job']:r['folder'] for r in c.execute("SELECT job,folder FROM owner_generation_recoveries WHERE kind='full' AND state='running'")} if 'owner_generation_recoveries' in present else {}
 for row in rows:
  folder=ROOT/(row['id'] if (row['attempts'] or 0)<=1 else row['id']+'-attempt-'+str(row['attempts']))
  if row['state']=='recovering' and row['id'] in recoveries:
   active=Path(recoveries[row['id']])
   if not active.is_symlink() and active.resolve().parent==ROOT.resolve() and active.name.startswith(row['id']+'-attempt-'):folder=active
  try:row['progress']=json.loads((folder/'production-progress.json').read_text())
  except (OSError,ValueError):row['progress']=None
 return rows

def enqueue(book):
 import local_voice
 if not local_voice.available():raise ValueError('Restore Kokoro Heart before generating.')
 script=script_for(book)
 if sum(len(s['narration'].split()) for s in script['sections'])<100:raise ValueError('The local summary is too short for a full-video draft.')
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  existing=c.execute("SELECT * FROM full_jobs WHERE book=? AND version='cinematic-default-v1' AND state IN ('queued','running','ready','retry_wait') ORDER BY created DESC LIMIT 1",(book,)).fetchone()
  if existing:return dict(existing)
  if (c.execute('SELECT count(*) FROM full_generation_attempts WHERE started>=? AND started<?',attempt_window()).fetchone()[0]>=attempt_limit() or c.execute('SELECT count(*) FROM full_jobs WHERE created>=? AND created<?',attempt_window()).fetchone()[0]>=per_day()):raise ValueError('Full-video limit for this America/Chicago day reached. Use Make more full videos or retry tomorrow.')
  id=uuid.uuid4().hex;c.execute("INSERT INTO full_jobs(id,book,state,version) VALUES (?,?,'queued','cinematic-default-v1')",(id,book));return dict(c.execute('SELECT * FROM full_jobs WHERE id=?',(id,)).fetchone())

def retry(id):
 """Owner-initiated recovery of one failed job. Never resets attempt history."""
 import local_voice,datetime
 from zoneinfo import ZoneInfo
 if not local_voice.available():raise ValueError('Restore Kokoro Heart before retrying.')
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT * FROM full_jobs WHERE id=?',(id,)).fetchone()
  if not row or row['state']!='failed' or row['version']!='cinematic-default-v1':raise ValueError('Only a failed cinematic full-video job can be retried.')
  if row['worker_pid']:
   try:os.kill(row['worker_pid'],0)
   except ProcessLookupError:pass
   except PermissionError:raise ValueError('Previous worker cannot be verified. Inspect it before retrying.')
   else:raise ValueError('The previous worker may still be running. Wait before retrying.')
  start,end=attempt_window()
  day=datetime.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
  if 'full_daily_generation' in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
   slot=c.execute('SELECT book FROM full_daily_generation WHERE day=?',(day,)).fetchone()
   if slot and slot[0]!=row['book']:raise ValueError('Today already has a different full-video reservation. Inspect it before retrying.')
  if c.execute("SELECT 1 FROM full_jobs WHERE state IN ('queued','running','retry_wait')").fetchone():raise ValueError('Another full-video job is active. Wait for it to finish.')
  if per_day()<=1 and c.execute("SELECT 1 FROM full_jobs WHERE created>=? AND created<? AND id!=?",(start,end,id)).fetchone():raise ValueError('Today already has a different full-video job. Keep one book per Chicago day.')
  if completed_today(c,start,end):raise ValueError('Today’s full-video goal is already complete.')
  used=attempts_today(c,start,end)
  if used>=attempt_limit():raise ValueError('Both full-video attempts were used today. Retry after midnight America/Chicago; history remains preserved.')
  script_for(row['book']) # Source/creative validation before reserving another render.
  c.execute("UPDATE full_jobs SET state='queued',error=NULL,retry_at=NULL,worker_pid=NULL,updated=CURRENT_TIMESTAMP WHERE id=?",(id,))
  c.execute('CREATE TABLE IF NOT EXISTS full_daily_generation(day TEXT PRIMARY KEY,book TEXT NOT NULL)')
  c.execute('INSERT OR REPLACE INTO full_daily_generation VALUES (?,?)',(datetime.datetime.now(ZoneInfo('America/Chicago')).date().isoformat(),row['book']))
  return dict(c.execute('SELECT * FROM full_jobs WHERE id=?',(id,)).fetchone())

def attempts_today(c,start,end):
 return max(c.execute('SELECT count(*) FROM full_generation_attempts WHERE started>=? AND started<?',(start,end)).fetchone()[0],c.execute('SELECT count(*) FROM full_jobs WHERE created>=? AND created<?',(start,end)).fetchone()[0])
def completed_today(c,start,end):
 return c.execute("SELECT count(*) FROM full_jobs j WHERE j.state='ready' AND ((j.created>=? AND j.created<?) OR EXISTS(SELECT 1 FROM full_generation_attempts a WHERE a.job=j.id AND a.started>=? AND a.started<?))",(start,end,start,end)).fetchone()[0]>=per_day()

def recover():
 with connect() as c:generation_recovery.interrupted(c,'full_jobs')

@render_capacity.guarded(lambda: DB)
def work_once():
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  used=max(c.execute('SELECT count(*) FROM full_generation_attempts WHERE started>=? AND started<?',attempt_window()).fetchone()[0],c.execute('SELECT count(*) FROM full_jobs WHERE created>=? AND created<?',attempt_window()).fetchone()[0])
  queued=c.execute("SELECT count(*) FROM full_jobs WHERE state='queued'").fetchone()[0]
  if used>=attempt_limit() or completed_today(c,*attempt_window()):return False
  generation_recovery.promote(c,'full_jobs',attempt_limit()-used-queued)
  row=c.execute("SELECT * FROM full_jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
  if not row:return False
  from zoneinfo import ZoneInfo
  import datetime
  day=datetime.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
  c.execute('CREATE TABLE IF NOT EXISTS full_daily_generation(day TEXT PRIMARY KEY,book TEXT NOT NULL)')
  reservation=c.execute('SELECT book FROM full_daily_generation WHERE day=?',(day,)).fetchone()
  if reservation and reservation[0]!=row['book'] and per_day()<=1:return False
  c.execute('INSERT OR IGNORE INTO full_daily_generation VALUES (?,?)',(day,row['book']))
  c.execute('INSERT INTO full_generation_attempts(job) VALUES (?)',(row['id'],))
  c.execute("UPDATE full_jobs SET state='running',attempts=attempts+1,updated=CURRENT_TIMESTAMP WHERE id=?",(row['id'],))
 folder=ROOT/(row['id'] if not row['attempts'] else row['id']+'-attempt-'+str(row['attempts']+1));folder.mkdir(parents=True,exist_ok=True)
 try:
  env={k:v for k,v in os.environ.items() if not any(x in k for x in ('API_KEY','TOKEN','VOICE_ID'))}
  env.pop('SHELFMADE_FULL_RESUME_FROM',None)
  if row['attempts']:
   previous=ROOT/(row['id'] if row['attempts']==1 else row['id']+'-attempt-'+str(row['attempts']))
   if previous.is_dir():env['SHELFMADE_FULL_RESUME_FROM']=str(previous.resolve())
  with (folder/'worker.log').open('w') as log:
   proc=subprocess.Popen([sys.executable,str(BASE/'generation_worker.py'),str(Path(__file__).resolve()),row['book'],str(folder)],env=env,stdout=log,stderr=log,start_new_session=True,pass_fds=render_capacity.inherited_fds())
   with connect() as c:c.execute('UPDATE full_jobs SET worker_pid=? WHERE id=?',(proc.pid,row['id']))
   try:code=proc.wait(timeout=7200)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise RuntimeError('Rendering exceeded two hours.')
   if code:
    lines=(folder/'worker.log').read_text(errors='replace').splitlines();detail=next((line.split('ValueError:',1)[1].strip() for line in reversed(lines) if 'ValueError:' in line),'Inspect the local worker log.')
    raise RuntimeError('Full-video build stopped: '+detail[:400])
  with connect() as c:c.execute("UPDATE full_jobs SET state='ready',error=NULL,worker_pid=NULL,updated=CURRENT_TIMESTAMP WHERE id=?",(row['id'],))
 except Exception as e:
  with connect() as c:generation_recovery.failure(c,'full_jobs',row,folder,str(e))
 return True

if __name__=='__main__':
 import cinematic_pipeline
 cinematic_pipeline.build(sys.argv[1],Path(sys.argv[2]))

def start():
 import threading,time
 recover()
 def loop():
  while True:
   try:worker_health.heartbeat('full')
   except Exception:pass
   try:
    queue_daily();worker_health.record('full')
   except Exception as error:
    try:worker_health.record('full',error)
    except Exception:pass
   try:
    if not work_once():time.sleep(30)
   except Exception as error:
    try:worker_health.record('full',error)
    except Exception:pass
    time.sleep(5)
 threading.Thread(target=loop,daemon=True).start()


def queue_daily(now=None):
 import datetime
 from zoneinfo import ZoneInfo
 import cinematic_pipeline,cinematic_content
 config=cinematic_pipeline.settings()
 local=(now or datetime.datetime.now(ZoneInfo('America/Chicago'))).astimezone(ZoneInfo('America/Chicago'))
 if not config.get('daily_generation') or local.hour<config['daily_hour_chicago']:return
 with connect() as c:
  if c.execute("SELECT 1 FROM full_jobs WHERE (created>=? AND created<?) OR state IN ('queued','running','retry_wait')",attempt_window(local)).fetchone():return
  c.execute('CREATE TABLE IF NOT EXISTS full_daily_generation(day TEXT PRIMARY KEY,book TEXT NOT NULL)')
  reservation=c.execute('SELECT book FROM full_daily_generation WHERE day=?',(local.date().isoformat(),)).fetchone()
  if reservation:
   # A prior-day job can cross midnight, fail, and reserve today's slot in
   # work_once(). Recover that failed reservation within today's bounded
   # attempt allowance instead of treating the failed reservation as success.
   failed=c.execute("SELECT id FROM full_jobs WHERE book=? AND version='cinematic-default-v1' AND state='failed' ORDER BY updated DESC LIMIT 1",(reservation['book'],)).fetchone()
   if failed and attempts_today(c,*attempt_window(local))<attempt_limit():
    failed_id=failed['id']
   else:return
  else:failed_id=None
  if failed_id is None:
   used={r[0] for r in c.execute('SELECT book FROM full_jobs')}
 if failed_id is not None:
  return retry(failed_id)
 # Existing full-video packages are also excluded; automatic work never remakes an old book.
 studio=Path(os.environ.get('SHELFMADE_STUDIO',str(Path.home()/'Documents'/'ContentEmpire-Studio')))
 used.update(p.name.split('_')[0] for p in (studio/'LONGFORM').glob('*') if p.is_dir())
 for folder in ROOT.glob('*'):
  try:used.add(json.loads((folder/'package.json').read_text())['book'])
  except (OSError,ValueError,KeyError):pass
 for book in json.loads((BASE/'books.json').read_text()):
  if book['id'] in used:continue
  try:script_for(book['id'])
  except ValueError:continue
  result=enqueue(book['id'])
  with connect() as c:c.execute('INSERT OR IGNORE INTO full_daily_generation VALUES (?,?)',(local.date().isoformat(),book['id']))
  return result


def make_extra(n):
 """Owner's 'Make N more full videos' click: allow N more today and queue them now. They build one after another."""
 import datetime
 from zoneinfo import ZoneInfo
 n=max(1,min(int(n),6));day=datetime.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
 cfg_path=BASE/'cinematic-settings.json';cfg=json.loads(cfg_path.read_text());cfg['full_extra']={'day':day,'n':n}
 tmp=cfg_path.with_suffix('.tmp');tmp.write_text(json.dumps(cfg,indent=2));os.replace(tmp,cfg_path)
 with connect() as c:used={r[0] for r in c.execute('SELECT book FROM full_jobs')}
 studio=Path(os.environ.get('SHELFMADE_STUDIO',str(Path.home()/'Documents'/'ContentEmpire-Studio')))
 try:used.update(p.name.split('_')[0] for p in (studio/'LONGFORM').glob('*') if p.is_dir())
 except OSError:pass
 queued=0;note=''
 for book in json.loads((BASE/'books.json').read_text()):
  if queued>=n:break
  if book['id'] in used:continue
  try:script_for(book['id'])
  except ValueError:continue
  try:enqueue(book['id']);queued+=1
  except Exception as e:note=str(e)[:160];break
 if queued<n and not note:note='Only '+str(queued)+' books are eligible right now (no unused book has enough matching material).'
 return {'requested':n,'queued':queued,'note':note}
