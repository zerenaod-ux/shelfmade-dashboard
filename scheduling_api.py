"""One-click scheduling switch per brand. Only flips 'enabled'; slot times stay in each brand's posting-slots.json."""
from pathlib import Path
import json,os,tempfile,sqlite3,datetime
HERE=Path(__file__).resolve().parent
FILES={'shelfmade':HERE/'posting-slots.json','mindlore':HERE.parent/'content-empire-studio'/'state'/'mindlore'/'posting-slots.json'}

def _read(brand):
 return json.loads(FILES[brand].read_text())

DBS={'mindlore':HERE.parent/'content-empire-studio'/'state'/'mindlore'/'workflow.sqlite3','shelfmade':HERE/'decisions.sqlite3'}

def _runway(brand):
 # Count posts already booked for the future and when the last one goes live.
 try:
  c=sqlite3.connect('file:'+str(DBS[brand])+'?mode=ro',uri=True,timeout=5)
  now=datetime.datetime.now(datetime.timezone.utc)
  if brand=='mindlore':
   rows=[json.loads(m or '{}').get('due_at') for (m,) in c.execute("select metrics from posts where state='scheduled'")]
  else:
   rows=[r for (r,) in c.execute("select due_at from platform_posts where state='scheduled'")]
  due=sorted(d for d in rows if d and datetime.datetime.fromisoformat(d.replace('Z','+00:00'))>now)
  return {'scheduled':len(due),'last':due[-1] if due else None}
 except Exception:return {'scheduled':0,'last':None}

def status():
 out={}
 for b in FILES:
  try:
   c=_read(b);out[b]={'runway':_runway(b),'enabled':bool(c.get('enabled')),'slots':c.get('slots',{}),'timezone':c.get('timezone')}
  except (OSError,ValueError):out[b]={'enabled':False,'slots':{},'timezone':None,'error':'Slots file unavailable'}
 return out

def set_enabled(brand,enabled):
 if brand not in FILES or not isinstance(enabled,bool):raise ValueError('Unknown brand or value.')
 c=_read(brand);c['enabled']=enabled
 fd,tmp=tempfile.mkstemp(dir=str(FILES[brand].parent),suffix='.tmp')
 with os.fdopen(fd,'w') as f:json.dump(c,f,indent=1)
 os.replace(tmp,FILES[brand]);return status()

def review_pack():
 import sys,importlib
 base=str(HERE.parent/'content-empire-studio')
 if base not in sys.path:sys.path.insert(0,base)
 w=importlib.import_module('studio.mindlore_workflow');rp=importlib.import_module('studio.review_pack')
 cat=w.catalogue()
 try:
  with w.db() as c:posted={r[0] for r in c.execute("SELECT DISTINCT item FROM posts WHERE state!='blocked' OR remote_id IS NOT NULL")}
 except Exception:posted=set()
 try:retired=set(json.loads((HERE/'mindlore-retired.json').read_text()).get('ids',[]))
 except Exception:retired=set()
 def fresh(r):
  if r['id'] in posted or r['id'] in retired:return False
  try:return not w.item_matches(r)
  except Exception:return True
 return {'mindlore':rp.build([r for r in cat if fresh(r)])}

import re
def set_slots(brand,platform,times):
 if brand not in FILES or not isinstance(times,list) or not 1<=len(times)<=6:raise ValueError('Give 1 to 6 times like 12:00.')
 for t in times:
  if not isinstance(t,str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',t):raise ValueError('Times must look like 12:00 or 21:30.')
 c=_read(brand)
 if platform not in c.get('slots',{}):raise ValueError('Unknown platform.')
 c['slots'][platform]=sorted(set(times))
 fd,tmp=tempfile.mkstemp(dir=str(FILES[brand].parent),suffix='.tmp')
 with os.fdopen(fd,'w') as f:json.dump(c,f,indent=1)
 os.replace(tmp,FILES[brand]);return status()


def mindlore_approved():
 """MindLore videos the owner approved (workflow database), newest first, with their posting state per platform."""
 import sys,importlib
 base=str(HERE.parent/'content-empire-studio')
 if base not in sys.path:sys.path.insert(0,base)
 w=importlib.import_module('studio.mindlore_workflow')
 out=[]
 with w.db() as c:
  rows=c.execute("SELECT a.item,a.updated,p.title,p.payload FROM approvals a LEFT JOIN preparations p ON p.item=a.item WHERE a.decision='approved' ORDER BY a.updated DESC").fetchall()
  for r in rows:
   posts=c.execute("SELECT platform,state,url,metrics FROM posts WHERE item=? AND state!='blocked'",(r[0],)).fetchall()
   fmt=None;vid=None
   try:
    pl=json.loads(r[3] or '{}');fmt=pl.get('format');vid=(pl.get('artifacts') or {}).get('video')
   except Exception:pass
   out.append({'id':r[0],'title':r[2] or r[0],'approved_at':r[1],'format':fmt,'video':vid,'local':bool(vid and (HERE.parent/'content-empire-studio'/'state'/'mindlore'/'staged'/(str(vid)+'.mp4')).is_file()),'posts':[{'platform':x[0],'state':x[1],'url':x[2],'due_at':_due(x[3])} for x in posts]})
 return out


def _due(m):
 try:return (json.loads(m or '{}') or {}).get('due_at')
 except Exception:return None
