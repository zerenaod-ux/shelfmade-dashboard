"""Approved Shorts that could not be submitted (Buffer daily allowance used up) are scheduled automatically later.
Never posts anything the owner did not approve: it only retries items that are approved, reviewed and already prepared."""
import threading,time,traceback
from pathlib import Path
import buffer_api,multiplatform,publishing
PLATFORMS=['youtube','instagram','tiktok']
LIVE=('scheduled','queued','sending','published','draft','needs_reconciliation')
def pending(inventory,connection):
 posted={}
 for r in multiplatform.rows():
  if r['state'] in LIVE:posted.setdefault((r['item'],r['fingerprint']),set()).add(r['platform'])
 out=[]
 with connection() as c:
  approved={r[0] for r in c.execute("SELECT id FROM decisions WHERE status='approved'")}
  reviews=dict(c.execute('SELECT id,fingerprint FROM editorial_reviews').fetchall())
 for item in inventory():
  if item.get('content_type')=='full' or item['id'] not in approved or not item.get('ready'):continue
  fp=item['quality']['fingerprint']
  if reviews.get(item['id'])!=fp or set(PLATFORMS)<=posted.get((item['id'],fp),set()) or posted.get((item['id'],fp)):continue
  with publishing.connect() as c:prep=c.execute('SELECT * FROM publications WHERE item=? AND fingerprint=? ORDER BY created DESC LIMIT 1',(item['id'],fp)).fetchone()
  if prep:out.append((item,dict(prep)))
 return out
def run_once(inventory,connection,studio):
 if buffer_api.budget_status()['available']<len(PLATFORMS)+16:return 'waiting for daily allowance'
 for item,prep in pending(inventory,connection):
  folder=Path(item['folder']) if item.get('generated') else studio/'01_REVIEW'/item['folder']
  try:
   multiplatform.start(item,prep,folder/'final.mp4',PLATFORMS,True);return 'scheduled '+item['id']
  except buffer_api.BudgetError:return 'waiting for daily allowance'
  except Exception as e:print('Auto-schedule skipped',item['id'],str(e)[:160],flush=True)
 return 'nothing waiting'
def start(inventory,connection,studio,every=600):
 def loop():
  time.sleep(120)
  while True:
   try:
    r=run_once(inventory,connection,studio)
    if r.startswith('scheduled'):print('Auto-schedule:',r,flush=True);time.sleep(30);continue
   except Exception:traceback.print_exc()
   time.sleep(every)
 threading.Thread(target=loop,daemon=True,name='auto-schedule').start()
