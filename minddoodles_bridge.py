"""Separate MindDoodles adapter: no imports of its studio package or shared credentials."""
import hashlib,json,re,urllib.request,urllib.error,threading,os,time
from pathlib import Path
ROOT=Path.home()/'Documents'/'minddoodles-studio'
UI=Path(__file__).resolve().parent.parent/'content-empire-studio'
PLATFORMS=('youtube','instagram','tiktok')
_fingerprints={}
_fingerprint_lock=threading.Lock()
PROTECTED={'published','uploading','processing','submitted','unknown','uploaded_private','uploaded_unlisted','failed_submitted'}
BUFFER_PRIVATE=Path(__file__).resolve().parent/'private-animationdoodles-buffer'
BUFFER_HANDLES={'instagram':'animationdoodleshq','tiktok':'animationdoodleshq'}
BUFFER_FORBIDDEN_IDS=frozenset({'6acef48c778b240e2f0201d8','6acef38d778b240e2f01f97b','6acef41b778b240e2f01fe44','6ad2d9d4778b240e2f33343d','6ad2d979778b240e2f3330c9','6ad2da89778b240e2f333abd'})
_BUFFER_VERIFY_LOCK=threading.Lock()

def _buffer_query(token,document):
 req=urllib.request.Request('https://api.buffer.com',json.dumps({'query':document}).encode(),{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=20) as response:raw=response.read(1024*1024+1)
  if len(raw)>1024*1024:raise ValueError()
  result=json.loads(raw)
  if not isinstance(result,dict) or result.get('errors') or not isinstance(result.get('data'),dict):raise ValueError()
  return result['data']
 except Exception:raise ValueError('Buffer could not verify this key. Check its account and channel read access; no key was saved.') from None

def _buffer_private_dir():
 if BUFFER_PRIVATE.is_symlink():raise ValueError('AnimationDoodles private Buffer storage is unsafe.')
 BUFFER_PRIVATE.mkdir(mode=0o700,exist_ok=True);BUFFER_PRIVATE.chmod(0o700)
 if not BUFFER_PRIVATE.is_dir():raise ValueError('AnimationDoodles private Buffer storage is unavailable.')

def buffer_connection_status():
 empty={'brand':'minddoodles','connected':False,'publishing_ready':False,'channels':[],'message':'Connect a separate AnimationDoodles Buffer key to verify Instagram and TikTok.'}
 try:
  p=BUFFER_PRIVATE/'connection.json'
  if BUFFER_PRIVATE.is_symlink() or p.is_symlink() or not p.is_file() or BUFFER_PRIVATE.stat().st_mode&0o077 or p.stat().st_mode&0o077:return empty
  saved=json.loads(p.read_text());channels=saved.get('channels')
  if saved.get('brand')!='minddoodles' or not isinstance(saved.get('token'),str) or not saved['token'] or not isinstance(channels,list):return empty
  if {x.get('platform'):x.get('handle') for x in channels}!=BUFFER_HANDLES:return empty
  return {'brand':'minddoodles','connected':True,'publishing_ready':False,'channels':channels,'verified_at':saved.get('verified_at'),'verification_scope':'Buffer account/channel reads only; AnimationDoodles publishing is not yet routed through Buffer','message':'AnimationDoodles Instagram and TikTok were verified in its own Buffer account. Publishing still needs to be connected to this route.'}
 except (OSError,ValueError,TypeError,KeyError):return empty

def connect_animationdoodles_buffer(token):
 if not isinstance(token,str) or not re.fullmatch(r'[!-~]{20,512}',token.strip()) or any(x in token for x in ('•','…','***')):raise ValueError('Paste the full AnimationDoodles Buffer API key.')
 token=token.strip()
 with _BUFFER_VERIFY_LOCK:
  data=_buffer_query(token,'{account {organizations {id}}}')
  try:orgs=data['account']['organizations'];ids=[o['id'] for o in orgs]
  except (KeyError,TypeError):raise ValueError('Buffer did not return an organization. No key was saved.') from None
  if not isinstance(ids,list) or not 1<=len(ids)<=3 or any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',i) for i in ids):raise ValueError('Buffer organization list was unexpected. No key was saved.')
  matches=[]
  for org in ids:
   rows=_buffer_query(token,'{channels(input:{organizationId:'+json.dumps(org)+'}){id name displayName service isDisconnected isLocked}}').get('channels')
   if not isinstance(rows,list) or len(rows)>100:raise ValueError('Buffer returned unexpected channel data. No key was saved.')
   found=[]
   for platform,handle in BUFFER_HANDLES.items():
    candidates=[]
    for row in rows:
     if not isinstance(row,dict) or row.get('id') in BUFFER_FORBIDDEN_IDS:continue
     names=[str(row.get(k,'')) for k in ('name','displayName')]
     normalized={re.sub(r'[^a-z0-9]','',n.lower().removeprefix('@')) for n in names}
     if row.get('service')==platform and any(handle in name for name in normalized):candidates.append(row)
    if len(candidates)!=1:break
    row=candidates[0]
    if row.get('isDisconnected') is not False or row.get('isLocked') is not False:raise ValueError('An AnimationDoodles Buffer channel is disconnected or locked. Reconnect it in Buffer first; no key was saved.')
    found.append({'platform':platform,'id':row['id'],'handle':handle})
   if len(found)==2:matches.append((org,found))
  if len(matches)!=1:raise ValueError('Could not identify exactly one AnimationDoodles Instagram and TikTok channel in a single Buffer organization. Confirm both exact handles are connected to this Buffer account; no key was saved.')
  org,channels=matches[0];_buffer_private_dir();path=BUFFER_PRIVATE/'connection.json';tmp=BUFFER_PRIVATE/'connection.pending'
  if path.is_symlink() or tmp.is_symlink():raise ValueError('AnimationDoodles private Buffer storage is unsafe.')
  fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w') as out:
   json.dump({'brand':'minddoodles','token':token,'organization':org,'channels':channels,'verified_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},out);out.flush();os.fsync(out.fileno())
  os.replace(tmp,path);path.chmod(0o600)
 return buffer_connection_status()

def buffer_publishing_status():
 import minddoodles_buffer_publish
 return minddoodles_buffer_publish.status()
def identity(value):
 if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:-\d+)?',value):raise ValueError('Choose a MindDoodles day')
 return value

def package(pid):
 p=ROOT/'data/days'/identity(pid)/'package.json'
 if p.is_symlink() or not p.resolve().is_relative_to((ROOT/'data/days').resolve()):raise ValueError('Unavailable package')
 d=json.loads(p.read_text())
 if d.get('id')!=pid:raise ValueError('Package identity mismatch')
 return d

def video_path(pid,key):
 p=package(pid)
 if key=='long':item=p.get('long',{})
 elif re.fullmatch(r'short[1-3]',key):item=(p.get('shorts') or [])[int(key[-1])-1]
 else:raise ValueError('Choose one video')
 if item.get('review_removed') is True:raise ValueError('This Short was removed from review')
 root=(ROOT/'data/days'/identity(pid)).resolve();path=(root/item.get('video','')).resolve()
 if not path.is_relative_to(root) or not path.is_file() or path.suffix!='.mp4':raise ValueError('Video not ready')
 return path

def fingerprint(pid):
 d=package(pid);metadata=json.dumps({k:d.get(k) for k in ['long','shorts']},sort_keys=True).encode();paths=[]
 for key in ['long']+['short'+str(i+1) for i in range(len(d.get('shorts',[])))]:
  try:
   v=video_path(pid,key);st=v.stat();paths.append((v,st.st_size,st.st_mtime_ns,st.st_ctime_ns))
  except (ValueError,IndexError):paths.append((None,0,0,0))
 signature=(hashlib.sha256(metadata).hexdigest(),tuple(paths))
 with _fingerprint_lock:
  if _fingerprints.get(pid,())[0:1]==(signature,):return _fingerprints[pid][1]
 h=hashlib.sha256(metadata)
 for v,*stats in paths:
  if v is None:h.update(b'missing-video');continue
  with v.open('rb') as f:
   for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 result=h.hexdigest()
 with _fingerprint_lock:_fingerprints[pid]=(signature,result)
 return result

def item_fingerprint(pid,key):
 d=package(pid);item=d['long'] if key=='long' else d['shorts'][int(key[5:])-1]
 h=hashlib.sha256(json.dumps(item,sort_keys=True).encode())
 with video_path(pid,key).open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()

def snapshot():
 connections={p:False for p in PLATFORMS}
 try:
  s=json.loads((ROOT/'data/secrets.json').read_text())
  connections={p:bool(s.get(k)) for p,k in [('youtube','YOUTUBE_REFRESH_TOKEN'),('instagram','INSTAGRAM_ACCESS_TOKEN'),('tiktok','TIKTOK_ACCESS_TOKEN')]}
 except (OSError,ValueError):pass
 accounts={}
 try:
  cached=json.loads((ROOT/'data/accounts/verified.json').read_text())
  accounts={p:{'verified':v.get('verified') is True,'account':str(v.get('account',''))[:120]} for p,v in cached.items() if p in PLATFORMS and isinstance(v,dict)}
 except (OSError,ValueError):pass
 rows=[]
 for f in sorted((ROOT/'data/days').glob('*/package.json'),reverse=True)[:60]:
  try:
   d=package(f.parent.name);items=[]
   for key,item in [('long',d.get('long',{}))]+[('short'+str(i+1),x) for i,x in enumerate(d.get('shorts',[])[:3])]:
    if not item:continue
    if item.get('review_removed') is True:continue
    try:ready=video_path(d['id'],key).is_file()
    except (ValueError,IndexError):ready=False
    results=[]
    for platform,st in d.get('publish',{}).get(key,{}).items():
     if platform not in PLATFORMS:continue
     url=st.get('url','');allowed=url.startswith(('https://youtube.com/','https://www.youtube.com/','https://www.instagram.com/','https://www.tiktok.com/'))
     results.append({'platform':platform,'state':st.get('status','pending'),'url':url if allowed else '', 'has_receipt':bool(st.get('id') or st.get('container_id')), 'checked_at':st.get('checked_at'), 'message':str(st.get('check_message',''))[:280], 'needs_attention':bool(st.get('error'))})
    try:
     import minddoodles_buffer_publish
     for saved in minddoodles_buffer_publish.records():
      if saved.get('package_id')==d['id'] and saved.get('key')==key:
       url=saved.get('url','');allowed=url.startswith(('https://www.instagram.com/','https://www.tiktok.com/'))
       results=[r for r in results if r.get('platform')!=saved.get('platform')]
       results.append({'platform':saved['platform'],'state':saved.get('state','unknown'),'url':url if allowed else '', 'has_receipt':bool(saved.get('remote_id')),'checked_at':saved.get('checked_at') or saved.get('created_at'),'message':str(saved.get('message',''))[:280],'needs_attention':saved.get('state') in ('failed','unknown')})
    except Exception:pass
    items.append({'key':key,'title':str(item.get('title','Untitled'))[:200],'ready':ready,'seconds':item.get('length'),'results':results,'learning_note':item.get('learning_note'),'renderer':item.get('renderer'),'caption':str(item.get('full_description' if key=='long' else 'full_caption',''))[:5000],'review_note':str(item.get('review_note',''))[:600]})
   rows.append({'id':d['id'],'status':d.get('status'),'mode':d.get('mode','earlier explainer'),'step':str(d.get('progress',{}).get('step',''))[:200],'items':items,'fingerprint':fingerprint(d['id']),'error':bool(d.get('error'))})
  except (OSError,ValueError,KeyError,IndexError):continue
 return {'brand':'minddoodles','installed':ROOT.is_dir(),'connections':connections,'accounts':accounts,'packages':rows,'native_url':'http://localhost:8777','direction':'Original comedy + one practical takeaway. No copied scripts, clips or promises of virality.'}

def remove_review_short(pid,key,confirmed=False):
 """Hide an unpublished Short from review and retain a recoverable local copy."""
 if confirmed is not True:raise ValueError('Confirm removing this Short from review.')
 pid=identity(pid)
 if not isinstance(key,str) or not re.fullmatch(r'short[1-3]',key):raise ValueError('Choose one of the three Shorts.')
 d=package(pid)
 if d.get('status') not in ('ready','approved'):raise ValueError('Only a finished Short can be removed from review.')
 index=int(key[-1])-1;items=d.get('shorts') or []
 if index>=len(items):raise ValueError('This Short is unavailable.')
 item=items[index]
 if item.get('review_removed') is True:raise ValueError('This Short was already removed from review.')
 states=(d.get('publish') or {}).get(key,{})
 for row in states.values():
  if not isinstance(row,dict) or row.get('status','pending')!='pending' or any(row.get(k) for k in ('id','container_id','upload_session','url','receipt')):
   raise ValueError('This Short has a publishing record; it is protected from deletion.')
 source=video_path(pid,key);day=(ROOT/'data/days'/pid).resolve()
 if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(day):raise ValueError('The Short file is unavailable or unsafe.')
 recovery=day/'.removed-from-review'/f'{key}-{source.name}'
 if recovery.exists() or recovery.is_symlink():raise ValueError('A recovery copy already exists for this Short.')
 recovery.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 source.replace(recovery)
 item['review_removed']=True;item['review_removed_at']=int(time.time())
 package_file=day/'package.json';tmp=package_file.with_name(package_file.name+'.remove.tmp')
 try:
  with tmp.open('w') as stream:
   json.dump(d,stream,indent=2);stream.flush();os.fsync(stream.fileno())
  os.replace(tmp,package_file)
 except Exception:
  try:tmp.unlink()
  except OSError:pass
  if recovery.exists() and not source.exists():recovery.replace(source)
  raise
 with _fingerprint_lock:_fingerprints.pop(pid,None)
 return {'id':pid,'key':key,'state':'removed_from_review','message':'Short removed from review. A recoverable local copy and its publishing history are preserved.'}

def production_snapshot():
 try:
  with urllib.request.urlopen('http://127.0.0.1:8777/api/production',timeout=2) as response:
   raw=response.read(200001)
  if len(raw)>200000:raise ValueError()
  data=json.loads(raw)
  if data.get('brand')!='minddoodles' or data.get('schema')!=1:raise ValueError()
  return {k:data.get(k) for k in ('brand','schema','day','timezone','targets','strategy','capability','today','history')}
 except Exception:
  return {'brand':'minddoodles','today':None,'history':[],'capability':{'state':'service_update_needed','automatic_video_generation':False,'message':'Restart MindDoodles to activate the saved daily production plan. Its previous videos and receipts are preserved.'}}

def account_setup_snapshot():
 """Return only non-secret account setup metadata to the authenticated shared UI."""
 try:
  with urllib.request.urlopen('http://127.0.0.1:8777/api/settings',timeout=3) as response:
   raw=response.read(50001)
  if len(raw)>50000:raise ValueError()
  data=json.loads(raw);keys=data.get('secrets') or {};redirects=data.get('redirects') or {}
  with urllib.request.urlopen('http://127.0.0.1:8777/api/accounts',timeout=3) as response:
   accounts=json.loads(response.read(20001))
  return {'brand':'minddoodles','connections':accounts,
   'youtube':{'client_id':str(keys.get('YOUTUBE_CLIENT_ID',''))[:300], 'client_secret_saved':bool(str(keys.get('YOUTUBE_CLIENT_SECRET','')).startswith('••••')),'redirect_uri':str(redirects.get('youtube',''))[:300]},
   'instagram':{'user_id':str(keys.get('INSTAGRAM_USER_ID',''))[:120], 'access_token_saved':bool(str(keys.get('INSTAGRAM_ACCESS_TOKEN','')).startswith('••••'))},
   'tiktok':{'client_key':str(keys.get('TIKTOK_CLIENT_KEY',''))[:300], 'client_secret_saved':bool(str(keys.get('TIKTOK_CLIENT_SECRET','')).startswith('••••')),'redirect_uri':str(redirects.get('tiktok',''))[:300]},
   'buffer':buffer_connection_status(),'buffer_publishing':buffer_publishing_status()}
 except Exception:
  raise ValueError('MindDoodles account setup is unavailable. Check that its local service is running.') from None

def action(body):
 if not isinstance(body,dict) or body.get('brand')!='minddoodles':raise ValueError('Explicit MindDoodles request required')
 kind=body.get('action')
 if kind=='connect-buffer':
  if set(body)!={'brand','action','token'}:raise ValueError('Choose only the AnimationDoodles Buffer connection.')
  return connect_animationdoodles_buffer(body.get('token'))
 if kind=='save-buffer-hosting':
  if set(body)!={'brand','action','cloud_name','api_key','api_secret'}:raise ValueError('Choose only AnimationDoodles video-host fields.')
  import minddoodles_buffer_publish
  return minddoodles_buffer_publish.save_hosting({k:body[k] for k in ('cloud_name','api_key','api_secret')})
 if kind=='publish-buffer-shorts':
  if set(body)!={'brand','action','id','fingerprint','reviewed','selection'} or body.get('reviewed') is not True:raise ValueError('Confirm review of these exact Shorts before publishing.')
  pid=identity(body.get('id'));d=package(pid)
  if body.get('fingerprint')!=fingerprint(pid):raise ValueError('This video package changed. Refresh and review it again.')
  selection=body.get('selection')
  if not isinstance(selection,dict) or not selection:raise ValueError('Choose at least one destination.')
  import minddoodles_buffer_publish
  if not minddoodles_buffer_publish.status().get('publishing_ready'):raise ValueError('Finish AnimationDoodles Buffer and separate video-host setup in Accounts & setup first.')
  for key,platforms in selection.items():
   if not isinstance(key,str) or not re.fullmatch(r'short[1-3]',key) or not isinstance(platforms,list) or not platforms:raise ValueError('Buffer publishing is available for reviewed Shorts only.')
   try:item=d.get('shorts',[])[int(key[-1])-1]
   except IndexError:raise ValueError('This Short is unavailable.') from None
   if item.get('review_removed') is True:raise ValueError('This Short was removed from review.')
   for platform in platforms:
    if platform not in ('instagram','tiktok'):raise ValueError('Choose Instagram or TikTok for the Buffer publishing route.')
    old=(d.get('publish',{}).get(key,{}) or {}).get(platform,{})
    if old.get('status','pending')!='pending' or old.get('id') or old.get('container_id'):raise ValueError('An existing submission is protected. Check its result instead of resubmitting.')
  outcomes=[]
  for key,platforms in selection.items():
   item=d['shorts'][int(key[-1])-1]
   for platform in platforms:
    result=minddoodles_buffer_publish.publish(platform,str(item.get('title',''))[:100],str(item.get('full_caption',''))[:2200],video_path(pid,key),item_fingerprint(pid,key),pid,key)
    outcomes.append({'key':key,'platform':platform,'state':result.get('state','unknown')})
  return {'ok':True,'message':'Selected Short(s) were sent to AnimationDoodles Buffer. Check the saved results before retrying.','results':outcomes}
 if kind=='admit-creator-short':
  if set(body)!={'brand','action','id'}:raise ValueError('Choose only this saved Short for review.')
  return admit_creator_short(body.get('id'))
 if kind=='create-short':return short_creator().create(body)
 if kind=='resume-short':return short_creator().resume(body.get('id'))
 if kind=='remove-short':return short_creator().remove(body.get('id'),body.get('confirmed'))
 if kind=='remove-reviewed-short':return remove_review_short(body.get('id'),body.get('key'),body.get('confirmed'))
 if kind=='render-action-test':return short_creator().start_action_test(body)
 if kind=='render-local-action-preview':return short_creator().start_local_action_preview(body)
 if kind=='build-speech':
  import minddoodles_identity
  minddoodles_identity.validate_speech_source()
  path='/api/speech/build';payload={'scene':'hands-free-v1'}
 elif kind=='verify-accounts':
  path='/api/accounts/verify';payload={}
 elif kind=='save-account-settings':
  allowed={'YOUTUBE_CLIENT_ID','YOUTUBE_CLIENT_SECRET','INSTAGRAM_USER_ID','INSTAGRAM_ACCESS_TOKEN','TIKTOK_CLIENT_KEY','TIKTOK_CLIENT_SECRET'}
  values=body.get('secrets',{})
  if not isinstance(values,dict) or set(values)-allowed:raise ValueError('Choose only MindDoodles account setup fields.')
  if any(not isinstance(v,str) or len(v)>5000 for v in values.values()):raise ValueError('One of the account fields is too long.')
  path='/api/settings';payload={'secrets':{k:v.strip() for k,v in values.items() if v.strip()}}
 elif kind=='check':
  pid=identity(body.get('id'))
  import minddoodles_buffer_publish
  buffer_posts=minddoodles_buffer_publish.check(pid)
  d=package(pid)
  native_pending=any(v.get('id') or v.get('container_id') for row in d.get('publish',{}).values() for v in row.values())
  if buffer_posts and not native_pending:return {'ok':True,'message':'Buffer results checked. Refresh the page to see the latest status.'}
  path='/api/package/'+pid+'/check';payload={}
 elif kind=='prepare-production':
  path='/api/production/prepare';payload={'topic':str(body.get('topic','')).strip()[:200]}
 elif kind=='generate':
  raise ValueError('Use the approved Leo/Mia production plan. Substitute puppet and 3D renderers are disabled for new production.')
 elif kind in ('approve','rebuild'):
  pid=identity(body.get('id'));d=package(pid)
  if body.get('fingerprint')!=fingerprint(pid):raise ValueError('This version changed. Refresh and review again.')
  if kind=='approve':
   if body.get('reviewed') is not True:raise ValueError('Review the exact videos before publishing')
   if d.get('status') not in ('ready','approved'):raise ValueError('Wait for generation to finish')
   selection=body.get('selection',{})
   if not isinstance(selection,dict) or not any(selection.values()):raise ValueError('Choose destinations')
   state=snapshot()
   for key,plats in selection.items():
    if key not in d.get('publish',{}) or not isinstance(plats,list):raise ValueError('Unknown video')
    for plat in plats:
     if plat not in PLATFORMS or (key=='long' and plat!='youtube'):raise ValueError('Invalid destination')
     if d['publish'][key].get(plat,{}).get('status') in PROTECTED:raise ValueError('Existing submission preserved; check results instead')
   payload={'mode':'now','selection':selection,'edits':{},'reviewed':True,'review_fingerprints':{k:item_fingerprint(pid,k) for k,v in selection.items() if v}}
  else:
   if any(v.get('status') in (PROTECTED|{'scheduled'}) for row in d.get('publish',{}).values() for v in row.values()):raise ValueError('Existing submissions are preserved. Create a new day instead.')
   payload={}
  path=f'/api/package/{pid}/{kind}'
 else:raise ValueError('Unknown MindDoodles action')
 try:
  with urllib.request.urlopen('http://127.0.0.1:8777/api/version',timeout=3) as response:version=json.loads(response.read(4096))
  expected={'minddoodles-reference-v6','minddoodles-reference-v7','minddoodles-reference-v8'} if kind in ('approve','check','verify-accounts','build-speech') else ({'minddoodles-reference-v3','minddoodles-reference-v4','minddoodles-reference-v5','minddoodles-reference-v6','minddoodles-reference-v7','minddoodles-reference-v8'} if kind=='prepare-production' else {'minddoodles-creative-v2','minddoodles-reference-v3','minddoodles-reference-v4','minddoodles-reference-v5','minddoodles-reference-v6','minddoodles-reference-v7','minddoodles-reference-v8'})
  if version.get('build') not in expected:raise ValueError()
  if kind=='build-speech' and version.get('build') not in ('minddoodles-reference-v7','minddoodles-reference-v8'):raise ValueError()
 except Exception:raise ValueError('Restart MindDoodles to load its publishing safeguards before using this action.') from None
 req=urllib.request.Request('http://127.0.0.1:8777'+path,data=json.dumps(payload).encode(),method='POST',headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8777'})
 try:
  with urllib.request.urlopen(req,timeout=8) as response:data=json.loads(response.read(100000))
  message=('Existing checked scene reused. Open it in your review library.' if kind=='build-speech' and data.get('state')=='ready_for_review' else 'Corrected job prepared. Free GPU execution is a private cloud handoff; no old renderer was started.' if kind=='build-speech' else 'Account verification complete. Refresh Accounts & setup for each destination.' if kind=='verify-accounts' else 'MindDoodles account settings saved on this Mac.' if kind=='save-account-settings' else 'Existing submissions checked. No new upload was made.' if kind=='check' else 'Daily plan saved. Script, reference frames and automated rendering are the next development stages.' if kind=='prepare-production' else 'MindDoodles accepted the request. Refresh to check progress.')
  return {'ok':True,'message':message,'id':data.get('id')}
 except urllib.error.HTTPError as error:
  try:message=json.loads(error.read(4096)).get('error','')
  except Exception:message=''
  if isinstance(message,str) and message.startswith(('Connect and verify','This video or caption changed','Existing submission preserved','Review this exact','Choose explicit publishing')):raise ValueError(message) from None
  raise ValueError('MindDoodles could not complete this action. Inspect its saved status; no retry was sent.') from None
 except Exception:raise ValueError('MindDoodles did not confirm this request. Check its own dashboard before retrying; restart both studios after this update.') from None

def stream(handler,pid,key):
 return stream_path(handler,video_path(pid,key))

def stream_path(handler,path):
 size=path.stat().st_size;start,end,status=0,size-1,200
 value=handler.headers.get('Range')
 if value:
  try:
   a,b=value.removeprefix('bytes=').split('-');start=int(a) if a else max(0,size-int(b));end=min(int(b),size-1) if a and b else size-1
   if not 0<=start<=end<size:raise ValueError()
   status=206
  except ValueError:return handler.send('',status=416,extra={'Content-Range':f'bytes */{size}'})
 handler.send_response(status)
 for name,val in [('Content-Type','video/mp4'),('Content-Length',str(end-start+1)),('Accept-Ranges','bytes'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]:handler.send_header(name,val)
 if status==206:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
 handler.end_headers()
 with path.open('rb') as f:
  f.seek(start);left=end-start+1
  try:
   while left:
    chunk=f.read(min(65536,left))
    if not chunk:break
    handler.wfile.write(chunk);left-=len(chunk)
  except (BrokenPipeError,ConnectionResetError):pass


def quality_snapshot():
 """Read-only release status; does not load models or read account secrets."""
 import importlib.util
 path=UI.parent/'minddoodles-production/production_release.py'
 try:
  spec=importlib.util.spec_from_file_location('_minddoodles_production_release',path)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  result=module.evaluate()
  result['development']=development_snapshot()
  return result
 except (OSError,ValueError,ImportError,AttributeError):
  return {'schema':1,'brand':'minddoodles','state':'quality_status_unavailable','new_full_build_allowed':False,'message':'The full-episode quality check is unavailable. Do not start a long render until its release evidence is available.','reasons':[]}

def development_snapshot(root=None,now=None):
 """Bounded local status only. No credential reads or provider requests."""
 import time,math
 root=Path(root) if root is not None else UI.parent/'minddoodles-production'
 now=time.time() if now is None else now
 def read(relative):
  path=root/relative
  if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size>100000:raise ValueError('Unavailable status')
  value=json.loads(path.read_text())
  if not isinstance(value,dict):raise ValueError('Invalid status')
  return value
 result={'source':'saved_local_observation','automatic_provider_polling':False,'character_test':{'state':'unavailable','message':'No saved character-test observation is available.'},'local_build':{'state':'not_started','message':'No supervised full build has started.'}}
 try:
  saved=read('leo-texture-v4/provider-state.json');checked=saved.get('checked_at')
  if type(checked) not in (int,float) or not math.isfinite(checked) or checked>now+60:raise ValueError()
  status=saved.get('provider_status');states={'queued':'Waiting in Kaggle’s queue; no start time is provided.','running':'Kaggle reports the character test is running.','complete':'Kaggle reports the test ended; inspect its collected result.','error':'Kaggle reports a test error.','cancelled':'The character test was cancelled.'}
  if status not in states:raise ValueError()
  result['character_test']={'state':status,'message':states[status],'checked_at':checked,'stale':now-checked>120,'character':'Leo','finished_video':False}
  try:
   collection=read('leo-texture-v4/Collection-report.json')
   if collection.get('state')=='trial_failed':result['character_test'].update(state='failed',message='The character test stopped. Diagnostics are saved; no accepted model was produced.')
   elif collection.get('state')=='downloaded_needs_visual_review':result['character_test'].update(state='needs_visual_review',message='Leo’s textured head was collected and still needs appearance review.')
  except (OSError,ValueError,TypeError):pass
 except (OSError,ValueError,TypeError):pass
 try:
  pointer=read('production-control/latest.json');ident=pointer['run_id']
  if not isinstance(ident,str) or not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError()
  state=read('production-control/runs/'+ident+'/status.json')
  if state.get('brand')!='minddoodles' or state.get('run_id')!=ident:raise ValueError()
  messages={'starting':'Starting the accepted local build.','running':'Local build is running.','total_budget_reached':'The total build-time budget was reached. Completed files are preserved.','worker_failed':'The local build stopped with an error. Completed files are preserved.','stopped_by_request':'The build was stopped by request.','supervisor_interrupted':'The build supervisor was interrupted; inspect its saved log.','worker_completed_needs_output_checks':'The build process ended. Output and owner review are still required.'}
  status=state.get('state')
  if status not in messages:raise ValueError()
  result['local_build']={'state':status,'message':messages[status]}
  for name in ['elapsed_seconds','budget_seconds','completed_shots']:
   value=state.get(name)
   if type(value) in (int,float) and math.isfinite(value) and value>=0:result['local_build'][name]=value
  if status in ('starting','running'):
   started=state.get('started_at');elapsed=state.get('elapsed_seconds')
   if type(started) not in (int,float) or type(elapsed) not in (int,float) or not math.isfinite(started+elapsed) or now-(started+elapsed)>30:
    result['local_build'].update(state='observation_stale',message='The saved build status is no longer updating. Inspect the build log before treating it as running or starting another build.')
 except (OSError,ValueError,KeyError,TypeError):pass
 return result


_short_creator_module=None
def short_creator():
 global _short_creator_module
 if _short_creator_module is None:
  import importlib.util
  spec=importlib.util.spec_from_file_location('_md_short_creator',UI.parent/'minddoodles-production/short_creator/service.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);_short_creator_module=module
 return _short_creator_module

def admit_creator_short(job_id):
 """Copy one verified creator render into the native Shorts owner-review queue."""
 if not isinstance(job_id,str) or not re.fullmatch(r'[a-f0-9]{32}',job_id):
  raise ValueError('Choose a saved AnimationDoodles Short.')
 creator=short_creator();status=creator.read(job_id)
 if status.get('id')!=job_id or status.get('state')!='ready' or status.get('published') is not False:
  raise ValueError('Only an unpublished Short marked ready for visual review can be opened here.')
 job_root=creator.folder(job_id)
 if job_root.is_symlink() or not job_root.is_dir():raise ValueError('The saved Short folder is unavailable or unsafe.')
 root=job_root.resolve()
 def read_job_json(relative):
  path=root/relative
  if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
   raise ValueError('The saved Short is missing a required review check.')
  try:return json.loads(path.read_text())
  except (OSError,ValueError):raise ValueError('The saved Short has an unreadable review check.') from None
 def job_file(relative):
  path=root/relative
  if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
   raise ValueError('The saved Short video is missing or unsafe.')
  return path
 def digest(path):
  h=hashlib.sha256()
  with path.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
  return h.hexdigest()
 video=job_file('Review.mp4');checks=read_job_json('Checks.json');assembly=read_job_json('Assembly.json')
 prepared=read_job_json('Prepared.json');report=read_job_json('provider-output/flashhead-review/report.json')
 if report.get('state')!='render_returned_needs_eye_review' or report.get('approved') is not False or report.get('publishing') is not False:
  raise ValueError('This render has not passed its private owner-review checks.')
 if assembly.get('published') is not False or assembly.get('new_dialogue') is not True or assembly.get('story_specific_action_clips_used') is not True:
  raise ValueError('The saved build is not a new, unpublished story Short.')
 if assembly.get('video')!=str(video) or checks.get('sha256')!=digest(video):
  raise ValueError('The saved video changed after its review checks. Refresh before continuing.')
 required=('exact_words','action_sound_cues_verified','three_approved_story_action_clips_verified',
  'story_specific_action_edit_verified','generic_music_removed','provider_speaking_clips_preserved_byte_for_byte',
  'original_provider_eye_motion_preserved','mouth_unchanged_by_eye_processing','owner_visual_review_required')
 if not all(checks.get(flag) is True for flag in required):
  raise ValueError('The saved Short is missing a required dialogue, action, or visual-review check.')
 script=status.get('script');prepared_script=prepared.get('script')
 if not isinstance(script,dict) or prepared_script!=script or not isinstance(prepared.get('voices'),list):
  raise ValueError('The saved dialogue does not match its prepared voice tracks.')
 voices={row.get('actor'):row for row in prepared['voices'] if isinstance(row,dict)}
 if set(voices)!={'Leo','Mia'} or any(voices[name].get('text')!=script.get(name.lower()) for name in ('Leo','Mia')):
  raise ValueError('The saved dialogue does not match its prepared voice tracks.')
 normalize=lambda value:re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]','',str(value).lower())).strip()
 expected=' '.join(script[name] for name in ('leo','mia'))
 if normalize(checks.get('expected',''))!=normalize(expected) or normalize(checks.get('heard',''))!=normalize(expected):
  raise ValueError('The audio transcript does not match the dialogue in the saved Short.')
 pinned=creator.verify_pinned_action_assets(job_id,script.get('recipe'))
 scene_rows=assembly.get('story_action_assets')
 if not isinstance(scene_rows,list) or len(scene_rows)!=3 or any(
  scene_rows[i].get('scene_id')!=pinned[i].get('scene_id') or scene_rows[i].get('sha256')!=pinned[i].get('sha256')
  for i in range(3)):
  raise ValueError('The saved story action clips do not match this Short.')
 clip_frames=0
 for actor in ('Leo','Mia'):
  clip_checks=read_job_json(actor+'-checks.json');clip=job_file(actor+'-ready.mp4');actual=digest(clip)
  if clip_checks.get('provider_video_copied_byte_for_byte') is not True or clip_checks.get('provider_video_sha256')!=actual or clip_checks.get('ready_video_sha256')!=actual:
   raise ValueError('A saved speaking clip differs from its checked provider video.')
  clip_frames+=creator.validate_action_clip(clip,1)['frames']
 cues=(assembly.get('sound_design') or {}).get('cues')
 if not isinstance(cues,list) or not cues:raise ValueError('The Short has no checked story-action sound cues.')
 actions=[];sounds=[]
 for index,cue in enumerate(cues):
  start=cue.get('time_seconds');duration=cue.get('duration_seconds');action=cue.get('action')
  if type(start) not in (int,float) or type(duration) not in (int,float) or not isinstance(action,str):
   raise ValueError('The saved story-action sound cues are invalid.')
  end=start+duration;cue_id=action+'-'+str(index+1)
  actions.append({'id':cue_id,'start':start,'end':end,'sound_required':True})
  sounds.append({'action':cue_id,'start':start,'end':end})
 digest_value=digest(video);seconds=checks.get('seconds')
 if type(seconds) not in (int,float) or not 5<=seconds<=60 or checks.get('decoded_frames',0)<2:
  raise ValueError('The saved file is outside the supported 5–60 second Shorts range.')
 starts=assembly.get('voice_starts') or {}
 if any(type(starts.get(actor)) not in (int,float) or type(voices[actor].get('seconds')) not in (int,float) for actor in ('Leo','Mia')):
  raise ValueError('The saved dialogue timing is incomplete.')
 performance={'schema':2,'seconds':seconds,'video_sha256':digest_value,'lip_sync_verified':False,
  'speech':[{'actor':actor,'text':voices[actor].get('text'),'start':starts.get(actor),
             'end':starts.get(actor)+voices[actor].get('seconds',0)} for actor in ('Leo','Mia')],
  'speech_animation':{'backend':'flashhead-provider-clips-v1','state':'rendered_for_owner_review',
   'video_sha256':digest_value,'audio_script_checked':True,'generated_speech_frames':clip_frames,
   'provider_clips_preserved_byte_for_byte':True,'exact_transcript_recognized':True},
  'actions':actions,'sounds':sounds}
 import importlib.util,sys
 # The shared dashboard may already have an unrelated top-level `studio`
 # module loaded. Load the native review package under a private name so its
 # package-relative imports resolve to this exact installation.
 native_package=ROOT/'studio'
 package_name='_minddoodles_native_studio'
 dependencies=ROOT/'.venv'/f'lib/python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
 if dependencies.is_dir() and str(dependencies) not in sys.path:sys.path.insert(0,str(dependencies))
 if package_name not in sys.modules:
  package_spec=importlib.util.spec_from_file_location(package_name,native_package/'__init__.py',submodule_search_locations=[str(native_package)])
  if not package_spec or not package_spec.loader:raise ValueError('The Shorts review package is unavailable.')
  package=importlib.util.module_from_spec(package_spec);sys.modules[package_name]=package;package_spec.loader.exec_module(package)
 module_name=package_name+'.review_short'
 review_module=sys.modules.get(module_name)
 if review_module is None:
  review_spec=importlib.util.spec_from_file_location(module_name,native_package/'review_short.py')
  if not review_spec or not review_spec.loader:raise ValueError('The Shorts review module is unavailable.')
  review_module=importlib.util.module_from_spec(review_spec);sys.modules[module_name]=review_module;review_spec.loader.exec_module(review_module)
 admit=review_module.admit
 title=str(script.get('title',''))[:100]
 caption='Leo’s breakfast budget hits an unexpected cost. Would you have spotted it?'
 provenance='AnimationDoodles private creator render '+job_id+'; exact transcript, source action clips and sound cues checked. Provider eye motion is preserved; final visual and lip-sync review is still required.'
 pkg=admit(video,title=title,caption=caption,provenance=provenance,performance=performance,
  hashtags=['#AnimationDoodles','#Budgeting','#ComedyShorts'])
 return {'ok':True,'package_id':pkg['id'],'review_url':'/studio/minddoodles?view=shorts&review='+str(pkg['id']),
  'message':'Short added to Shorts review only. Watch the copied video, choose verified destinations, then approve to publish.'}

def action_package(recipe):
 import importlib.util,sys
 source=UI.parent/'minddoodles-production/short_creator/action_package.py'
 sys.path.insert(0,str(source.parent))
 spec=importlib.util.spec_from_file_location('_md_action_package',source)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.build_package(recipe)

def short_stream(handler,job):
 path=short_creator().media(job)
 return stream_path(handler,path)

def action_test_stream(handler,job):
 path=short_creator().action_test_media(job)
 return stream_path(handler,path)

def local_action_preview_stream(handler,attempt_id):
 path=short_creator().local_action_preview_media(attempt_id)
 return stream_path(handler,path)

def lipsync_pilot_stream(handler):
 """Serve the fixed, local-only one-shot mouth-sync pilot for review."""
 root=(UI.parent/'minddoodles-production'/'coffee-break-50'/'repair-v2'/'face-polish-v1').resolve()
 path=root/'shot-05-wav2lip.mp4'
 if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root) or path.stat().st_size>10_000_000:
  raise ValueError('Local lip-sync sample is unavailable or unsafe.')
 return stream_path(handler,path)

def coffee_break_review_stream(handler):
 """Serve the existing repaired 50-second draft for local owner review only."""
 root=(UI.parent/'minddoodles-production'/'coffee-break-50'/'repair-v2'/'assembly-work'/'review').resolve()
 path=root/'Leo-Mia-The-Five-Second-Coffee-Break-50s.mp4'
 if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root) or path.stat().st_size>30_000_000:
  raise ValueError('Coffee Break review video is unavailable or unsafe.')
 return stream_path(handler,path)
