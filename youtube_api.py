import captions
"""Direct YouTube upload. Tokens remain local; channels are verified before upload."""
import json,time,os,urllib.request,urllib.parse,urllib.error,threading
from pathlib import Path
import publishing
BASE=Path(__file__).resolve().parent;AUTH=BASE/'private-google';EXPECTED='UCI4dLh_Uz4HrNq7NOetzbxQ'
def save_private(path,data):
 AUTH.mkdir(mode=0o700,exist_ok=True);AUTH.chmod(0o700)
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:json.dump(data,f)
 path.chmod(0o600)
def request(url,data=None,headers=None,method=None):
 req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
 try:return urllib.request.urlopen(req,timeout=120)
 except urllib.error.HTTPError as e:
  if e.code==308:return e
  raise RuntimeError('Google request failed (HTTP '+str(e.code)+'). Reconnect or check YouTube API configuration.') from None

def token():
 try:stored=json.loads((AUTH/'tokens.json').read_text());client=json.loads((AUTH/'client.json').read_text())['installed']
 except (OSError,ValueError,KeyError):raise ValueError('Connect YouTube from the laptop first.')
 if stored.get('expires_at',0)>time.time()+60:return stored['access_token']
 if not stored.get('refresh_token'):raise ValueError('YouTube authorization expired. Reconnect on the laptop.')
 payload=urllib.parse.urlencode({'client_id':client['client_id'],'client_secret':client.get('client_secret',''),'refresh_token':stored['refresh_token'],'grant_type':'refresh_token'}).encode()
 with request('https://oauth2.googleapis.com/token',payload,{'Content-Type':'application/x-www-form-urlencoded'}) as r:new=json.load(r)
 stored.update(new);stored['expires_at']=time.time()+new.get('expires_in',3600);save_private(AUTH/'tokens.json',stored);return stored['access_token']

def verify_channel(access_token):
 with request('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',headers={'Authorization':'Bearer '+access_token}) as r:channels=json.load(r).get('items',[])
 if len(channels)!=1 or channels[0]['id']!=EXPECTED:raise ValueError('The authorized channel is not ShelfMade. Reconnect and select the correct channel.')
 return {'id':channels[0]['id'],'title':channels[0]['snippet']['title']}
def status():
 try:c=json.loads((AUTH/'channel.json').read_text());connected=c.get('id')==EXPECTED and (AUTH/'tokens.json').exists()
 except (OSError,ValueError):c={};connected=False
 return {'connected':connected,'channel':c.get('title','ShelfMade'),'client_configured':(AUTH/'client.json').exists(),'dashboard_can_upload':connected,'mode':'YouTube API' if connected else 'Google setup required'}

def connect_db():
 c=publishing.connect()
 columns={r[1] for r in c.execute('PRAGMA table_info(publications)')}
 for name in ('upload_session','visibility','audience','thumbnail_state','thumbnail_error','upload_size'):
  if name not in columns:
   try:c.execute('ALTER TABLE publications ADD COLUMN '+name+' TEXT')
   except publishing.sqlite3.OperationalError as e:
    if 'duplicate column' not in str(e):raise
 c.commit();return c

def set_thumbnail(video_id,file,access_token):
 if not file.is_file() or file.stat().st_size>2*1024*1024:raise ValueError('Thumbnail missing or larger than the conservative 2-MiB export limit.')
 kind='image/jpeg' if file.suffix.lower() in ('.jpg','.jpeg') else 'image/png'
 url='https://www.googleapis.com/upload/youtube/v3/thumbnails/set?'+urllib.parse.urlencode({'videoId':video_id,'uploadType':'media'})
 with request(url,file.read_bytes(),{'Authorization':'Bearer '+access_token,'Content-Type':kind}) as r:result=json.load(r)
 if not result.get('items'):raise RuntimeError('YouTube did not confirm the thumbnail.')
 return True

def send_upload(id,file,visibility,made_for_kids,thumbnail=None,publish_at=None):
 with connect_db() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM publications WHERE id=?',(id,)).fetchone()
  if not row:raise ValueError('Prepare this video first.')
  safe_retry=(row['state']=='failed' and not row['upload_session'] and 'Google request failed (HTTP 400)' in (row['error'] or ''))
  if row['state'] not in ('awaiting_publisher','awaiting_connection') and not safe_retry:raise ValueError('This upload was already submitted or its result is uncertain. Check its status instead of creating another.')
  if not status()['connected']:raise ValueError('Connect YouTube on the laptop first.')
  if visibility not in ('public','private','unlisted') or not isinstance(made_for_kids,bool):raise ValueError('Choose audience and visibility.')
  if publish_at is not None:
   import re as _re
   if not isinstance(publish_at,str) or not _re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z',publish_at) or visibility!='public':raise ValueError('Scheduled uploads need a UTC publish time and final visibility public.')
  if 'platform_posts' in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
   other=c.execute("SELECT id FROM platform_posts WHERE item=? AND fingerprint=? AND platform='youtube' AND (remote_id IS NOT NULL OR state NOT IN ('failed','blocked'))",(row['item'],row['fingerprint'])).fetchone()
   if other:raise ValueError('This video already has a YouTube submission through Buffer. Refresh that result instead.')
  digest=publishing.media_digest(file)
  if not publishing.claim(c,'youtube',digest,id):raise ValueError('These video bytes already have a YouTube submission. Check its result instead of submitting a duplicate.')
  c.execute("UPDATE publications SET upload_size=? WHERE id=?",(str(file.stat().st_size),id))
  if publish_at:
   try:c.execute('ALTER TABLE publications ADD COLUMN publish_at TEXT')
   except publishing.sqlite3.OperationalError as e:
    if 'duplicate column' not in str(e):raise
   c.execute('UPDATE publications SET publish_at=? WHERE id=?',(publish_at,id))
  c.execute("UPDATE publications SET state='uploading',visibility=?,audience=?,error=NULL WHERE id=?",(visibility,str(made_for_kids),id))
 def upload():
  submission_started=False
  try:
   access_token=token();verify_channel(access_token)
   size=file.stat().st_size
   if size<=0:raise ValueError('Video is empty.')
   metadata={'snippet':{'title':row['title'],'description':captions.clean(row['description']),'categoryId':'27'},'status':{'privacyStatus':('private' if publish_at else visibility),'selfDeclaredMadeForKids':made_for_kids}}
   if publish_at:metadata['status']['publishAt']=publish_at
   headers={'Authorization':'Bearer '+access_token,'Content-Type':'application/json','X-Upload-Content-Type':'video/mp4','X-Upload-Content-Length':str(size)}
   submission_started=True
   with request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',json.dumps(metadata).encode(),headers) as r:session=r.headers.get('Location','')
   parsed=urllib.parse.urlparse(session)
   if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com') or parsed.username or parsed.password or parsed.port not in (None,443):raise ValueError('Google returned an invalid upload session.')
   with connect_db() as c:c.execute('UPDATE publications SET upload_session=? WHERE id=?',(session,id))
   with file.open('rb') as stream:
    with request(session,stream,{'Authorization':'Bearer '+access_token,'Content-Type':'video/mp4','Content-Length':str(size)},'PUT') as r:
     if r.status==308:raise RuntimeError('Upload incomplete. Keep the upload session for recovery; do not submit a duplicate.')
     result=json.load(r)
   video_id=result.get('id');actual=result.get('status',{}).get('privacyStatus')
   import re
   if not isinstance(video_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id) or result.get('snippet',{}).get('channelId')!=EXPECTED:raise RuntimeError('Upload response could not be verified. Do not submit again.')
   state='published' if actual=='public' and result.get('status',{}).get('uploadStatus')=='processed' else 'processing_'+(actual or 'unknown')
   if result.get('status',{}).get('uploadStatus')=='rejected':state='rejected'
   elif publish_at and actual=='private':state='scheduled'
   with connect_db() as c:c.execute('UPDATE publications SET state=?,url=?,error=NULL WHERE id=?',(state,'https://www.youtube.com/watch?v='+video_id,id))
   if thumbnail and state!='rejected':
    try:
     set_thumbnail(video_id,Path(thumbnail),access_token)
     with connect_db() as c:c.execute("UPDATE publications SET thumbnail_state='uploaded',thumbnail_error=NULL WHERE id=?",(id,))
    except Exception:
     # Never turn a successful video upload into an upload retry because its cover failed.
     with connect_db() as c:c.execute("UPDATE publications SET thumbnail_state='needs_attention',thumbnail_error='Video uploaded. YouTube could not apply the custom thumbnail. Check channel thumbnail eligibility and upload the saved cover in YouTube Studio.' WHERE id=?",(id,))
  except Exception as e:
   with connect_db() as c:
    row2=c.execute('SELECT upload_session FROM publications WHERE id=?',(id,)).fetchone()
    c.execute('UPDATE publications SET state=?,error=? WHERE id=?',('needs_reconciliation' if submission_started or (row2 and row2[0]) else 'failed',str(e),id))
 threading.Thread(target=upload,daemon=True).start()
 return {'status':'uploading','id':id}

def recover_sessions(access_token):
 """An empty status query to the EXISTING Google session; never upload/resume here."""
 with connect_db() as c:pending=[dict(r) for r in c.execute("SELECT * FROM publications WHERE state='needs_reconciliation' AND url IS NULL AND upload_session IS NOT NULL AND upload_size IS NOT NULL")]
 for row in pending:
  parsed=urllib.parse.urlparse(row['upload_session'])
  if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com') or parsed.username or parsed.password or parsed.port not in (None,443):continue
  try:
   size=int(row['upload_size'])
   if size<=0:continue
   with request(row['upload_session'],b'',{'Authorization':'Bearer '+access_token,'Content-Length':'0','Content-Range':'bytes */'+str(size)},'PUT') as response:
    if response.status==308:
     with connect_db() as c:c.execute("UPDATE publications SET error='YouTube confirms the existing upload is incomplete. Check YouTube Studio; a second upload has not been started.' WHERE id=?",(row['id'],))
     continue
    video=json.load(response)
   import re
   video_id=video.get('id');remote=video.get('status',{})
   if not isinstance(video_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id) or video.get('snippet',{}).get('channelId')!=EXPECTED:continue
   state=('published' if remote.get('privacyStatus')=='public' else 'uploaded_'+remote.get('privacyStatus','unknown')) if remote.get('uploadStatus')=='processed' else 'processing_'+remote.get('privacyStatus','unknown')
   if remote.get('uploadStatus') in ('failed','rejected'):state=remote['uploadStatus']
   with connect_db() as c:c.execute("UPDATE publications SET state=?,url=?,error=NULL WHERE id=? AND state='needs_reconciliation'",(state,'https://www.youtube.com/watch?v='+video_id,row['id']))
  except Exception:
   # Expired, missing or ambiguous sessions stay uncertain. No automatic fresh upload.
   with connect_db() as c:c.execute("UPDATE publications SET error='The existing YouTube upload could not be confirmed. Check YouTube Studio before creating another upload.' WHERE id=? AND state='needs_reconciliation'",(row['id'],))

SYNC={'checked_at':None,'error':None}
SYNC_LOCK=threading.Lock()
def sync_publications():
 if not status()['connected']:return {'error':'Connect YouTube first.'}
 if not SYNC_LOCK.acquire(blocking=False):return {'busy':True}
 try:
  import re,datetime
  access_token=token()
  recover_sessions(access_token)
  with connect_db() as c:
   columns={r[1] for r in c.execute('PRAGMA table_info(publications)')}
   for name in ('actual_visibility','remote_checked_at','views','likes','comments','publish_at'):
    if name not in columns:
     try:c.execute('ALTER TABLE publications ADD COLUMN '+name+' TEXT')
     except publishing.sqlite3.OperationalError as e:
      if 'duplicate column' not in str(e):raise
   rows=[dict(r) for r in c.execute('SELECT id,url,publish_at FROM publications WHERE url IS NOT NULL')]
   sched={r['id'] for r in rows if r.get('publish_at')}
  ids={}
  for row in rows:
   parsed=urllib.parse.urlparse(row['url']);video_id=parsed.path.rsplit('/',1)[-1] if '/shorts/' in parsed.path else urllib.parse.parse_qs(parsed.query).get('v',[''])[0]
   if re.fullmatch('[A-Za-z0-9_-]{11}',video_id):ids[video_id]=row['id']
  checked=datetime.datetime.now(datetime.timezone.utc).isoformat()
  observed_videos=[]
  for offset in range(0,len(ids),50):
   batch=list(ids)[offset:offset+50]
   with request('https://www.googleapis.com/youtube/v3/videos?'+urllib.parse.urlencode({'part':'status,snippet,statistics','id':','.join(batch)}),headers={'Authorization':'Bearer '+access_token}) as r:data=json.load(r)
   observed_videos.extend(data.get('items',[]))
   with connect_db() as c:
    for video in data.get('items',[]):
     if video.get('snippet',{}).get('channelId')!=EXPECTED:continue
     remote=video.get('status',{});privacy=remote.get('privacyStatus','unknown');upload=remote.get('uploadStatus','unknown')
     state=('published' if privacy=='public' else 'uploaded_'+privacy) if upload=='processed' else 'processing_'+privacy
     if upload in ('failed','rejected'):state=upload
     if privacy=='private' and upload=='processed' and ids[video['id']] in sched:state='scheduled'
     c.execute('UPDATE publications SET state=?,actual_visibility=?,remote_checked_at=?,views=?,likes=?,comments=?,error=NULL WHERE id=?',(state,privacy,checked,video.get('statistics',{}).get('viewCount'),video.get('statistics',{}).get('likeCount'),video.get('statistics',{}).get('commentCount'),ids[video['id']]))
  try:
   import audience_learning
   for video in observed_videos:audience_learning.ingest_youtube(video,checked,EXPECTED,db=publishing.DB)
  except Exception:pass # Saved publication state has priority over optional analytics.
  SYNC.update(checked_at=checked,error=None);return dict(SYNC)
 except Exception as e:SYNC['error']=str(e);return dict(SYNC)
 finally:SYNC_LOCK.release()
def start_monitor():
 def loop():
  while True:
   sync_publications();time.sleep(120)
 threading.Thread(target=loop,daemon=True).start()


def recover_interrupted():
 """Startup never creates another upload for an interrupted request."""
 with connect_db() as c:
  c.execute("UPDATE publications SET state='needs_reconciliation',error='Studio restarted during upload. Refresh status or check YouTube Studio before trying another upload.' WHERE state='uploading'")
