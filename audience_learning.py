"""Durable observed performance, comparable age windows and cautious editorial experiments.
No publishing or content-generation imports. Cached history is never made artificially fresh.
"""
import datetime,hashlib,json,math,re,sqlite3,statistics,threading,time,urllib.parse
from pathlib import Path
BASE=Path(__file__).resolve().parent;DB=BASE/'decisions.sqlite3';VERSION='audience-learning-v2'
HOUR=3600;MIN_SAMPLE=5;WINDOWS={24:6,72:12}

def connect(db=None):
 c=sqlite3.connect(db or DB,timeout=20);c.row_factory=sqlite3.Row
 c.executescript('''CREATE TABLE IF NOT EXISTS audience_posts(
 platform TEXT,post_key TEXT,provider TEXT,url TEXT,title TEXT,published_at REAL,
 first_seen REAL,last_seen REAL,content_hash TEXT,content_changed INTEGER DEFAULT 0,
 format TEXT DEFAULT 'unknown',item TEXT,fingerprint TEXT,creative_json TEXT,
 PRIMARY KEY(platform,post_key,provider));
 CREATE TABLE IF NOT EXISTS audience_observations(
 platform TEXT,post_key TEXT,provider TEXT,sample_key TEXT,observed_at REAL,measured_at REAL,
 views INTEGER,likes INTEGER,comments INTEGER,average_watch_seconds REAL,
 PRIMARY KEY(platform,post_key,provider,sample_key));
 CREATE INDEX IF NOT EXISTS audience_age ON audience_observations(platform,post_key,provider,measured_at);
 CREATE TABLE IF NOT EXISTS audience_collectors(name TEXT PRIMARY KEY,last_attempt REAL,next_due REAL,last_success REAL,state TEXT);''')
 return c

def timestamp(value):
 if isinstance(value,bool):return None
 if isinstance(value,(float,int)):return float(value) if math.isfinite(value) and value>0 else None
 if not isinstance(value,str):return None
 try:
  date=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
  return date.timestamp() if date.tzinfo else None
 except (ValueError,OverflowError):return None

def number(value,integer=True):
 if value is None or isinstance(value,bool):return None
 try:n=float(value)
 except (ValueError,TypeError,OverflowError):return None
 if not math.isfinite(n) or n<0 or (integer and not n.is_integer()):return None
 return int(n) if integer else n

def identity(platform,url):
 try:
  u=urllib.parse.urlparse(url);host=(u.hostname or '').lower();path=u.path.rstrip('/')
  if u.scheme!='https' or u.username or u.password:return None
  if platform=='youtube' and host in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
   key=path.rsplit('/',1)[-1] if host=='youtu.be' or path.startswith(('/shorts/','/live/')) else urllib.parse.parse_qs(u.query).get('v',[''])[0]
   return key if re.fullmatch('[A-Za-z0-9_-]{11}',key) else None
  if platform=='instagram' and host in ('instagram.com','www.instagram.com'):
   match=re.fullmatch('/(?:reel|p|tv)/([A-Za-z0-9_-]+)',path);return match[1] if match else None
  if platform=='tiktok' and host in ('tiktok.com','www.tiktok.com'):
   match=re.fullmatch('/@[^/]+/video/([0-9]+)',path);return match[1] if match else None
 except (ValueError,TypeError):pass
 return None

def known_format(platform,url):
 path=urllib.parse.urlparse(url).path
 return 'short' if (platform=='youtube' and path.startswith('/shorts/')) or (platform=='instagram' and path.startswith('/reel/')) else 'unknown'

def display_title(text):
 import captions
 clean=captions.clean(str(text or ''));line=next((line.strip() for line in clean.splitlines() if line.strip()),'Published video')
 return line if len(line)<=130 else line[:130].rsplit(' ',1)[0]+'…'

def record(platform,provider,url,title,published_at,observed_at,metrics,measured_at=None,content=None,db=None):
 key=identity(platform,url);observed=timestamp(observed_at);published=timestamp(published_at);measured=timestamp(measured_at)
 if published and observed and published>observed+300:published=None
 if not key or provider not in ('youtube_direct','buffer') or not observed:return False
 # Never qualify a future or pre-publication provider timestamp as a checkpoint.
 if measured and (measured>observed+300 or (published and measured<published)):measured=None
 digest=hashlib.sha256(str(content if content is not None else title).encode()).hexdigest()
 # Direct API observations are saved at most once per UTC hour; Buffer by its real update time.
 normalized={name:number(metrics.get(name),name!='average_watch_seconds') for name in ('views','likes','comments','average_watch_seconds')}
 revision=hashlib.sha256(json.dumps(normalized,sort_keys=True).encode()).hexdigest()[:16]
 sample='m:'+str(measured)+':'+revision if provider=='buffer' and measured else 'h:'+str(int(observed/HOUR))
 with connect(db) as c:
  c.execute('INSERT INTO audience_posts(platform,post_key,provider,url,title,published_at,first_seen,last_seen,content_hash) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(platform,post_key,provider) DO UPDATE SET url=excluded.url,title=excluded.title,published_at=COALESCE(audience_posts.published_at,excluded.published_at),last_seen=MAX(audience_posts.last_seen,excluded.last_seen),content_changed=MAX(audience_posts.content_changed,audience_posts.content_hash!=excluded.content_hash)',(platform,key,provider,url,str(title or 'Published video')[:200],published,observed,observed,digest))
  fmt=known_format(platform,url)
  if fmt=='unknown':
   formats={r[0] for r in c.execute("SELECT DISTINCT format FROM audience_posts WHERE platform=? AND post_key=? AND format!='unknown'",(platform,key))}
   if len(formats)==1:fmt=formats.pop()
  if fmt!='unknown':c.execute("UPDATE audience_posts SET format=? WHERE platform=? AND post_key=? AND format='unknown' AND item IS NULL",(fmt,platform,key))
  same=c.execute('SELECT 1 FROM audience_observations WHERE platform=? AND post_key=? AND provider=? AND measured_at IS ? AND views IS ? AND likes IS ? AND comments IS ? AND average_watch_seconds IS ? LIMIT 1',(platform,key,provider,measured,normalized['views'],normalized['likes'],normalized['comments'],normalized['average_watch_seconds'])).fetchone() if provider=='buffer' and measured else None
  if not same:c.execute('INSERT OR IGNORE INTO audience_observations VALUES(?,?,?,?,?,?,?,?,?,?)',(platform,key,provider,sample,observed,measured,normalized['views'],normalized['likes'],normalized['comments'],normalized['average_watch_seconds']))
 return True

def ingest_buffer(data,expected,db=None):
 observed=timestamp(data.get('checked_at')) or timestamp(data.get('fetched'));count=0
 if not observed:return 0
 for post in data.get('posts',[]):
  platform=post.get('channelService')
  if platform not in expected or post.get('channelId')!=expected[platform] or post.get('status')!='sent' or not post.get('externalLink'):continue
  raw={m.get('type'):m for m in post.get('metrics',[]) or []};metrics={k:(raw.get(k) or {}).get('value') for k in ('views','likes','comments')}
  if 'likes' not in raw and 'reactions' in raw:metrics['likes']=raw['reactions'].get('value')
  watch=raw.get('averageTimeWatched') or {};unit=str(watch.get('unit','')).lower();value=number(watch.get('value'),False)
  metrics['average_watch_seconds']=value if unit in ('s','second','seconds','count') else (value/1000 if value is not None and unit in ('ms','millisecond','milliseconds') else None)
  count+=bool(record(platform,'buffer',post['externalLink'],display_title(post.get('text','')),post.get('sentAt'),observed,metrics,post.get('metricsUpdatedAt'),post.get('text',''),db=db))
 note_collection('buffer',observed,db=db)
 return count

def ingest_youtube(video,observed,expected,db=None):
 if video.get('snippet',{}).get('channelId')!=expected:return False
 if video.get('status',{}).get('privacyStatus')!='public' or video.get('status',{}).get('uploadStatus')!='processed':return False
 stats=video.get('statistics',{})
 saved=record('youtube','youtube_direct','https://www.youtube.com/watch?v='+video.get('id',''),video.get('snippet',{}).get('title',''),video.get('snippet',{}).get('publishedAt'),observed,{'views':stats.get('viewCount'),'likes':stats.get('likeCount'),'comments':stats.get('commentCount')},observed,db=db)
 if saved:note_collection('youtube_direct',observed,db=db)
 return saved

def note_collection(provider,observed,db=None):
 at=timestamp(observed)
 if not at:return
 interval=6*HOUR if provider=='buffer' else 120
 with connect(db) as c:
  c.execute("INSERT INTO audience_collectors(name,last_attempt,next_due,last_success,state) VALUES(?,?,?,?,'saved') ON CONFLICT(name) DO UPDATE SET last_attempt=MAX(audience_collectors.last_attempt,excluded.last_attempt),next_due=MAX(audience_collectors.next_due,excluded.next_due),last_success=MAX(COALESCE(audience_collectors.last_success,0),excluded.last_success),state=CASE WHEN excluded.last_success>=audience_collectors.last_attempt THEN 'saved' ELSE audience_collectors.state END",(provider,at,at+interval,at))

def bind_items(items,publications):
 """Bind only a URL plus matching reviewed fingerprint. Never infer format from titles."""
 available={i['id']:i for i in items};count=0
 with connect() as c:
  for post in publications:
   item=available.get(post.get('item'));platform=post.get('platform','youtube');key=identity(platform,post.get('url'))
   if not item or not key or not post.get('fingerprint') or post['fingerprint']!=item.get('quality',{}).get('fingerprint'):continue
   creative=item.get('quality',{}).get('creative') or {};hook=creative.get('hook','')
   features={'hook':hook,'hook_style':('question' if '?' in hook else 'statement') if hook else 'unknown','headline':creative.get('headline'),'creative_version':'+'.join(filter(None,[(creative.get('director') or {}).get('version') or creative.get('version'),creative.get('scene_direction_version')]))}
   c.execute("UPDATE audience_posts SET format=?,item=?,fingerprint=?,creative_json=? WHERE platform=? AND post_key=? AND item IS NULL AND (format='unknown' OR format=?)",(item.get('content_type','unknown'),item['id'],post['fingerprint'],json.dumps(features),platform,key,item.get('content_type','unknown')));count+=c.execute('SELECT changes()').fetchone()[0]
 return count

def checkpoint(observations,published,hours,now):
 if not published:return {'state':'publication_time_unknown','sample':None}
 eligible=[s for s in observations if s['measured_at'] is not None and hours*HOUR<=s['measured_at']-published<=(hours+WINDOWS[hours])*HOUR and s['measured_at']<=now and s['views'] is not None]
 if eligible:
  point=min(eligible,key=lambda s:(s['measured_at'],-s['observed_at']));return {'state':'measured','age_hours':round((point['measured_at']-published)/HOUR,2),'sample':point}
 state='waiting' if now<published+hours*HOUR else ('collecting' if now<=published+(hours+WINDOWS[hours])*HOUR else 'missed')
 return {'state':state,'sample':None}

def production_version(post):
 value=post.get('creative',{}).get('creative_version')
 return value.strip() if isinstance(value,str) and value.strip() else 'unrecorded'

def coverage(cohort,hours):
 counts={state:0 for state in ('measured','waiting','collecting','missed','publication_time_unknown')}
 for post in cohort:counts[post['at_'+str(hours)+'h']['state']]+=1
 return counts

def readiness(posts):
 rows=[]
 for platform in ('youtube','instagram','tiktok'):
  groups={}
  for post in posts:
   if post['platform']==platform:groups.setdefault(post['post_key'],[]).append(post)
  rows.append({'platform':platform,'posts':len(groups),'measured_24h_posts':sum(any(p['at_24h']['sample'] is not None for p in group) for group in groups.values()),'unclassified_24h_posts':sum(any(p['at_24h']['sample'] is not None for p in group) and not any(p['format'] in ('short','full') for p in group) for group in groups.values()),'measured_72h_posts':sum(any(p['at_72h']['sample'] is not None for p in group) for group in groups.values()),'watch_time_posts':sum(any(p['latest'] and p['latest']['average_watch_seconds'] is not None for p in group) for group in groups.values()),'retention_available':False})
 return rows

def experiment(cohort):
 valid=[p for p in cohort if p['at_24h']['sample'] and not p['content_changed']];n=len(valid)
 result={'sample_size':n,'minimum':MIN_SAMPLE,'platform':cohort[0]['platform'],'format':cohort[0]['format'],'provider':cohort[0]['provider'],'creative_version':production_version(cohort[0]),'coverage_24h':coverage(cohort,24),'coverage_72h':coverage(cohort,72),'changed_posts_excluded':sum(bool(p['content_changed']) for p in cohort),'kind':'waiting','message':f'{n}/{MIN_SAMPLE} comparable 24-hour measurements. Keep collecting before changing the creative rules.'}
 if n<MIN_SAMPLE:return result
 values=[p['at_24h']['sample']['views'] for p in valid];median=statistics.median(values);top=max(valid,key=lambda p:p['at_24h']['sample']['views'])
 result.update(kind='observation',median_24h_views=median,leading_post={'title':top['title'],'url':top['url'],'views':top['at_24h']['sample']['views'],'age_hours':top['at_24h']['age_hours']},message='Review the leading post’s opening and cover, checking source accuracy before borrowing an idea. Test one change in a future reviewed draft. Views do not verify a claim or prove better retention or a causal effect.')
 groups={kind:[p['at_24h']['sample']['views'] for p in valid if p['creative'].get('hook_style')==kind] for kind in ('question','statement')}
 if all(len(g)>=3 for g in groups.values()) and n>=8 and all(production_version(p)!='unrecorded' for p in valid) and len({production_version(p) for p in valid})==1:
  result['hook_comparison']={kind:{'n':len(g),'median_views':statistics.median(g)} for kind,g in groups.items()}
 result['caution']='Small observational sample: topic, timing, reach and platform reporting can explain differences. No automatic script changes.'
 return result

def snapshot(now=None):
 now=time.time() if now is None else now
 result={'available':True,'version':VERSION,'saved_observations':0,'posts':[],'cohorts':[],'collectors':[],'data_readiness':[],'post_count':0,'retention_curve':{'available':False,'reason':'Retention curves are not collected by the current connections. Average watch time is shown separately only when a provider supplies explicit seconds or milliseconds.'},'policy':'Comparisons use the last 30 days. 24h: first measured point between 24–30h. 72h: first point between 72–84h. Missing windows are never reconstructed from current totals. Platforms, formats, providers and recorded production styles are compared separately. Unrecorded styles stay separate and cannot support hook-style comparisons.'}
 if not DB.is_file():return result
 with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=20) as c:
  c.row_factory=sqlite3.Row;tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if 'audience_posts' not in tables:return result
  posts=[dict(r) for r in c.execute('SELECT * FROM audience_posts ORDER BY published_at DESC')];observations=[dict(r) for r in c.execute('SELECT * FROM audience_observations ORDER BY observed_at')]
  result['collectors']=[dict(r) for r in c.execute('SELECT * FROM audience_collectors')]
 result['saved_observations']=len(observations);grouped={}
 for s in observations:grouped.setdefault((s['platform'],s['post_key'],s['provider']),[]).append(s)
 enriched=[]
 for p in posts:
  samples=grouped.get((p['platform'],p['post_key'],p['provider']),[]);p['creative']=json.loads(p.pop('creative_json') or '{}');p.pop('content_hash',None)
  p['latest']=samples[-1] if samples else None;p['at_24h']=checkpoint(samples,p['published_at'],24,now);p['at_72h']=checkpoint(samples,p['published_at'],72,now)
  a,b=p['at_24h']['sample'],p['at_72h']['sample'];p['views_gained_24_to_72']=b['views']-a['views'] if a and b else None
  p['counter_adjusted']=p['views_gained_24_to_72'] is not None and p['views_gained_24_to_72']<0
  last=p['latest'];p['like_comment_rate']=round(100*(last['likes']+last['comments'])/last['views'],2) if last and last['views'] and last['likes'] is not None and last['comments'] is not None else None
  p['stale']=not last or now-(last['measured_at'] or last['observed_at'])>12*HOUR
  p['timing_verified']=bool(last and last['measured_at'] is not None)
  p['timeline']=samples[-30:];enriched.append(p)
 # A YouTube video can be present in both sources. Prefer direct observations for display;
 # preserve both histories and compare within their own provider cohorts.
 display={}
 for p in enriched:
  key=(p['platform'],p['post_key']);old=display.get(key)
  if old is None or p['provider']=='youtube_direct':display[key]=p
 result['posts']=list(display.values())
 # Keep the preferred provider for headline totals, but expose other saved checkpoint evidence explicitly.
 for post in result['posts']:
  post['source_measurements']=[{'provider':p['provider'],'latest':p['latest'],'at_24h':p['at_24h'],'at_72h':p['at_72h'],'stale':p['stale']} for p in enriched if (p['platform'],p['post_key'])==(post['platform'],post['post_key'])]
 result['data_readiness']=readiness(enriched)
 for platform in ('youtube','instagram','tiktok'):
  for fmt in ('short','full'):
   for provider in ('youtube_direct','buffer'):
    cohort=[p for p in enriched if p['platform']==platform and p['format']==fmt and p['provider']==provider and p['published_at'] and 0<=now-p['published_at']<=30*24*HOUR]
    for version in sorted({production_version(p) for p in cohort}):
     result['cohorts'].append(experiment([p for p in cohort if production_version(p)==version]))
 result['post_count']=len(result['posts']);return result

def claim(name,now=None):
 now=time.time() if now is None else now
 with connect() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT next_due FROM audience_collectors WHERE name=?',(name,)).fetchone()
  if row and row[0]>now:return False
  c.execute("INSERT INTO audience_collectors(name,last_attempt,next_due,state) VALUES(?,?,?,'checking') ON CONFLICT(name) DO UPDATE SET last_attempt=excluded.last_attempt,next_due=excluded.next_due,state='checking'",(name,now,now+6*HOUR));return True

def collector_result(name,state,now=None,next_due=None):
 now=time.time() if now is None else now
 with connect() as c:
  c.execute('UPDATE audience_collectors SET state=?,last_success=CASE WHEN ?=\'saved\' THEN ? ELSE last_success END,next_due=? WHERE name=?',(state,state,now,next_due or now+(6*HOUR if state in ('saved','budget_paused','not_connected') else HOUR),name))

def refresh_due(items_callback=None):
 if not claim('buffer'):return False
 try:
  import buffer_api,multiplatform
  if not (buffer_api.PRIVATE/'credentials.json').is_file():collector_result('buffer','not_connected');return False
  if buffer_api.budget_status()['analytics_paused']:collector_result('buffer','budget_paused');return False
  data=multiplatform.remote_history();ingest_buffer(data,multiplatform.EXPECTED)
  if items_callback:
   import publishing
   bind_items(items_callback(),publishing.list_posts()+multiplatform.rows())
  collector_result('buffer','saved',now=timestamp(data.get('checked_at')) or timestamp(data.get('fetched')),next_due=max(time.time()+60,(timestamp(data.get('fetched')) or time.time())+6*HOUR));return True
 except Exception:
  collector_result('buffer','refresh_failed');return False

def start(items_callback=None):
 # Bootstrap the previous cache at its original timestamp. Never invent historical observations.
 import multiplatform
 with connect():pass
 try:ingest_buffer(json.loads((BASE/'buffer-history.json').read_text()),multiplatform.EXPECTED)
 except (OSError,ValueError,sqlite3.Error):pass
 if items_callback:
  try:
   import publishing
   bind_items(items_callback(),publishing.list_posts()+multiplatform.rows())
  except Exception:pass
 def loop():
  while True:
   try:refresh_due(items_callback)
   except Exception:pass # Metrics must never stop generation or publishing.
   time.sleep(60)
 threading.Thread(target=loop,daemon=True).start()
