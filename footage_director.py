"""Free stock-video acquisition and auditable chapter briefs. No paid or generic fallback.
Semantic matching is a lexical editorial heuristic; every visual remains reviewable.
"""
import json,re,hashlib,sqlite3,time,urllib.request,urllib.parse,subprocess,os,math,shutil
from pathlib import Path
import media_runtime

# A stock clip may be reused once it is this many days old (0 or less = never reuse). Shared by ShelfMade and MindLore.
REUSE_DAYS=float(os.environ.get('FOOTAGE_REUSE_DAYS','10'))
def reuse_cutoff():
 return time.time()-REUSE_DAYS*86400 if REUSE_DAYS>0 else 0
BASE=Path(__file__).resolve().parent
CACHE=BASE/'footage-cache';DB=BASE/'footage-history.sqlite3'
LOCAL_CACHE=BASE/'local-video-cache';LOCAL_CACHE.mkdir(exist_ok=True)
MAX_SEARCHES=30;MAX_SEARCH_PAGES=10;MAX_BYTES=5*1024*1024*1024
MAX_LOCAL_CACHE_GB=50
# Themes translate narrated concepts into concrete filmable subjects, not literal historical claims.
BRIEFS=[
 ('control',('control','power','anger','response','judgment','insult'),['person thinking window','person writing journal reflection','person walking busy city']),
 ('learning',('knowledge','truth','reason','belief','learn','education','educational','student','students','teacher','teaching','mentorship','mentoring','studied','intellectual','mind','concentration','understanding','wisdom','wise','shadow','shadows','cave','reality'),['person examining object close up','reading book library','student writing notes','scientist observing microscope','hands turning book pages','person studying library','person drawing diagram']),
 ('nature',('nature','woods','forest','pond','lake','simplicity','simple','simpler','quiet'),['walking forest sunlight','forest stream rocks','small cabin nature']),
 ('time',('time','hour','mortality','death','day','attention'),['clock hands close up','person commuting city','person watching sunset','calendar planning schedule','hands setting alarm clock','morning routine breakfast','person checking wristwatch','hourglass sand close up','writing weekly planner','train station commuters']),
 ('practice',('habit','practice','discipline','effort','character','work'),['hands practicing craft','person training climbing','hands writing daily journal']),
 ('community',('people','friend','duty','society','kindness','justice','benefit','benefits'),['people listening conversation','people helping each other','family sharing meal','volunteers packing food','neighbors working together garden','friends talking cafe','person carrying groceries neighbor']),
 ('choice',('choice','choose','decision','desire','freedom','virtue'),['person writing journal decision','person standing doorway','person walking fork road','person thinking window','person crossroads walking','hands making decision']),
 ('strategy',('war','battle','enemy','strategy','victory','planning'),['chess hands planning move','martial arts practice','person drawing plan']),
 ('wealth',('wealth','money','opportunity','poverty','diamond'),['hands repairing old object','person working small workshop','hands planting seeds']),
 ('craft',('carve','carving','carved','sculpture','sculpting','sculptor','drawing'),['sculptor carving wood','hands carving sculpture','artist drawing sketch','woodworker carving detail','sculptor modeling clay','craftsperson carving wood workshop']),
 ('suffering',('pain','suffering','happiness','desire','fear'),['person sitting alone window rain','person walking out into sunlight','hands releasing tension'])]

STORY_BRIEFS=[
 ('sleep',('sleep','dream','dreams','bed','tired','rest','night'),['person sleeping bed night','person yawning morning','bedroom window moonlight','person waking up stretching']),
 ('memory',('memory','remember','forget','forgot','notebook','recall','brain'),['hands writing notes notebook','old photographs close up','person thinking window','person studying notes library']),
 ('workday',('hours','job','productivity','office','desk','busy','boss','career','hustle'),['person working laptop office','person tired at desk','commuters train station','hands typing keyboard','busy office people']),
 ('screens',('phone','scrolling','screen','notifications','internet','online','social'),['person scrolling phone close up','phone notifications close up','person typing message smartphone','person putting phone down']),
 ('alone',('alone','lonely','loneliness','elderly','aging','family','friends'),['elderly person window','person sitting alone park','family dinner table','friends laughing cafe']),
 ('danger',('danger','risk','threat','chase','thrill','scared','afraid'),['storm clouds sky','city night street walking','person standing cliff edge','person looking over shoulder']),
 ('health',('health','stress','calm','breath','body','anxiety','relax'),['person breathing outdoors','person stretching morning','person meditating sunrise','hands releasing tension']),
 ('willpower',('willpower','self','control','resist','temptation','discipline','king','ruler'),['person resisting dessert','person training gym determination','hands closing door','person standing mountain top']),
 ('society',('modern','society','city','crowd','chaos','civilization','violence','trust','neighbors'),['crowded street walking','city traffic timelapse','people crossing street','neighbors talking fence'])]
if os.environ.get('STORY_SCRIPT'):BRIEFS=BRIEFS+STORY_BRIEFS

def key():
 value=os.environ.get('PEXELS_API_KEY','')
 if value:return value
 p=BASE/'private-footage/pexels-key'
 if p.exists():return p.read_text().strip()
 # Reuse only the specifically named existing free-service credential. Never load the env file.
 p=Path.home()/'Dev'/'content-empire'/'demo'/'.env'
 if p.exists():
  for line in p.read_text().splitlines():
   if line.strip().startswith('PEXELS_API_KEY='):return line.split('=',1)[1].strip().strip('\"\'')
 return ''

def connect():
 CACHE.mkdir(exist_ok=True);c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row
 c.executescript('CREATE TABLE IF NOT EXISTS requests(at REAL); CREATE TABLE IF NOT EXISTS searches(query TEXT PRIMARY KEY,created REAL,payload TEXT); CREATE TABLE IF NOT EXISTS used(asset TEXT,package TEXT,created REAL,PRIMARY KEY(asset,package)); CREATE TABLE IF NOT EXISTS reserved(asset TEXT PRIMARY KEY,package TEXT,expires REAL); CREATE TABLE IF NOT EXISTS local_cache(asset_id TEXT PRIMARY KEY,query TEXT,downloaded_at REAL,file_path TEXT,size_bytes INTEGER,access_count INTEGER DEFAULT 0,last_accessed REAL,sha256 TEXT);')
 return c

HINT=''  # set by hook_rules: the real source quote behind a template hook line

def brief(text,chapter='',book=''):
 words=set(re.findall('[a-z]+',text.lower()));context=set(re.findall('[a-z]+',chapter.lower()))
 if HINT and chapter.lower()=='hook':words|=set(re.findall('[a-z]+',HINT.lower()))
 if os.environ.get('STORY_SCRIPT') and not any(x in words for _t,_terms,_q in BRIEFS for x in _terms):words.add('mind')   # story Shorts: abstract sentence -> calm learning/thinking footage
 scored=[(sum(4 for t in terms if t in words)+sum(.25 for t in terms if t in context),theme,queries,[t for t in terms if t in words]) for theme,terms,queries in BRIEFS]
 score,theme,queries,hits=max(scored,key=lambda row:row[0])
 if not hits:raise ValueError('No confident visual brief for: '+chapter+'. Add a specific editorial footage brief instead of generic scenery.')
 # Concrete details in the actual passage take priority over a broad theme.
 subject='theme'
 details=[
  (('mentorship','mentoring','teacher','teaching','educational','student','students','studied'),['teacher helping student','student writing notes','students studying library','teacher explaining classroom'],'education and mentorship'),
  (('insult','message','notification','phone'),['person reading message phone','people listening conversation','person writing journal reflection','phone notifications close up','person typing message smartphone','friends talking cafe','hands writing letter','person putting phone down'],'message and response'),
  (('forest','woods','trees','path'),['walking forest sunlight','forest stream rocks','person observing forest'],'forest attention'),
  (('pond','lake','water','stream'),['water ripples close up','forest stream rocks','person watching lake'],'water observation'),
  (('clock','minutes','hours','commuting'),['clock hands close up','person commuting city','person writing daily schedule','calendar planning schedule','hands setting alarm clock','writing weekly planner','person checking wristwatch','train station commuters'],'time and routine'),
  (('carve','carving','carved','sculpture','sculpting','sculptor'),['sculptor carving wood','hands carving sculpture','artist working sculpture','woodworker carving detail','sculptor modeling clay','craftsperson carving wood workshop'],'carving and sculpture'),
  (('benefit','benefits'),['people helping each other','person carrying groceries neighbor','volunteers sharing food'],'practical help'),
  (('practice','craft','repair','workshop'),['hands practicing craft','person working small workshop','hands repairing old object'],'practical work'),
  (('shadow','shadows','cave'),['person shadow wall light','sunlight entering dark room','person examining object close up'],'shadow and light')]
 for keys,concrete,label in details:
  if label=='practical help' and theme!='community':continue
  if words.intersection(keys):queries=concrete;subject=label;break
 return {'theme':theme,'subject':subject,'queries':queries,'keywords':hits,'reason':'Illustrative '+theme+' imagery anchored to '+', '.join(hits),'review_required':True,'book':book,'chapter':chapter}

def search(query,page=1):
 cache_key=query if page==1 else query+' [page '+str(page)+']'
 with connect() as c:
  old=c.execute('select created,payload from searches where query=?',(cache_key,)).fetchone()
  if old and time.time()-old['created']<86400:return json.loads(old['payload'])
  c.execute('BEGIN IMMEDIATE')
  if c.execute('select count(*) from requests where at>?',(time.time()-3600,)).fetchone()[0]>=300:raise ValueError('Free footage hourly search budget reached; try later.')
  import footage_budget
  footage_budget.reserve(c,DB)
 token=key()
 if not token:raise ValueError('Connect the free Pexels footage key; fresh footage is required. No old-clip fallback was used.')
 url='https://api.pexels.com/videos/search?'+urllib.parse.urlencode({'query':query,'orientation':'landscape','size':'medium','per_page':80,'page':page})
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':token,'User-Agent':'ShelfMade/1.0'}),timeout=30) as r:data=json.load(r)
 except Exception as error:
  import generation_recovery
  if generation_recovery.transient(error):raise generation_recovery.RecoverableGenerationError('Free footage provider is temporarily unavailable; completed work is saved.','provider_unavailable') from None
  raise ValueError('Free footage search failed. Check the Pexels connection or quota; old footage was not substituted.') from None
 with connect() as c:c.execute('insert or replace into searches values (?,?,?)',(cache_key,time.time(),json.dumps(data)))
 return data

def download_video(source_path,asset_id):
 """Copy an already validated download into the local reuse cache.

 The main footage download has already fetched and probed this asset. Copying
 that file avoids a second provider transfer and stores cache metadata in the
 eight-column local_cache table.
 """
 source_path=Path(source_path);LOCAL_CACHE.mkdir(parents=True,exist_ok=True)
 local_path=LOCAL_CACHE/(asset_id+'.mp4')
 if local_path.is_file() and local_path.stat().st_size>0:
  with connect() as c:
   row=c.execute('SELECT size_bytes FROM local_cache WHERE asset_id=?',(asset_id,)).fetchone()
   if row and local_path.stat().st_size==row['size_bytes']:
    c.execute('UPDATE local_cache SET access_count=access_count+1,last_accessed=? WHERE asset_id=?',(time.time(),asset_id))
    return local_path
  local_path.unlink(missing_ok=True)
 if not source_path.is_file() or source_path.stat().st_size<=0:
  raise ValueError('Cannot cache a missing or empty source video.')
 part=local_path.with_suffix('.mp4.part')
 try:
  shutil.copyfile(source_path,part)
  size=part.stat().st_size
  if size!=source_path.stat().st_size or size<=0:raise ValueError('Local cache copy failed size verification.')
  digest=hashlib.sha256()
  with part.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
  sha256=digest.hexdigest();part.replace(local_path);now=time.time()
  with connect() as c:
   c.execute('INSERT OR REPLACE INTO local_cache (asset_id,query,downloaded_at,file_path,size_bytes,access_count,last_accessed,sha256) VALUES (?,?,?,?,?,?,?,?)',(asset_id,'pexels-download',now,str(local_path),size,1,now,sha256))
  cleanup_old_cache()
  return local_path
 except Exception:
  part.unlink(missing_ok=True)
  raise

def get_cached_video(asset_id):
 """Check if video is cached locally and return path if available."""
 with connect() as c:
  row=c.execute('SELECT file_path,size_bytes,access_count FROM local_cache WHERE asset_id=?',(asset_id,)).fetchone()
  if row:
    path=Path(row['file_path'])
    if path.is_file() and path.stat().st_size==row['size_bytes'] and row['size_bytes']>0:
     c.execute('UPDATE local_cache SET access_count=access_count+1,last_accessed=? WHERE asset_id=?',(time.time(),asset_id))
     return path
    c.execute('DELETE FROM local_cache WHERE asset_id=?',(asset_id,))
    try:path.unlink(missing_ok=True)
    except OSError:pass
 return None

def cleanup_old_cache():
 """Remove least recently used files if cache exceeds limit."""
 total_size=0
 with connect() as c:
  for row in c.execute('SELECT asset_id,file_path,size_bytes FROM local_cache'):
   path=Path(row['file_path'])
   if path.exists():
    total_size+=row['size_bytes']
  max_bytes=MAX_LOCAL_CACHE_GB*1024*1024*1024
  if total_size<=max_bytes:return
 with connect() as c:
   for row in c.execute('SELECT asset_id,file_path FROM local_cache ORDER BY last_accessed ASC'):
    if total_size<=max_bytes:break
    path=Path(row['file_path'])
    if path.exists():
     try:total_size-=path.stat().st_size;path.unlink();c.execute('DELETE FROM local_cache WHERE asset_id=?',(row['asset_id'],))
     except OSError:pass

def used_ids(package=None):
 result=set()
 with connect() as c:result.update(r[0] for r in c.execute('select distinct asset from used where created>?',(reuse_cutoff(),)));result.update(r[0] for r in c.execute('select asset from reserved where expires>? and package!=?',(time.time(),str(package or ''))))
 # Include completed package manifests, including a crash after completion but before ledger recording.
 for root in [BASE/'full-generated',BASE/'generated',BASE/'replacements',BASE.parent/'content-empire-studio/rebuilds/kokoro-heart-v1',BASE.parent/'content-empire-studio/daily-generated']:
  for p in root.glob('**/footage-selection.json'):
   try:
    if (p.parent/'POST_THIS.txt').exists() and (p.parent/'POST_THIS.txt').stat().st_mtime>reuse_cutoff():result.update(a['id'] for a in json.loads(p.read_text())['assets'])
   except (OSError,ValueError,KeyError):pass
 return result

def dataless(p):
 """True for an iCloud placeholder (content not on this Mac). stat never triggers a download; reading would hang."""
 try:return bool(os.stat(p).st_flags & 0x40000000)
 except (OSError,AttributeError):return False

def historical_hashes(identifiers):
 result=set()
 for ident in identifiers:
  if not re.fullmatch(r'pexels-[0-9]+',ident) or dataless(CACHE/(ident+'.json')):continue
  try:result.add(json.loads((CACHE/(ident+'.json')).read_text())['sha256'])
  except (OSError,ValueError,KeyError):pass
 # Exact file identity also catches legacy clips whose provider IDs were never recorded.
 cache=CACHE/'legacy-hashes.json'
 try:old=json.loads(cache.read_text())
 except (OSError,ValueError):old={}
 for a in json.loads((BASE/'cinematic-assets.json').read_text()):
  path=Path(a['path'])
  if not path.exists():continue
  stamp=str(path.stat().st_size)+':'+str(path.stat().st_mtime_ns);entry=old.get(str(path),{})
  if entry.get('stamp')!=stamp:
   digest=hashlib.sha256()
   with path.open('rb') as source:
    for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
   entry={'stamp':stamp,'sha256':digest.hexdigest()};old[str(path)]=entry
  result.add(entry['sha256'])
 cache.write_text(json.dumps(old));return result

def metadata_match(video,query):
 slug=urllib.parse.urlparse(video.get('url','')).path.lower()
 # Search engines can return homonyms: 'responding' must not become emergency responders.
 if any(word in slug for word in ('ambulance','firetruck','emergency','surgery','weapon','police')):return False
 stop={'person','people','man','woman','hands','hand','close','up','the','a','and','with','on','of','at','in','before','each','other'}
 stem=lambda w: re.sub(r'(ing|ers|er|ed|s)$','',w)
 anchors={stem(w) for w in re.findall('[a-z]+',query.lower()) if w not in stop}
 subject={stem(w) for w in re.findall('[a-z]+',slug) if w not in stop}
 return bool(anchors & subject)

def query_role(query):
 words=set(re.findall('[a-z]+',query.lower()))
 if words.intersection({'hands','hand','close','object','notes','journal','seeds'}):return 'detail'
 if words.intersection({'walking','training','climbing','practicing','helping','conversation'}):return 'action'
 return 'establish'

def download(video,selection,budget):
 ident='pexels-'+str(video['id']);target=CACHE/(ident+'.mp4')
 if invalid_cached_asset(ident) or dataless(target) or dataless(target.with_suffix('.json')):return None
 if not target.exists():
  files=[f for f in video.get('video_files',[]) if f.get('file_type')=='video/mp4' and f.get('width',0)>=1280 and f.get('height',0)>=720 and f.get('width',0)>f.get('height',0)]
  if not files:return None
  f=min(files,key=lambda f:abs(f.get('width',0)-1280));url=f['link'];parsed=urllib.parse.urlparse(url)
  if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.pexels.com'):return None
  local_cached=get_cached_video(ident)
  if local_cached and local_cached.exists():
   try:
    shutil.copy2(local_cached,target)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(target)],check=True,capture_output=True,text=True,timeout=30,env=media_runtime.environment()).stdout)
    stream=next(s for s in probe['streams'] if s['codec_type']=='video');duration=float(probe['format']['duration'])
    if stream['width']<1280 or stream['height']<720 or duration<12:
     target.unlink(missing_ok=True);target.with_suffix('.rejected.json').write_text(json.dumps({'at':time.time(),'reason':'Cached media fails minimum dimensions/duration','duration':duration,'width':stream['width'],'height':stream['height']}));return None
    (target.with_suffix('.json')).write_text(json.dumps({'duration':duration,'width':stream['width'],'height':stream['height'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
    meta=json.loads(target.with_suffix('.json').read_text())
    return {'id':ident,'path':str(target),'duration':meta['duration'],'sha256':meta['sha256'],'tags':selection['keywords']+[selection['theme']],'themes':[selection['theme']],'visual_subject':selection.get('subject','theme'),'description':selection['reason']+'; searched for '+selection['query'],'query':selection['query'],'shot_intent':query_role(selection['query']),'creator':video.get('user',{}).get('name','Pexels contributor'),'creator_url':video.get('user',{}).get('url',''),'source_url':video.get('url',''),'provider':'Pexels','metadata_match':True,'provenance':'Free Pexels stock; illustrative, not historical/location evidence; human relevance review required.'}
   except Exception:target.unlink(missing_ok=True)
  part=target.with_suffix('.part')
  try:
   _dl=time.monotonic()+150
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ShelfMade/1.0'}),timeout=30) as r,part.open('wb') as out:
    while True:
     if time.monotonic()>_dl:raise TimeoutError('slow clip download skipped')
     data=r.read(1024*1024)
     if not data:break
     budget[0]+=len(data)
     if budget[0]>MAX_BYTES:raise ValueError('Fresh footage download budget reached; job stopped without reusing old clips.')
     out.write(data)
   probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(part)],check=True,capture_output=True,text=True,timeout=30,env=media_runtime.environment()).stdout)
   stream=next(s for s in probe['streams'] if s['codec_type']=='video');duration=float(probe['format']['duration'])
   if stream['width']<1280 or stream['height']<720 or duration<12:
    part.unlink(missing_ok=True);target.with_suffix('.rejected.json').write_text(json.dumps({'at':time.time(),'reason':'Actual media fails minimum dimensions/duration','duration':duration,'width':stream['width'],'height':stream['height']}));return None
   part.replace(target)
   try:download_video(target,ident)
   except Exception:pass
  except subprocess.CalledProcessError:
   part.unlink(missing_ok=True)
   runtime=media_runtime.health(force=True)
   if not runtime['ready']:raise media_runtime.MediaRuntimeError(runtime['message'])
   return None
  except ValueError:part.unlink(missing_ok=True);raise
  except Exception:part.unlink(missing_ok=True);return None
  (target.with_suffix('.json')).write_text(json.dumps({'duration':duration,'width':stream['width'],'height':stream['height'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
 meta=json.loads(target.with_suffix('.json').read_text())
 return {'id':ident,'path':str(target),'duration':meta['duration'],'sha256':meta['sha256'],'tags':selection['keywords']+[selection['theme']],'themes':[selection['theme']],'visual_subject':selection.get('subject','theme'),'description':selection['reason']+'; searched for '+selection['query'],'query':selection['query'],'shot_intent':query_role(selection['query']),'creator':video.get('user',{}).get('name','Pexels contributor'),'creator_url':video.get('user',{}).get('url',''),'source_url':video.get('url',''),'provider':'Pexels','metadata_match':True,'provenance':'Free Pexels stock; illustrative, not historical/location evidence; human relevance review required.'}

def search_allowance(remaining,demands):
 """Weight searches by scene demand while reserving a first search for later themes."""
 if not demands or remaining<=0:return 0
 minimum=2 if remaining>=2*len(demands) else 1
 reserve=minimum*(len(demands)-1)
 if remaining<=reserve:return 1
 return min(remaining-reserve,max(minimum,math.ceil(remaining*demands[0]/sum(demands))))

def invalid_cached_asset(ident):
 if dataless(CACHE/(ident+'.rejected.json')):return False
 try:return time.time()-json.loads((CACHE/(ident+'.rejected.json')).read_text())['at']<86400
 except (OSError,ValueError,KeyError,TypeError):return False

def cached_search_page(query,page=1):
 """Fresh cached provider metadata is free to inspect; no request or quota mutation."""
 cache_key=query if page==1 else query+' [page '+str(page)+']'
 with connect() as c:row=c.execute('select created,payload from searches where query=?',(cache_key,)).fetchone()
 if not row or time.time()-row['created']>=86400:return None
 try:
  data=json.loads(row['payload'])
  return data if isinstance(data,dict) and isinstance(data.get('videos'),list) else None
 except (ValueError,TypeError):return None

def cached_page_exhausted(query,page,excluded):
 """Skip a proven-exhausted cached page without spending a search attempt.
 Unknown/expired pages still go through the normal bounded provider request.
 """
 cache_key=query if page==1 else query+' [page '+str(page)+']'
 with connect() as c:row=c.execute('select created,payload from searches where query=?',(cache_key,)).fetchone()
 if not row or time.time()-row['created']>=86400:return False
 try:videos=json.loads(row['payload']).get('videos',[])
 except (ValueError,AttributeError):return False
 return bool(videos) and not any('pexels-'+str(v['id']) not in excluded and not invalid_cached_asset('pexels-'+str(v['id'])) and v.get('duration',0)>=12 and metadata_match(v,query) for v in videos)

def progress_identity(script):
 import full_checkpoint
 return full_checkpoint.digest({'script':script,'briefs':BRIEFS,'direction_version':__import__('scene_direction').VERSION})

def saved_assets(folder,script):
 import full_checkpoint as checkpoint
 try:data=json.loads((Path(folder)/'acquisition-progress.json').read_text())
 except (OSError,ValueError):return []
 if not isinstance(data,dict) or not isinstance(data.get('assets'),list) or data.get('identity')!=progress_identity(script):return []
 result=[];hashes=set()
 for a in data.get('assets',[]):
  try:
   p=Path(a['path'])
   if p.is_symlink() or not p.resolve().is_relative_to(CACHE.resolve()) or not p.is_file() or checkpoint.file_hash(p)!=a['sha256'] or a['sha256'] in hashes:continue
   hashes.add(a['sha256']);result.append(a)
  except (OSError,KeyError,ValueError,TypeError):continue
 return result

def restore_progress(source,folder,script):
 import full_checkpoint as checkpoint
 assets=saved_assets(source,script)
 if not assets:return
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  for a in assets:c.execute('UPDATE reserved SET package=?,expires=? WHERE asset=? AND package=?',(str(Path(folder).resolve()),time.time()+10800,a['id'],str(Path(source).resolve())))
 checkpoint.write(Path(folder)/'acquisition-progress.json',{'identity':progress_identity(script),'assets':assets})

def acquire(script,folder,needed=64,chapters=None):
 media_runtime.require_ready()
 folder=Path(folder)
 if shutil.disk_usage(BASE).free<2*1024**3:raise ValueError('Less than 2 GiB free disk space. Free storage before acquiring fresh footage.')
 book=script.get('book_title',script.get('title',''));briefs=[]
 for s in script['sections']:
  try:b=brief(s['narration'],s['title'],book)
  except ValueError:
   if s['title']=='cta' and briefs:b={**briefs[-1],'chapter':'cta','reason':'Closing continuity with the preceding lesson; review required.'}
   else:raise
  briefs.append(b)
 (folder/'visual-briefs.json').write_text(json.dumps({'version':'fresh-chapter-v1','book':book,'briefs':briefs,'review_required':True},indent=2))
 seen=used_ids(folder.resolve());chosen={};hashes=historical_hashes(seen);budget=[0];queries=0
 try:queries=int(json.loads((folder/'footage-preflight.json').read_text()).get('provider_searches',0))
 except (OSError,ValueError,TypeError):pass
 import full_checkpoint as checkpoint
 for asset in saved_assets(folder,script):
  if asset['id'] in seen or asset['sha256'] in hashes:continue
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   if c.execute('SELECT 1 FROM used WHERE asset=?',(asset['id'],)).fetchone():continue
   other=c.execute('SELECT package FROM reserved WHERE asset=? AND expires>?',(asset['id'],time.time())).fetchone()
   if other and other[0]!=str(folder.resolve()):continue
   c.execute('INSERT OR REPLACE INTO reserved VALUES (?,?,?)',(asset['id'],str(folder.resolve()),time.time()+10800))
  chosen[asset['id']]=asset;hashes.add(asset['sha256'])
 # Two distinct queries per chapter, allocated by its share of narrated words.
 requirements={}
 words=[]
 timing=folder/'.render/word-timing.json'
 if timing.exists():words=json.loads(timing.read_text())['words']
 # Search and editing use the same narration-to-shot decisions, including Shorts without word timing.
 import scene_direction
 timeline=[];cursor=0
 for index,section in enumerate(script['sections']):
  supplied=chapters[index] if chapters else {}
  chapter={'index':index,'title':section['title'],'narration':section['narration'],'start':cursor,'duration':len(section['narration'].split())/2.6,**supplied}
  if section['title']=='cta' and index:chapter.setdefault('visual_context',script['sections'][index-1]['narration'])
  timeline.append(chapter);cursor=chapter['start']+chapter['duration']
 mindlore_full=script.get('brand')=='mindlore' and script.get('format')=='full'
 directions=scene_direction.plan(timeline,words,script.get('content_type')=='short',long_scene_seconds=12 if mindlore_full else 8)
 (folder/'scene-direction.json').write_text(json.dumps(scene_direction.receipt(timeline,words,directions),indent=2))
 for beat in directions:
  unitbrief=beat['visual'];theme=(unitbrief['theme'],unitbrief.get('subject','theme'))
  if theme not in requirements:requirements[theme]=[{**unitbrief,'queries':list(unitbrief['queries'])},0]
  else:
   current=requirements[theme][0]['queries']
   for query in unitbrief['queries']:
    if query not in current:current.append(query)
  requirements[theme][1]+=1
 # Reserve a fair share for later themes rather than exhausting the budget on the first.
 def accept(video,b,query):
  ident='pexels-'+str(video['id'])
  if ident in seen or ident in chosen or video.get('duration',0)<(15 if mindlore_full else 12) or not metadata_match(video,query):return False
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');c.execute('delete from reserved where expires<?',(time.time(),))
   reservation=c.execute('select package from reserved where asset=?',(ident,)).fetchone()
   if reservation and reservation[0]!=str(folder.resolve()):return False
   if c.execute('select 1 from used where asset=? and created>?',(ident,reuse_cutoff())).fetchone():return False
   c.execute('insert or replace into reserved values (?,?,?)',(ident,str(folder.resolve()),time.time()+10800))
  a=download(video,{**b,'query':query},budget)
  if not a or a['sha256'] in hashes:
   with connect() as c:c.execute('delete from reserved where asset=? AND package=?',(ident,str(folder.resolve())))
   return False
  chosen[ident]=a;hashes.add(a['sha256']);checkpoint.write(folder/'acquisition-progress.json',{'identity':progress_identity(script),'assets':list(chosen.values())});return True
 groups=list(requirements.values())
 for index,(b,required) in enumerate(groups):
  # Keep spare candidates in metadata, not extra downloads that waste bandwidth.
  target=required;matching=[a for a in chosen.values() if b['theme'] in a.get('themes',[]) and a.get('visual_subject','theme')==b.get('subject','theme') and a.get('query') in b['queries']];count=len(matching);query_counts={q:sum(a['query']==q for a in matching) for q in b['queries']};deferred=[];exhausted=set()
  if count>=required:continue
  if matching:target=required
  allowance=search_allowance(MAX_SEARCHES-queries,[n for _,n in groups[index:]]);spent=0
  per_query=max(1,math.ceil(target/len(b['queries'])))
  # Prefer different queries before filling gaps from a richer matching search.
  for page in range(1,MAX_SEARCH_PAGES+1):
   for query in b['queries']:
    if count>=target:break
    if query in exhausted:continue
    if cached_page_exhausted(query,page,seen|set(chosen)):continue
    cached=cached_search_page(query,page)
    if cached is None:
     if spent>=allowance or queries>=MAX_SEARCHES:continue
     spent+=1;queries+=1;cached=search(query,page)
    videos=cached.get('videos',[])
    if not videos:exhausted.add(query);continue
    for video in videos:
     if count>=target:break
     if query_counts.get(query,0)>=per_query:deferred.append((video,query));continue
     if accept(video,b,query):count+=1;query_counts[query]=query_counts.get(query,0)+1
   if count<target:
    for video,query in deferred:
     if count>=target:break
     if accept(video,b,query):count+=1
    deferred=[]
   if count>=target:break
  if count<required:
   (folder/'footage-shortage.json').write_text(json.dumps({'theme':b['theme'],'subject':b.get('subject','theme'),'required':required,'found':count,'queries':b['queries'],'provider_searches':queries,'group_provider_searches':spent,'max_provider_searches':MAX_SEARCHES,'review_required':True},indent=2))
   from generation_recovery import RecoverableGenerationError
   raise RecoverableGenerationError('Not enough fresh footage for theme: '+b['theme']+'. Found '+str(count)+' of '+str(required)+' required distinct matching clips. Completed work is saved for bounded recovery.','footage_shortage')
 assets=list(chosen.values())
 (folder/'footage-selection.json').write_text(json.dumps({'version':'fresh-chapter-v1','assets':assets,'searches':queries,'downloaded_bytes':budget[0],'previously_used_excluded':len(seen),'review_required':True},indent=2))
 (folder/'Footage-credits.txt').write_text('Videos provided by Pexels — https://www.pexels.com\n\n'+'\n'.join(a['creator']+' — '+a['source_url']+'\nSearch: '+a['query'] for a in assets)+'\n')
 return assets

def commit(folder,assets):
 with connect() as c:
  for a in assets:
   c.execute('insert or ignore into used values (?,?,?)',(a['id'],str(Path(folder).resolve()),time.time()));c.execute('delete from reserved where asset=?',(a['id'],))

def status():
 return {'version':'fresh-chapter-v1','connected':bool(key()),'provider':'Pexels','paid_services':False,'fresh_clips_cached':len(list(CACHE.glob('pexels-*.mp4'))),'policy':'Clips used in the last '+str(int(REUSE_DAYS))+' days are excluded; each shot uses a different clip; insufficient matching footage stops the build.','review':'Search relevance is not visual understanding. Review every chapter and illustrative metaphor.'}

def credit_block(assets,limit=2000):
 """Public descriptions need no Pexels list. Detailed credits stay in manifests
 and Footage-credits.txt, and are shown in the studio's source-review interface.
 """
 return ''
