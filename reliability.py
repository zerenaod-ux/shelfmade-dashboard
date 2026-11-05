"""Seven-day local evidence tracker. No network, generation, review or publishing actions."""
import argparse,datetime,fcntl,hashlib,json,os,sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
import quality
BASE=Path(__file__).resolve().parent;DB=BASE/'decisions.sqlite3';HISTORY=BASE/'reliability-history.json'
ZONE=ZoneInfo('America/Chicago');NETWORKS=('youtube','instagram','tiktok')
def utc(value):
 try:
  parsed=datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'));return parsed.replace(tzinfo=datetime.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(datetime.timezone.utc)
 except (ValueError,TypeError):return None
def rows(c,table):
 if table not in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}:return []
 return [dict(r) for r in c.execute('SELECT * FROM '+table)]
def snapshot(now=None):
 now=(now or datetime.datetime.now(ZONE)).astimezone(ZONE);day=now.date();items=[];problems=[]
 with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=10) as c:
  c.row_factory=sqlite3.Row;shorts=rows(c,'jobs');fulls=rows(c,'full_jobs');posts=rows(c,'platform_posts');direct=rows(c,'publications')
 for kind,records in [('short',shorts),('full',fulls)]:
  for job in records:
   completed=utc(job.get('updated'))
   if not completed or completed>now or completed.astimezone(ZONE).date()!=day:continue
   if job['state']=='failed':problems.append({'type':kind,'book':job['book'],'state':'failed','reason':job.get('error')});continue
   if job['state']!='ready':continue
   attempts=job.get('attempts') or 0
   folder=(BASE/'generated'/job['id']/str(attempts)) if kind=='short' else BASE/'full-generated'/(job['id']+'-attempt-'+str(attempts) if attempts>1 else job['id'])
   video=folder/('final.mp4' if kind=='short' else 'cinematic_LONGFORM.mp4')
   if not video.is_file() or not (folder/'POST_THIS.txt').is_file():problems.append({'type':kind,'book':job['book'],'state':'missing_package'});continue
   checked=quality.inspect(folder,video.name,kind=='full')
   if not checked.get('can_approve') or (kind=='full' and not 300<=float(checked.get('duration') or 0)<=480):problems.append({'type':kind,'book':job['book'],'state':'quality_blocked'});continue
   item='job-'+job['id'] if kind=='short' else 'long-'+hashlib.sha256(folder.name.encode()).hexdigest()[:24];fingerprint=checked['fingerprint'];destinations={}
   for platform in NETWORKS if kind=='short' else ('youtube',):
    candidates=[p for p in posts if p.get('item')==item and p.get('fingerprint')==fingerprint and p.get('platform')==platform]
    if platform=='youtube':candidates.extend(p for p in direct if p.get('item')==item and p.get('fingerprint')==fingerprint)
    confirmed=next((p for p in candidates if p.get('state')=='published' and p.get('url')),None)
    destinations[platform]={'state':'published','url':confirmed['url']} if confirmed else {'state':candidates[0]['state'] if candidates else 'not_submitted','url':None}
   items.append({'item':item,'book':job['book'],'type':kind,'completed_at':completed.isoformat(),'duration':checked.get('duration'),'attempts':attempts,'destinations':destinations})
 short_count=sum(i['type']=='short' for i in items);full_count=sum(i['type']=='full' for i in items)
 return {'observed_at':now.isoformat(),'day':day.isoformat(),'timezone':str(ZONE),'targets':{'shorts':3,'full':1},'completed':{'shorts':short_count,'full':full_count},'production_target_met':short_count>=3 and full_count>=1,'items':items,'problems':problems,'all_completed_items_published':bool(items) and all(all(p['state']=='published' for p in i['destinations'].values()) for i in items),'limits':'Observed local completed packages and last verified receipts. Not continuous uptime, provider authentication, source-fact or visual playback review. Pending provider states may be stale; no missing observations are backfilled.'}
def record(now=None):
 now=(now or datetime.datetime.now(ZONE)).astimezone(ZONE)
 lock=HISTORY.with_suffix('.lock');fd=os.open(lock,os.O_RDWR|os.O_CREAT,0o600)
 with os.fdopen(fd,'a') as handle:
  fcntl.flock(handle,fcntl.LOCK_EX)
  if HISTORY.exists():history=json.loads(HISTORY.read_text())
  else:
   history={'window_start':now.date().isoformat(),'window_end':(now.date()+datetime.timedelta(days=6)).isoformat(),'timezone':str(ZONE),'observations':[]}
  if history['window_start']<=now.date().isoformat()<=history['window_end']:
   observation=snapshot(now)
   if not history['observations'] or history['observations'][-1]['observed_at']!=observation['observed_at']:history['observations'].append(observation)
   temp=HISTORY.with_suffix('.pending');file=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
   with os.fdopen(file,'w') as target:json.dump(history,target,indent=2);target.flush();os.fsync(target.fileno())
   temp.replace(HISTORY)
  return history

def summary(history):
 latest={}
 for observation in history['observations']:latest[observation['day']]=observation
 return {'window_start':history['window_start'],'window_end':history['window_end'],'observed_days':len(latest),'days_target_met_at_last_observation':sum(o['production_target_met'] for o in latest.values()),'unobserved_days':7-len(latest),'latest':history['observations'][-1] if history['observations'] else None,'note':'An incomplete day is not a full-day failure until the day closes. Unobserved days are unknown; this is not a continuous-uptime test.'}
def dashboard(now=None):
 """Read saved observations only; dashboard refresh never records or probes providers."""
 now=(now or datetime.datetime.now(ZONE)).astimezone(ZONE)
 if not HISTORY.exists():return {'available':False,'message':'The seven-day check has no saved observations yet.'}
 try:
  history=json.loads(HISTORY.read_text());start=datetime.date.fromisoformat(history['window_start']);end=datetime.date.fromisoformat(history['window_end'])
  if (end-start).days!=6:raise ValueError('Invalid observation window')
  latest={}
  for observation in history['observations']:
   stamp=utc(observation['observed_at']);day=datetime.date.fromisoformat(observation['day'])
   if not stamp or stamp>now or stamp.astimezone(ZONE).date()!=day or not start<=day<=end:continue
   counts=observation['completed']
   if any(type(counts[k]) is not int or counts[k]<0 for k in ('shorts','full')):raise ValueError('Invalid counts')
   if day not in latest or stamp>utc(latest[day]['observed_at']):latest[day]=observation
  days=[]
  for offset in range(7):
   day=start+datetime.timedelta(days=offset);saved=latest.get(day)
   if saved:
    counts=saved['completed'];state='target_met' if counts['shorts']>=3 and counts['full']>=1 else 'incomplete'
    # Require a complete receipt for each expected destination; a saved boolean alone is insufficient.
    confirmed=expected=0
    for item in saved.get('items',[]):
     for platform in NETWORKS if item['type']=='short' else ('youtube',):
      expected+=1;receipt=item.get('destinations',{}).get(platform,{})
      confirmed+=int(receipt.get('state')=='published' and bool(receipt.get('url')))
    days.append({'day':day.isoformat(),'state':state,'completed':counts,'observed_at':saved['observed_at'],'confirmed_destinations':confirmed,'expected_destinations':expected,'problem_count':len(saved.get('problems',[]))})
   else:days.append({'day':day.isoformat(),'state':'upcoming' if day>now.date() else 'unknown','completed':None,'observed_at':None})
  return {'available':True,'window_start':start.isoformat(),'window_end':end.isoformat(),'timezone':str(ZONE),'today':now.date().isoformat(),'observed_days':len(latest),'days':days,'note':'Saved observations only. Missing days stay unknown; incomplete counts describe the last check, not continuous uptime. Publishing receipts may be delayed. Daily check: 6 p.m. Chicago time.'}
 except (ValueError,KeyError,TypeError,OSError):return {'available':False,'message':'Saved reliability history could not be read. Run the local maintenance check.'}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('record','status'));args=parser.parse_args()
 history=record() if args.action=='record' else json.loads(HISTORY.read_text());print(json.dumps(summary(history),indent=2))
