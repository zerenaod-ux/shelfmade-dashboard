"""AnimationDoodles post results from the AnimationDoodles Buffer account (read-only): link, sent time, views/likes/comments. Cached 30 min."""
import json,time,urllib.request,urllib.error
from pathlib import Path
CONN=Path(__file__).resolve().parent/'private-animationdoodles-buffer'/'connection.json'
CACHE={'t':0,'data':None}
DOC='''query($input:PostsInput!){posts(first:100,input:$input){edges{node{id channelService channelId externalLink sentAt dueAt status text metricsUpdatedAt metrics{type name value unit}}}}}'''
def _req(token,doc,variables):
    r=urllib.request.Request('https://api.buffer.com',json.dumps({'query':doc,'variables':variables}).encode(),{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=60) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        try:return json.load(e)
        except Exception:return {'errors':[{'message':'HTTP '+str(e.code)}]}
def fetch(force=False):
    if not force and CACHE['data'] is not None and time.time()-CACHE['t']<1800:return CACHE['data']
    try:
        c=json.loads(CONN.read_text());token=c['token'];org=c['organization'];oid=org['id'] if isinstance(org,dict) else org
        ids=[ch['id'] for ch in c.get('channels',[]) if isinstance(ch,dict) and 'id' in ch]
    except Exception:return {'posts':[],'error':'AnimationDoodles Buffer connection unavailable.'}
    last=None
    for status in (['sent'],'sent',None):
        flt={'channelIds':ids} if ids else {}
        if status is not None:flt['status']=status
        res=_req(token,DOC,{'input':{'organizationId':oid,'filter':flt}})
        if res.get('errors') and not res.get('data'):last=res['errors'][0].get('message','error');continue
        posts=[]
        for e in ((res.get('data') or {}).get('posts') or {}).get('edges',[]):
            n=e['node'];m={}
            for k in n.get('metrics') or []:
                nm=((k.get('type') or '')+' '+(k.get('name') or '')).lower()
                if 'view' in nm or 'play' in nm:m['views']=k.get('value')
                elif 'like' in nm or 'reaction' in nm:m['likes']=k.get('value')
                elif 'comment' in nm:m['comments']=k.get('value')
                m.setdefault('all',{})[k.get('type') or k.get('name')]=k.get('value')
            posts.append({'service':n.get('channelService'),'link':n.get('externalLink'),'sent_at':n.get('sentAt'),'due_at':n.get('dueAt'),'status':n.get('status'),'text':(n.get('text') or '')[:200],'metrics':m,'updated':n.get('metricsUpdatedAt')})
        data={'posts':posts,'fetched':time.time()};CACHE.update(t=time.time(),data=data);return data
    return {'posts':[],'error':'Buffer: '+str(last)[:200]}
