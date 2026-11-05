"""Explicit owner-requested recovery; never a background limit bypass or publisher.
One recovery per failed job/current day, archived originals and separate ledger.
Normal attempt rows/limits remain unchanged. Same shared render and footage budgets.
"""
from pathlib import Path
import datetime as dt,json,sqlite3,hashlib,os,signal,subprocess,sys
from zoneinfo import ZoneInfo
import jobs,full_jobs,render_capacity,media_runtime,footage_budget,quality
BASE=Path(__file__).resolve().parent;DB=BASE/'decisions.sqlite3'
TABLES={'short':'jobs','full':'full_jobs'}
def day():return dt.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def connect():
 if DB.is_symlink():raise ValueError('Unsafe recovery database')
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row
 c.execute('''CREATE TABLE IF NOT EXISTS owner_generation_recoveries(kind TEXT,job TEXT,day TEXT,state TEXT,original_record TEXT,record_hash TEXT,authorization TEXT,authorized_at TEXT,started TEXT,updated TEXT,worker_pid INTEGER,folder TEXT,error TEXT,output_sha256 TEXT,PRIMARY KEY(kind,job))''');c.commit();return c

def alive(pid):
 if not pid:return False
 try:os.kill(int(pid),0);return True
 except ProcessLookupError:return False
 except PermissionError:raise ValueError('Previous worker cannot be verified; recovery was not started')

def authorize(kind,job,authorization):
 if kind not in TABLES:raise ValueError('Choose Short or full recovery')
 if not isinstance(authorization,str) or len(authorization.strip())<20:raise ValueError('Record the explicit owner recovery request')
 today=day();start,end=jobs.attempt_window();table=TABLES[kind]
 with connect() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('select * from '+table+' where id=?',(job,)).fetchone()
  if not row or row['state'] not in ('failed','retry_wait'):raise ValueError('Only an unfinished failed daily job can be recovered')
  if not start<=row['created']<end:raise ValueError('Recovery is limited to today; no silent backlog rendering')
  if alive(row['worker_pid']):raise ValueError('The previous worker is still running')
  if c.execute('select 1 from owner_generation_recoveries where kind=? and job=?',(kind,job)).fetchone():raise ValueError('This job already has an owner recovery record; inspect it instead of retrying')
  # Receipts and uncertain submissions are protected even if a local job row is wrong.
  item_ids=['job-'+job] if kind=='short' else ['long-'+hashlib.sha256((job if n==1 else job+'-attempt-'+str(n)).encode()).hexdigest()[:24] for n in range(1,row['attempts']+1)]
  present={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
  for post_table in ('platform_posts','publications'):
   if post_table not in present:continue
   for item in item_ids:
    for post in c.execute('select state,url from '+post_table+' where item=?',(item,)):
     if post['url'] or post['state'] in ('published','queued','hosting','submitting','uploading','sending','needs_reconciliation','scheduled'):
      raise ValueError('A successful or uncertain publication exists; recovery is blocked')
  # A successful media package is never a recovery candidate.
  source=jobs.ROOT/job/str(row['attempts']) if kind=='short' else full_jobs.ROOT/(job if row['attempts']<=1 else job+'-attempt-'+str(row['attempts']))
  if (source/'POST_THIS.txt').exists():raise ValueError('A completed edition already exists; preserve it')
  next_attempt=row['attempts']+1
  target=jobs.ROOT/job/str(next_attempt) if kind=='short' else full_jobs.ROOT/(job+'-attempt-'+str(next_attempt))
  if target.exists():raise ValueError('Recovery output already exists; no overwrite')
  original=dict(row);now=stamp()
  c.execute('insert into owner_generation_recoveries values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(kind,job,today,'authorized',json.dumps(original),digest(original),authorization,now,None,now,None,str(target),None,None))
 return str(target)

def run_one(kind,job):
 if kind not in TABLES:raise ValueError('Unknown recovery format')
 media_runtime.require_ready()
 with render_capacity.claim() as acquired:
  if not acquired:raise ValueError('Another studio render owns the shared slot; wait')
  if not footage_budget.available():raise ValueError('The existing shared footage allowance needs time to recover')
  table=TABLES[kind]
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');rec=c.execute('select * from owner_generation_recoveries where kind=? and job=?',(kind,job)).fetchone()
   row=c.execute('select * from '+table+' where id=?',(job,)).fetchone()
   if not rec or rec['day']!=day() or rec['state']!='authorized':raise ValueError('No current unused owner authorization')
   if not row or digest(dict(row))!=rec['record_hash'] or alive(row['worker_pid']):raise ValueError('The candidate changed or a previous worker is active')
   folder=Path(rec['folder'])
   if folder.exists() or folder.is_symlink():raise ValueError('Recovery output must be new')
   folder.mkdir(parents=True)
   now=stamp();c.execute("update owner_generation_recoveries set state='running',started=?,updated=? where kind=? and job=?",(now,now,kind,job))
   c.execute('update '+table+" set state='recovering',worker_pid=NULL,retry_at=NULL,updated=CURRENT_TIMESTAMP where id=?",(job,))
  try:
   env={k:v for k,v in media_runtime.environment().items() if not any(x in k for x in ('API_KEY','TOKEN','VOICE_ID'))}
   if kind=='short':
    book=next(b for b in jobs.BOOKS if b['id']==row['book']);args=[str(BASE/'worker.py'),json.dumps(book),str(folder)]
   else:
    args=[str(BASE/'full_jobs.py'),row['book'],str(folder)]
    source=full_jobs.ROOT/(job if row['attempts']<=1 else job+'-attempt-'+str(row['attempts']))
    env['SHELFMADE_FULL_RESUME_FROM']=str(source)
   with (folder/'worker.log').open('x') as log:
    process=subprocess.Popen([sys.executable,str(BASE/'generation_worker.py'),*args],cwd=BASE,stdout=log,stderr=log,env=env,start_new_session=True,pass_fds=render_capacity.inherited_fds())
    with connect() as c:
     c.execute('update owner_generation_recoveries set worker_pid=? where kind=? and job=?',(process.pid,kind,job));c.execute('update '+table+' set worker_pid=? where id=?',(process.pid,job))
    try:code=process.wait(timeout=7200 if kind=='full' else 1200)
    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=20);raise ValueError('Recovery time budget reached')
   if code:raise ValueError('Recovery worker stopped; inspect its preserved log')
   name='final.mp4' if kind=='short' else 'cinematic_LONGFORM.mp4';check=quality.inspect(folder,name,kind=='full')
   if not check['can_approve']:raise ValueError('Completed output failed media or creative validation: '+'; '.join(check['warnings']))
   # Full decode in addition to stream/header and sealed-input checks.
   result=subprocess.run(['ffmpeg','-v','error','-i',str(folder/name),'-f','null','-'],env=media_runtime.environment(),capture_output=True,text=True,timeout=600)
   if result.returncode:raise ValueError('Recovery output failed full media decoding')
   output=hashlib.sha256((folder/name).read_bytes()).hexdigest();now=stamp()
   with connect() as c:
    c.execute('BEGIN IMMEDIATE');current=c.execute('select * from '+table+' where id=?',(job,)).fetchone()
    if current['state']!='recovering' or current['worker_pid']!=process.pid:raise ValueError('Job changed during recovery; validated output preserved without activation')
    c.execute("update owner_generation_recoveries set state='ready',updated=?,worker_pid=NULL,error=NULL,output_sha256=? where kind=? and job=?",(now,output,kind,job))
    c.execute('update '+table+" set state='ready',attempts=?,error=NULL,worker_pid=NULL,retry_at=NULL,updated=CURRENT_TIMESTAMP where id=?",(int(folder.name) if kind=='short' else int(folder.name.rsplit('-attempt-',1)[1]),job))
   print('RECOVERED',kind,row['book'],check['duration'],'seconds',flush=True)
   return {'kind':kind,'job':job,'folder':str(folder),'duration':check['duration'],'sha256':output,'owner_review_required':True}
  except Exception as error:
   now=stamp()
   with connect() as c:
    c.execute("update owner_generation_recoveries set state='failed',updated=?,worker_pid=NULL,error=? where kind=? and job=?",(now,str(error),kind,job))
    c.execute('update '+table+" set state='failed',error=?,worker_pid=NULL,retry_at=NULL,updated=CURRENT_TIMESTAMP where id=?",('Owner-requested recovery stopped; original failure preserved. '+str(error),job))
   raise


def continue_after_repair(kind,job,authorization):
 """At most one explicit technical continuation; preserve the first recovery row.
 This is maintenance-only and never called by the normal background scheduler.
 """
 if kind not in TABLES or not isinstance(authorization,str) or len(authorization)<20:raise ValueError('Explicit owner continuation request required')
 with connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS owner_recovery_continuations(kind TEXT,job TEXT,previous_record TEXT,authorization TEXT,repair_sha256 TEXT,created TEXT,PRIMARY KEY(kind,job))')
  c.commit();c.execute('BEGIN IMMEDIATE')
  rec=c.execute('select * from owner_generation_recoveries where kind=? and job=?',(kind,job)).fetchone()
  row=c.execute('select * from '+TABLES[kind]+' where id=?',(job,)).fetchone()
  if not rec or rec['day']!=day() or rec['state']!='failed' or not row or row['state']!='failed' or alive(row['worker_pid']):raise ValueError('No stopped current-day recovery to continue')
  if c.execute('select 1 from owner_recovery_continuations where kind=? and job=?',(kind,job)).fetchone():raise ValueError('A technical continuation already exists; no further retry')
  old=Path(rec['folder'])
  if (old/'POST_THIS.txt').exists():raise ValueError('Completed media must not be overwritten')
  number=int(old.name) if kind=='short' else int(old.name.rsplit('-attempt-',1)[1]);number+=1
  folder=old.with_name(str(number) if kind=='short' else job+'-attempt-'+str(number))
  if folder.exists():raise ValueError('Continuation output already exists')
  repair=hashlib.sha256((BASE/'voice_frontend.py').read_bytes()).hexdigest();now=stamp()
  c.execute('insert into owner_recovery_continuations values(?,?,?,?,?,?)',(kind,job,json.dumps(dict(rec)),authorization,repair,now))
  c.execute("update owner_generation_recoveries set state='authorized',record_hash=?,authorization=?,started=NULL,updated=?,worker_pid=NULL,folder=?,error=NULL where kind=? and job=?",(digest(dict(row)),authorization,now,str(folder),kind,job))
 return str(folder)
