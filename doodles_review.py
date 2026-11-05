"""AnimationDoodles weekly review: list new Shorts, approve/reject them, and start making more (free, local)."""
import json,os,re,subprocess,time,datetime,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent
import os
STUDIO_ROOT=Path(os.environ.get('MINDDOODLES_STUDIO',str(Path.home()/'Documents'/'minddoodles-studio')))
DATA=STUDIO_ROOT/'data'/'doodles'
ENGINE=STUDIO_ROOT/'doodles_engine'
IMG_PY=Path.home()/'Dev/_ops/img-lab/bin/python3'
STATE=DATA/'make_state.json'
ID=re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]{3,60}$')
def _pkg(p):
    try:return json.loads((p/'package.json').read_text())
    except Exception:return None
def list_packs():
    out=[]
    for p in sorted(DATA.glob('20*')):
        k=_pkg(p)
        if not k or not (p/'short.mp4').is_file():continue
        out.append({'id':p.name,'title':k.get('title',p.name),'caption':k.get('caption',''),'concept':k.get('concept',''),'status':k.get('status','ready'),'posting':k.get('posting'),'created':k.get('created',''),'fingerprint':str((p/'short.mp4').stat().st_mtime_ns)})
    out.sort(key=lambda r:(r['status']!='ready',r['created']),reverse=False)
    ready=[r for r in out if r['status']=='ready'];ready.sort(key=lambda r:r['created'])
    return {'ready':ready,'approved':[r for r in out if r['status']=='approved'],'rejected':[r for r in out if r['status']=='rejected'],'make':make_status(),'post':post_status()}
def media_path(pid):
    if not ID.match(pid or ''):raise ValueError('Bad id')
    p=(DATA/pid/'short.mp4').resolve()
    if DATA.resolve() not in p.parents or not p.is_file():raise ValueError('Not found')
    return p
def decision(pid,status,title=None,caption=None):
    if not ID.match(pid or '') or status not in('approved','rejected','ready'):raise ValueError('Bad request')
    f=DATA/pid/'package.json';k=json.loads(f.read_text())
    k['status']=status
    if title:k['title']=str(title)[:100]
    if caption is not None:k['caption']=str(caption)[:2200]
    k[status+'_at']=datetime.datetime.now().isoformat()
    tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(k,indent=1));os.replace(tmp,f)
    out={'ok':True,'status':status}
    if status=='approved':
        try:out['post']=post_approved(pid)
        except Exception as e:out['post']={'posted':False,'reason':str(e)[:200]}
    return out
def _alive(pid):
    try:os.kill(int(pid),0);return True
    except Exception:return False
def make_status():
    st={}
    try:st=json.loads(STATE.read_text())
    except Exception:pass
    running=bool(st.get('pid')) and _alive(st['pid'])
    step,pct,story=None,None,None
    if running:
        prog=sorted(DATA.glob('20*/progress.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:1]
        if prog:
            try:d=json.loads(prog[0].read_text());step,pct,story=d.get('step'),d.get('pct'),prog[0].parent.name
            except Exception:pass
    return {'running':running,'step':step,'pct':pct,'story':story,'n':st.get('n'),'started':st.get('started')}
def start_make(n):
    n=max(1,min(int(n),6))
    if make_status()['running']:raise ValueError('Already making videos. Wait for it to finish.')
    log=open(DATA/'manual.log','a')
    pr=subprocess.Popen(['/usr/bin/caffeinate','-i',str(IMG_PY),str(ENGINE/'daily_doodles.py'),'--extra',str(n)],stdout=log,stderr=log,start_new_session=True,cwd=str(ENGINE.parent))
    STATE.write_text(json.dumps({'pid':pr.pid,'n':n,'started':time.strftime('%Y-%m-%d %H:%M:%S')}));return make_status()

POST_SWITCH=BASE/'doodles-publish.json'
def post_enabled():
    try:return json.loads(POST_SWITCH.read_text()).get('auto_post') is True
    except Exception:return False
def set_post_enabled(on):
    if not isinstance(on,bool):raise ValueError('Bad value')
    if on:
        import minddoodles_buffer_publish as b
        if not b.status().get('publishing_ready'):raise ValueError('Finish the AnimationDoodles video-host setup first (Accounts & setup).')
    tmp=POST_SWITCH.with_suffix('.tmp');tmp.write_text(json.dumps({'auto_post':on}));os.replace(tmp,POST_SWITCH);return post_status()
def post_status():
    try:
        import minddoodles_buffer_publish as b;st=b.status()
    except Exception:st={'publishing_ready':False,'message':'Publishing adapter unavailable.'}
    return {'auto_post':post_enabled(),'ready':bool(st.get('publishing_ready')),'message':st.get('message','')}
def _sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for c in iter(lambda:f.read(1<<20),b''):h.update(c)
    return h.hexdigest()
def post_approved(pid):
    """Called only from the owner's Approve click. Queues the video on the next free slot for YouTube, Instagram and TikTok."""
    import minddoodles_buffer_publish as b
    if not post_enabled() or not b.status().get('publishing_ready'):return {'posted':False,'reason':'Auto-post is off or not set up.'}
    k=json.loads((DATA/pid/'package.json').read_text());path=media_path(pid);fp=_sha(path);res={}
    for plat in ('youtube','instagram','tiktok'):
        try:
            r=b.publish(plat,k.get('title',pid),k.get('caption',''),path,fp,pid,'short1')
            res[plat]={'state':r.get('state'),'due_at':r.get('due_at'),'message':r.get('message','')}
        except Exception as e:res[plat]={'state':'failed','message':str(e)[:200]}
    k['posting']=res;f=DATA/pid/'package.json';tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(k,indent=1));os.replace(tmp,f)
    return {'posted':True,'results':res}


def remove(pid):
    """Owner's Remove click: pull the video's queued posts from Buffer, then mark it rejected so it never shows as approved or posts."""
    if not ID.match(pid or ''):raise ValueError('Bad request')
    f=DATA/pid/'package.json';k=json.loads(f.read_text());buf=[]
    try:
        import minddoodles_buffer_publish as b
        buf=b.cancel(pid)
    except Exception as e:buf=[{'platform':'all','removed':False,'note':str(e)[:160]}]
    k['status']='rejected';k['rejected_at']=datetime.datetime.now().isoformat();k['removed_from_queue']=buf
    tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(k,indent=1));os.replace(tmp,f)
    return {'ok':True,'buffer':buf,'all_removed':all(x.get('removed') for x in buf)}
