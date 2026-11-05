"""One saved daily review slate. Automatic preparation never uploads content."""
import production_boost
import datetime,json,sqlite3,re,csv,hashlib
from pathlib import Path
from zoneinfo import ZoneInfo
import jobs
BASE=Path(__file__).resolve().parent;DB=BASE/'decisions.sqlite3'
TRACKER=Path.home()/'Documents'/'ContentEmpire-Studio'/'POSTING_TRACKER.csv'
normalize=lambda text:re.sub('[^a-z0-9]','',text.lower().replace(' · new local draft',''))
def history():
 if not TRACKER.exists():return {}
 try:
  with TRACKER.open() as f:
   return {normalize(r.get('video','')):r['url'] for r in csv.DictReader(f) if r.get('platform')=='youtube' and r.get('url')}
 except (OSError,csv.Error):return {}
import threading,time
_LOCK=threading.RLock()
def connection():
 for n in range(6):
  try:
   c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
   c.execute('CREATE TABLE IF NOT EXISTS daily_slates(day TEXT PRIMARY KEY,items TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP)');return c
  except sqlite3.OperationalError:
   if n==5:raise
   time.sleep(0.3*(n+1))
def today(now=None):return (now or datetime.datetime.now(ZoneInfo('America/Chicago'))).astimezone(ZoneInfo('America/Chicago')).date().isoformat()
def _retry(fn,*a,**k):
 last=None
 for n in range(8):
  try:
   with _LOCK:return fn(*a,**k)
  except sqlite3.OperationalError as e:
   last=e;time.sleep(0.4*(n+1))
 raise last
def prepare(items,posts,now=None):
 return _retry(_prepare,items,posts,now)
def _prepare(items,posts,now=None):
 day=today(now);previous=history();uploaded={p['item'] for p in posts if p.get('url') or p['state'] in ('uploading','needs_reconciliation')}
 eligible=[i for i in items if i.get('content_type')!='full' and not i.get('published_everywhere') and i['id'] not in uploaded and (i.get('generated') or normalize(i['title']) not in previous) and i['status']!='rejected' and i['ready'] and i['quality']['can_approve']]
 # New locally generated drafts first, followed by existing eligible backlog.
 eligible.sort(key=lambda i:(not i.get('generated',False),i['title']))
 with connection() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT items FROM daily_slates WHERE day=?',(day,)).fetchone()
  ids=json.loads(row['items']) if row else []
  ids=[id for id in ids if any(i['id']==id for i in eligible)]
  replacements=[i['id'] for i in eligible if i.get('replacement') and i['status']=='review']
  ids=list(dict.fromkeys(replacements+ids))[:production_boost.shorts_target()]
  for i in eligible:
   if len(ids)>=production_boost.shorts_target():break
   if i['id'] not in ids:ids.append(i['id'])
  c.execute('INSERT INTO daily_slates(day,items) VALUES (?,?) ON CONFLICT(day) DO UPDATE SET items=excluded.items',(day,json.dumps(ids)))
 return {'day':day,'timezone':'America/Chicago','ids':ids,'target':production_boost.shorts_target(),'ready':len(ids),'automatic_publish':False,'generation':short_progress(day)}
def short_slots(c):
 c.execute('CREATE TABLE IF NOT EXISTS short_daily_slots(day TEXT NOT NULL,slot INTEGER NOT NULL,book TEXT NOT NULL,job TEXT,PRIMARY KEY(day,slot),UNIQUE(day,book))')
 # Preserve the existing one-per-day reservation during the upgrade.
 c.execute('CREATE TABLE IF NOT EXISTS daily_generation(day TEXT PRIMARY KEY,book TEXT NOT NULL)')
 for row in c.execute('SELECT day,book FROM daily_generation').fetchall():
  c.execute('INSERT OR IGNORE INTO short_daily_slots(day,slot,book) VALUES (?,1,?)',(row['day'],row['book']))

def short_progress(day):
 all_jobs=jobs.list_jobs();by_id={j['id']:j for j in all_jobs};by_book={}
 for job in all_jobs:by_book.setdefault(job['book'],job)
 with connection() as c:
  short_slots(c)
  slots=[dict(r) for r in c.execute('SELECT slot,book,job FROM short_daily_slots WHERE day=? ORDER BY slot',(day,))]
 for slot in slots:
  job=by_id.get(slot.get('job')) or by_book.get(slot['book'],{});slot.update(state=job.get('state','reserved'),job=job.get('id'),error=job.get('error'),edition=job.get('edition',1))
 return {'target':production_boost.shorts_target(),'reserved':len(slots),'ready':sum(s['state']=='ready' for s in slots),'slots':slots}

def has_next_edition(job):
 if job.get('state')!='ready':return False
 try:
  metadata=json.loads((jobs.package(job)/'edition.json').read_text())
  return int(metadata.get('edition_capacity',job.get('edition',1)+1))>int(job.get('edition',1))
 except (OSError,ValueError,TypeError,KeyError):
  # Legacy packages predate passage-aware manifests. Allow one new edition;
  # its verified package then reports the actual remaining passage supply.
  return True

def queue_fresh(items,posts,now=None):
 # Three distinct fresh Shorts per Chicago day. Full-video reservations are separate.
 local=(now or datetime.datetime.now(ZoneInfo('America/Chicago'))).astimezone(ZoneInfo('America/Chicago'))
 day=today(local)
 if local.hour<9:return
 previous=history()
 full_ids={i['id'] for i in items if i.get('content_type')=='full'}
 posted={normalize(p['title']) for p in posts if p.get('url') and p['item'] not in full_ids and not p['item'].startswith('long-')}
 results=[]
 for _ in range(production_boost.shorts_target()):
  known=jobs.list_jobs();used={j['book'] for j in known}
  latest={}
  for j in known:latest.setdefault(j['book'],j)
  with connection() as c:
   short_slots(c);c.commit();c.execute('BEGIN IMMEDIATE')
   slots=c.execute('SELECT slot,book,job FROM short_daily_slots WHERE day=?',(day,)).fetchall()
   known_ids={j['id'] for j in known}
   orphan=next((r for r in slots if (r['job'] and r['job'] not in known_ids) or (not r['job'] and r['book'] not in used)),None)
   failed_retry=next((r for r in slots if r['job'] in {j['id'] for j in known if jobs.pre_source_retryable(j) or jobs.pipeline_fix_retryable(j)}),None)
   if len(slots)>=production_boost.shorts_target() and not orphan and not failed_retry:return results
   used.update(r['book'] for r in c.execute('SELECT book FROM short_daily_slots'))
   fresh=next((b for b in jobs.BOOKS if b['id'] not in used and normalize(b['title']) not in previous and normalize(b['title']) not in posted),None)
   reusable=next((b for b in jobs.BOOKS if b['id'] in latest and has_next_edition(latest[b['id']]) and b['id'] not in {r['book'] for r in slots}),None)
   book=next((b for b in jobs.BOOKS if b['id']==failed_retry['book']),None) if failed_retry else (next((b for b in jobs.BOOKS if b['id']==orphan['book']),None) if orphan else (fresh or reusable))
   if not book:return results
   slot=failed_retry['slot'] if failed_retry else (orphan['slot'] if orphan else next(n for n in range(1,9) if n not in {r['slot'] for r in slots}))
   if not orphan and not failed_retry:c.execute('INSERT INTO short_daily_slots(day,slot,book) VALUES (?,?,?)',(day,slot,book['id']))
   c.commit()
  try:job=jobs.enqueue(book['id'],retry=True) if failed_retry else jobs.enqueue(book['id'])
  except Exception:
   with connection() as c:c.execute('DELETE FROM short_daily_slots WHERE day=? AND slot=? AND job IS NULL',(day,slot))
   raise
  with connection() as c:c.execute('UPDATE short_daily_slots SET job=? WHERE day=? AND slot=?',(job['id'],day,slot))
  results.append(job)
 return results

def full_pick(*a,**k):
 return _retry(_full_pick,*a,**k)
def _full_pick(items,posts,now=None):
 """One stable review selection per day; never auto-approves or publishes."""
 day=today(now)
 eligible=[i for i in items if i.get('content_type')=='full' and 300<=float(i['quality']['duration'] or 0)<=480 and i['ready'] and i['status']!='rejected' and i['quality']['can_approve'] and not any(p['item']==i['id'] and (p.get('url') or p['state'] in ('uploading','needs_reconciliation')) for p in posts)]
 eligible.sort(key=lambda i:(not 300<=float(i['quality']['duration'] or 0)<=480,i['title']))
 with connection() as c:
  c.execute('CREATE TABLE IF NOT EXISTS full_daily_slates(day TEXT PRIMARY KEY,item TEXT)')
  row=c.execute('SELECT item FROM full_daily_slates WHERE day=?',(day,)).fetchone()
  # Prefer the completed draft reserved for this Chicago day over an untouched
  # backlog selection. Owner approvals and all publishing preparations stay pinned.
  saved=row['item'] if row else None
  selected=next((i for i in items if i['id']==saved),None)
  protected=bool(saved and (any(p['item']==saved for p in posts) or (selected and selected['status']=='approved')))
  fresh=None
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if {'full_jobs','full_daily_generation'}<=tables:
   columns={r[1] for r in c.execute('PRAGMA table_info(full_jobs)')}
   if 'attempts' in columns:
    rows=c.execute("SELECT j.id,j.attempts FROM full_jobs j JOIN full_daily_generation d ON d.book=j.book WHERE d.day=? AND j.state='ready' ORDER BY j.updated DESC",(day,)).fetchall()
    for job in rows:
     folder=job['id'] if (job['attempts'] or 0)<=1 else job['id']+'-attempt-'+str(job['attempts'])
     candidate='long-'+hashlib.sha256(folder.encode()).hexdigest()[:24]
     if any(i['id']==candidate and i.get('ready') and i.get('status')!='rejected' and i.get('quality',{}).get('can_approve') for i in items):
      fresh=candidate;break
  selectable_fresh=fresh if any(i['id']==fresh for i in eligible) else None
  item=saved if protected else (selectable_fresh or (saved if any(i['id']==saved for i in eligible) else None) or (eligible[0]['id'] if eligible else None))
  c.execute('INSERT INTO full_daily_slates(day,item) VALUES (?,?) ON CONFLICT(day) DO UPDATE SET item=excluded.item',(day,item))
 return {'day':day,'id':item,'daily_draft_id':fresh,'available':len(eligible),'target':1,'automatic_generation':json.loads((BASE/'cinematic-settings.json').read_text()).get('daily_generation',False)}


def make_extra(n):
 """Owner's 'Make N more Shorts' click: queue N fresh Shorts any time (not tied to the 9 AM daily slot). They build one at a time."""
 n=max(1,min(int(n),21));previous=history();known=jobs.list_jobs()
 active={j['book'] for j in known if j['state'] in ('queued','running','retry_wait','recovering')}
 latest={}
 for j in known:latest.setdefault(j['book'],j)
 fresh=[b for b in jobs.BOOKS if b['id'] not in latest and normalize(b['title']) not in previous]
 reuse=[b for b in jobs.BOOKS if b['id'] in latest and b['id'] not in active and has_next_edition(latest[b['id']])]
 queued=[];note=''
 for b in fresh+reuse:
  if len(queued)>=n:break
  try:queued.append(jobs.enqueue(b['id'])['id'])
  except Exception as e:
   note=str(e)[:160]
   if 'limit' in note.lower():break
 return {'requested':n,'queued':len(queued),'note':note}
