"""Durable per-platform publishing with conservative retry semantics."""
import json, sqlite3, threading, time, uuid, hashlib, datetime, re
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import buffer_api, cloudinary_host, publishing, quality, delivery_video, captions, posting_slots
BASE=Path(__file__).resolve().parent
DB=BASE/'decisions.sqlite3'
LOCK=threading.Lock()
FIELDS='id channelId channelService text status externalLink sentAt dueAt error {message} assets {source} createdAt'
EXPECTED={'youtube':'6acef48c778b240e2f0201d8','instagram':'6acef38d778b240e2f01f97b','tiktok':'6acef41b778b240e2f01fe44'}
def connect():
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS platform_posts(id TEXT PRIMARY KEY,item TEXT,fingerprint TEXT,platform TEXT,title TEXT,description TEXT,state TEXT,remote_id TEXT,url TEXT,error TEXT,checked_at TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(item,fingerprint,platform))')
 c.execute('CREATE TABLE IF NOT EXISTS hosted_videos(fingerprint TEXT PRIMARY KEY,url TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS delivery_hosts(fingerprint TEXT PRIMARY KEY,url TEXT NOT NULL)')
 columns={r[1] for r in c.execute('PRAGMA table_info(platform_posts)')}
 if 'due_at' not in columns:
  try:c.execute('ALTER TABLE platform_posts ADD COLUMN due_at TEXT')
  except sqlite3.OperationalError as e:
   if 'duplicate column' not in str(e):raise
 if 'path' not in columns:
  try:c.execute('ALTER TABLE platform_posts ADD COLUMN path TEXT')
  except sqlite3.OperationalError as e:
   if 'duplicate column' not in str(e):raise
 if 'submitted_at' not in columns:
  try:c.execute('ALTER TABLE platform_posts ADD COLUMN submitted_at TEXT')
  except sqlite3.OperationalError as e:
   if 'duplicate column' not in str(e):raise
 c.execute('CREATE TABLE IF NOT EXISTS publishing_events(sequence INTEGER PRIMARY KEY,post_id TEXT,state TEXT,evidence TEXT,observed_at TEXT)')
 publishing.claim_schema(c)
 c.commit()
 return c

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def rows():
 with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM platform_posts ORDER BY created DESC')]
def update(id,**values):
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  previous=c.execute('SELECT state FROM platform_posts WHERE id=?',(id,)).fetchone()
  # An uncertain response or stale provider snapshot must never erase a verified receipt.
  if previous and previous['state']=='published' and values.get('state','published')!='published':return False
  c.execute('UPDATE platform_posts SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),id))
  if previous and 'state' in values:
   c.execute('INSERT INTO publishing_events(post_id,state,evidence,observed_at) VALUES(?,?,?,?)',(id,values['state'],values.get('error') or ('Provider response checked' if values.get('checked_at') else 'Local workflow'),now()))
 return True

def public_link(platform,url):
 if not isinstance(url,str):return False
 try:
  p=urlparse(url)
  if p.scheme!='https' or p.username or p.password or p.port not in (None,443):return False
  host=(p.hostname or '').lower()
  if platform=='youtube':return (host in ('youtube.com','www.youtube.com','m.youtube.com') and ((p.path=='/watch' and re.fullmatch(r'[A-Za-z0-9_-]{11}',parse_qs(p.query).get('v',[''])[0])) or re.fullmatch(r'/shorts/[A-Za-z0-9_-]{11}/?',p.path))) or (host=='youtu.be' and re.fullmatch(r'/[A-Za-z0-9_-]{11}/?',p.path))
  if platform=='instagram':return host in ('instagram.com','www.instagram.com') and bool(re.fullmatch(r'/(?:reel|reels|p)/[A-Za-z0-9_-]+/?',p.path))
  if platform=='tiktok':return host in ('tiktok.com','www.tiktok.com') and bool(re.fullmatch(r'/@[^/]+/video/[0-9]+/?',p.path))
 except ValueError:return False
 return False

def status():
 try:
  connection_data=json.loads((buffer_api.PRIVATE/'channels.json').read_text());channels=connection_data['channels']
  configured=all(any(c['id']==id and c['service']==p for c in channels) for p,id in EXPECTED.items())
 except (OSError,ValueError,KeyError):configured=False
 try:cloudinary_host.credentials();hosted=True
 except ValueError:hosted=False
 networks={}
 for platform,id in EXPECTED.items():
  channel=next((c for c in channels if c['id']==id),{}) if configured else {}
  networks[platform]={'connected':bool(channel) and not channel.get('isDisconnected',False) and not channel.get('isLocked',False),'account':channel.get('name',''),'reconnect_url':'https://publish.buffer.com/channels/'+id+'/schedule'}
 return {'ready':configured and hosted,'buffer':configured,'hosting':hosted,'posts':rows(),'networks':networks,'all_connected':all(v['connected'] for v in networks.values()),'budget':buffer_api.budget_status()}
def validate_channels(platforms=None,force=True):
 platforms=platforms or list(EXPECTED)
 channels=None
 if not force:
  try:
   data=json.loads((buffer_api.PRIVATE/'channels.json').read_text())
   import datetime
   at=datetime.datetime.fromisoformat(data['verified_at']).timestamp()
   if time.time()-at<300:channels=data['channels']
  except (OSError,ValueError,KeyError):pass
 if channels is None:channels=buffer_api.verify()
 for p in platforms:
  id=EXPECTED[p];channel=next((c for c in channels if c['id']==id and c['service']==p),None)
  if not channel or channel.get('isDisconnected') or channel.get('isLocked'):raise buffer_api.NotSubmittedError(p+' is disconnected. Refresh its connection in Buffer before publishing there.')
 return channels

def payload(platform,title,description,url,draft=False):
 metadata={'youtube':{'title':title,'privacy':'public','madeForKids':False,'notifySubscribers':True,'categoryId':'27'},'instagram':{'type':'reel','shouldShareToFeed':True},'tiktok':{'title':title}}
 due=None if draft else posting_slots.next_due(BASE/'posting-slots.json',platform,reserve=True)
 out={'channelId':EXPECTED[platform],'text':captions.clean(description),'schedulingType':'automatic','mode':'customScheduled' if due else 'shareNow','needsApproval':False,'saveToDraft':draft,'assets':[{'video':{'url':url,'metadata':{'thumbnailOffset':1000}}}],'metadata':{platform:metadata[platform]}}
 if due:out['dueAt']=due
 return out
def create_remote(platform,title,description,url,draft=False):
 result=buffer_api.query('mutation($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{'+FIELDS+'}} ... on MutationError{message}}}',{'input':payload(platform,title,description,url,draft)})['createPost']
 if not result.get('post'):raise buffer_api.NotSubmittedError(result.get('message','Buffer rejected this post.'))
 return result['post']
def apply_remote(id,post):
 with connect() as c:row=c.execute('SELECT * FROM platform_posts WHERE id=?',(id,)).fetchone()
 if not row:return False
 valid=isinstance(post,dict) and isinstance(post.get('id'),str) and bool(post.get('id')) and post.get('channelId')==EXPECTED[row['platform']] and post.get('channelService')==row['platform'] and (not row['remote_id'] or row['remote_id']==post['id'])
 if not valid:
  update(id,state='needs_reconciliation',error='Platform response could not be matched to this account and submission. Refresh status; do not submit again.')
  return False
 remote=post.get('status');link=post.get('externalLink')
 state='published' if remote=='sent' and public_link(row['platform'],link) else 'failed' if remote=='error' else remote if remote in ('sending','scheduled','draft','queued') else 'needs_reconciliation'
 detail=post.get('error');error=detail.get('message') if isinstance(detail,dict) else None
 if state=='needs_reconciliation':error='Buffer has not supplied a verified public post link. Refresh status before any retry.'
 return update(id,remote_id=post['id'],state=state,url=link if state=='published' else None,error=error,checked_at=now(),due_at=post.get('dueAt') if state=='scheduled' else None)

def start(item,preparation,path,platforms,approved):
 if item.get("content_type")=="full":raise ValueError("Full videos use the direct YouTube upload queue.")
 if not approved:raise ValueError('Review and approve the current video first.')
 if not isinstance(platforms,list) or not platforms or len(set(platforms))!=len(platforms) or any(p not in EXPECTED for p in platforms):raise ValueError('Choose valid publishing destinations.')
 ticket=buffer_api.reserve_publish(len(platforms)+16)
 with buffer_api.allocated(ticket,release=False):
  try:return _start(item,preparation,path,platforms,approved,ticket)
  except Exception:
   buffer_api.release_publish(ticket);raise

def _start(item,preparation,path,platforms,approved,ticket):
 if not approved or not item['quality']['can_approve']:raise ValueError('Review and approve the current video first.')
 if preparation['fingerprint']!=item['quality']['fingerprint']:raise ValueError('Video changed since preparation. Review it again.')
 if not isinstance(platforms,list) or not platforms or len(set(platforms))!=len(platforms) or any(p not in EXPECTED for p in platforms):raise ValueError('Choose valid publishing destinations.')
 if not status()['ready']:raise ValueError('Finish Buffer and video hosting setup first.')
 preparation={**preparation,'description':captions.clean(preparation['description'])}
 if len(preparation['description'])>2200:raise ValueError('For all three platforms, keep the caption within 2,200 characters.')
 remote=remote_history(force=True)
 # A failed platform attempt is retryable only after Buffer confirms it failed.
 failures=[r for r in rows() if r['item']==item['id'] and r['fingerprint']==item['quality']['fingerprint'] and r['platform'] in platforms and r['state']=='failed' and r['remote_id']]
 for failed in failures:
  result=buffer_api.query('{post(input:{id:'+json.dumps(failed['remote_id'])+'}){'+FIELDS+'}}')['post']
  verified=apply_remote(failed['id'],result)
  if not verified or result.get('status')!='error':raise ValueError('This platform has not confirmed a failed attempt. Refresh its status first.')
 validate_channels(platforms)
 fingerprint=item['quality']['fingerprint'];pending=[];duplicate_media=[]
 digest=publishing.media_digest(path)
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  for platform in platforms:
   prior=check_duplicates(item,platform,remote)
   if prior:continue
   # Existing direct YouTube uploads are authoritative, including uncertain attempts.
   if platform=='youtube':
    with publishing.connect() as old:
     previous=old.execute("SELECT * FROM publications WHERE item=? AND fingerprint=? AND (url IS NOT NULL OR state IN ('uploading','needs_reconciliation'))",(item['id'],fingerprint)).fetchone()
    if previous:continue
   row=c.execute('SELECT * FROM platform_posts WHERE item=? AND fingerprint=? AND platform=?',(item['id'],fingerprint,platform)).fetchone()
   if row:
    if ((row['state']=='blocked' and not row['remote_id']) or row['state']=='failed') and publishing.claim(c,platform,digest,row['id']):
     c.execute("UPDATE platform_posts SET state='queued',error=NULL,remote_id=NULL,url=NULL,submitted_at=NULL,title=?,description=?,path=? WHERE id=?",(preparation['title'],preparation['description'],str(path),row['id']));pending.append(row['id'])
    continue # Remote/uncertain attempts are never submitted twice.
   id=uuid.uuid4().hex
   if not publishing.claim(c,platform,digest,id):
    duplicate_media.append(platform);continue
   c.execute('INSERT INTO platform_posts(id,item,fingerprint,platform,title,description,state,path) VALUES(?,?,?,?,?,?,?,?)',(id,item['id'],fingerprint,platform,preparation['title'],preparation['description'],'queued',str(path)))
   pending.append(id)
 if pending:threading.Thread(target=run,args=(pending,Path(path),fingerprint,ticket),daemon=True).start()
 else:buffer_api.release_publish(ticket)
 return {'started':len(pending),'posts':rows(),'warnings':['Same video file already has a submission for '+', '.join(duplicate_media)+'. Check the original receipt; a new caption does not create a new video.'] if duplicate_media else []}

def scheduling_cfg():
 try:
  cfg=json.loads((BASE/'posting-slots.json').read_text())
  return cfg if cfg.get('enabled') is True else None
 except (OSError,ValueError):return None

def at_capacity(c,id):
 # With scheduling on, Buffer's free plan holds ~10 scheduled posts per channel. Extra approved posts wait as 'queued' and go up as slots free.
 cfg=scheduling_cfg()
 if not cfg:return False
 r=c.execute('SELECT platform FROM platform_posts WHERE id=?',(id,)).fetchone()
 if not r:return False
 held=c.execute("SELECT count(*) FROM platform_posts WHERE platform=? AND state IN ('scheduled','sending','submitting','hosting')",(r[0],)).fetchone()[0]
 return held>=int(cfg.get('buffer_queue_limit',9))

def drain_waiting():
 # Called from sync(): send approved-but-waiting posts when capacity frees (studio must be open).
 if not scheduling_cfg():return
 with connect() as c:
  waiting=[dict(r) for r in c.execute("SELECT * FROM platform_posts WHERE state='queued' AND remote_id IS NULL AND path IS NOT NULL ORDER BY created")]
 groups={}
 for r in waiting:groups.setdefault((r['path'],r['fingerprint']),[]).append(r['id'])
 for (path,fp),ids in groups.items():
  if Path(path).is_file():threading.Thread(target=_run,args=(ids,Path(path),fp),daemon=True).start()

def run(ids,path,fingerprint,ticket=None):
 with buffer_api.allocated(ticket):
  _run(ids,path,fingerprint)

def _run(ids,path,fingerprint):
 with LOCK:
  # Claim only unsent work. Replayed worker calls cannot re-submit accepted posts.
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   ids=[id for id in ids if not at_capacity(c,id) and c.execute("UPDATE platform_posts SET state='hosting' WHERE id=? AND state='queued' AND remote_id IS NULL",(id,)).rowcount]
  if not ids:return
  try:
   if quality.inspect(path.parent)['fingerprint']!=fingerprint:raise ValueError('Video changed after approval. Review the current version.')
   with connect() as c:platforms=[r[0] for r in c.execute('SELECT platform FROM platform_posts WHERE id IN ('+','.join('?' for _ in ids)+')',ids)]
   validate_channels(platforms,force=False)
   with connect() as c:cached=c.execute('SELECT url FROM delivery_hosts WHERE fingerprint=?',(fingerprint,)).fetchone()
   if cached:url=cached['url']
   else:
    delivery,digest=delivery_video.prepare(path,fingerprint)
    result=cloudinary_host.upload_video(delivery,digest);url=result['url']
    with connect() as c:c.execute('INSERT OR IGNORE INTO delivery_hosts VALUES(?,?)',(fingerprint,url))
  except Exception as e:
   for id in ids:update(id,state='blocked',error=str(e))
   return
  for id in ids:
   with connect() as c:row=dict(c.execute('SELECT * FROM platform_posts WHERE id=?',(id,)).fetchone())
   update(id,state='submitting',error=None,submitted_at=now())
   try:apply_remote(id,create_remote(row['platform'],row['title'],row['description'],url))
   except buffer_api.NotSubmittedError as e:
    update(id,state='blocked',error=str(e))
   except Exception as e:
    # A timeout can occur after Buffer accepted a post. Do not submit again automatically.
    update(id,state='needs_reconciliation',error='Check Buffer before retrying: '+str(e))

SYNC_LAST=0
def sync():
 global SYNC_LAST
 with LOCK:
  reconcile_local()
  try:drain_waiting()
  except Exception:pass
  if time.time()-SYNC_LAST<60:return status()
  SYNC_LAST=time.time()
  pending=[r for r in rows() if r['remote_id'] and r['state'] not in ('published','failed','draft')]
  if not pending:return status()
  # One batched query avoids spending a request for each platform.
  query='{'+''.join('p'+str(i)+':post(input:{id:'+json.dumps(r['remote_id'])+'}){'+FIELDS+'}' for i,r in enumerate(pending))+'}'
  results=buffer_api.query(query)
  for i,row in enumerate(pending):apply_remote(row['id'],results.get('p'+str(i)))
 return status()

HISTORY_LOCK=threading.Lock()
def remote_history(force=False):
 with HISTORY_LOCK:return _remote_history(force)

def _remote_history(force=False):
 """Read the account's posts. No polling loop; owner refresh is rate-limited."""
 cache=BASE/'buffer-history.json'
 try:cached=json.loads(cache.read_text())
 except (OSError,ValueError):cached={}
 if time.time()-cached.get('fetched',0)<(900 if force else 21600):return cached
 organizations=buffer_api.query('{account{organizations{id}}}')['account']['organizations']
 all_posts=[]
 for org in organizations:
  after=None
  for page in range(10):
   result=buffer_api.query('query($input:PostsInput!,$after:String){posts(input:$input,first:100,after:$after){edges{node{'+FIELDS+' metrics{type value unit} metricsUpdatedAt}} pageInfo{hasNextPage endCursor}}}',{'input':{'organizationId':org['id'],'filter':{'channelIds':list(EXPECTED.values())}},'after':after})['posts']
   all_posts.extend(edge['node'] for edge in result.get('edges') or [])
   if not result['pageInfo']['hasNextPage']:break
   after=result['pageInfo']['endCursor']
  else:raise ValueError('Too much remote history to check safely; no posts submitted.')
 result={'fetched':time.time(),'posts':all_posts,'checked_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 temp=cache.with_suffix('.pending');temp.write_text(json.dumps(result));temp.replace(cache)
 try:
  import audience_learning
  audience_learning.ingest_buffer(result,EXPECTED,db=DB)
 except Exception:pass # Analytics history must not interfere with duplicate checks or publication.
 return result

def social_status():
 try:data=json.loads((BASE/'buffer-history.json').read_text())
 except (OSError,ValueError):data={}
 networks={}
 for platform in EXPECTED:
  posts=[]
  for p in sorted(data.get('posts',[]),key=lambda p:p.get('sentAt') or p.get('createdAt') or '',reverse=True):
   if p.get('channelService')!=platform or p.get('channelId')!=EXPECTED[platform]:continue
   metrics={m['type']:m['value'] for m in p.get('metrics') or []}
   if 'likes' not in metrics and 'reactions' in metrics:metrics['likes']=metrics['reactions']
   posts.append({'title':p['text'][:100],'state':'Published' if p['status']=='sent' and public_link(platform,p.get('externalLink')) else ('needs_reconciliation' if p['status']=='sent' else p['status']),'url':p.get('externalLink'),'remote_checked_at':data.get('checked_at'),**{k:metrics.get(k) for k in ('views','likes','comments')}})
  # Local submissions may not have appeared in the remote history cache yet.
  known={p.get('url') for p in posts if p.get('url')}
  for r in rows():
   if r['platform']==platform and (not r['url'] or r['url'] not in known):posts.append(r)
  networks[platform]={'connected':status()['networks'][platform]['connected'],'account':'ShelfMade' if platform=='youtube' else 'shelfmade.daily','posts':posts,'message':'No posts returned by Buffer yet. Older posts made outside Buffer may be unavailable.','refresh_mode':'buffer'}
 return {'checked_at':data.get('checked_at'),'networks':networks,'source':'Buffer API','note':'Metrics are reported by Buffer and may be delayed; unavailable values are shown as —.'}

def check_duplicates(item,platform,remote):
 import csv,re
 normalize=lambda s:re.sub('[^a-z0-9]','',s.lower().replace(' · new local draft',''))
 title=normalize(item['title'])
 # A new generated rendition is not a duplicate merely because its book title matches.
 if item.get('generated'):return None
 tracker=Path.home()/'Documents'/'ContentEmpire-Studio'/'POSTING_TRACKER.csv'
 if tracker.exists():
  with tracker.open() as f:
   for row in csv.DictReader(f):
    if row.get('platform')==platform and normalize(row.get('video',''))==title and row.get('url'):return row['url']
 for p in remote.get('posts',[]):
  if p.get('channelId')==EXPECTED[platform] and p['channelService']==platform and p['status']!='error' and title and title in normalize(p['text']):return p.get('externalLink') or 'Already present in Buffer'
 return None

def recover_interrupted():
 with connect() as c:
  c.execute("UPDATE platform_posts SET state='blocked',error='Studio restarted before platform submission. Safe to retry.' WHERE ((state='queued' AND (path IS NULL OR ?)) OR state='hosting') AND remote_id IS NULL",(0 if scheduling_cfg() else 1,))
  c.execute("UPDATE platform_posts SET state='needs_reconciliation',error='Studio restarted during submission. Refresh status before retrying.' WHERE state='submitting'")

def availability(items):
 try:remote=json.loads((BASE/'buffer-history.json').read_text())
 except (OSError,ValueError):remote={'posts':[]}
 result={}
 attempts=rows()
 legacy=publishing.list_posts()
 for item in items:
  result[item['id']]={p:check_duplicates(item,p,remote) for p in EXPECTED}
  for attempt in attempts:
   if attempt['item']==item['id'] and attempt['fingerprint']==item['quality']['fingerprint'] and attempt['state'] not in ('failed','blocked'):
    result[item['id']][attempt['platform']]=attempt['url'] or 'Pending status check'
  prior=next((p for p in legacy if p['item']==item['id'] and p['fingerprint']==item['quality']['fingerprint'] and (p.get('url') or p['state'] in ('uploading','needs_reconciliation'))),None)
  if prior:result[item['id']]['youtube']=prior.get('url') or 'Pending status check'
 return result

def within_attempt(row,post):
 try:
  started=datetime.datetime.fromisoformat((row['submitted_at'] or row['created']).replace('Z','+00:00'))
  created=datetime.datetime.fromisoformat(post['createdAt'].replace('Z','+00:00'))
  if started.tzinfo is None:started=started.replace(tzinfo=datetime.timezone.utc)
  return started-datetime.timedelta(minutes=2)<=created<=started+datetime.timedelta(hours=2)
 except (ValueError,TypeError,KeyError):return False

def reconcile_local():
 """Never resubmit: recover a known remote post or prove a local rejection."""
 try:remote=json.loads((BASE/'buffer-history.json').read_text()).get('posts',[])
 except (OSError,ValueError):remote=[]
 for row in rows():
  if row['state']!='needs_reconciliation' or row['remote_id']:continue
  with connect() as c:
   host=c.execute('SELECT url FROM delivery_hosts WHERE fingerprint=?',(row['fingerprint'],)).fetchone()
  candidates=[p for p in remote if p.get('channelId')==EXPECTED[row['platform']] and p.get('channelService')==row['platform'] and within_attempt(row,p) and host and any(a.get('source')==host['url'] for a in p.get('assets') or []) and captions.clean(p.get('text',''))==captions.clean(row['description'])]
  if len(candidates)==1:
   apply_remote(row['id'],candidates[0]);continue
  if not candidates and 'Daily Buffer request allowance reached.' in (row['error'] or ''):
   update(row['id'],state='blocked',error='Not submitted: the local API allowance was exhausted. Safe to retry after reviewing the destinations.')

def refresh_connections_if_due():
 try:
  data=json.loads((buffer_api.PRIVATE/'channels.json').read_text())
  import datetime
  if time.time()-datetime.datetime.fromisoformat(data['verified_at']).timestamp()<21600:return
 except (OSError,ValueError,KeyError):pass
 buffer_api.verify()
