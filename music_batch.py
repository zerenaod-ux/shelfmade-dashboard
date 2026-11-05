"""Add background music to every UNREVIEWED draft that does not have it yet (ShelfMade + MindLore).
Approved/published drafts are never touched. Safe to re-run."""
import sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'content-empire-studio'))
import music_lab
def has_music(f):
    try:return 'music' in json.loads((f/'validation.json').read_text())
    except Exception:return False
done=skip=fail=0
def go(label,folder):
    global done,skip,fail
    folder=Path(folder)
    if not (folder/'final.mp4').is_file() or not (folder/'validation.json').is_file() or has_music(folder):skip+=1;return
    t=time.time()
    try:
        mood=music_lab.remix(folder,gain=1.0);done+=1;print('music ok',label,mood,round(time.time()-t),'s',flush=True)
    except Exception as e:
        fail+=1;print('FAILED',label,str(e)[:120],flush=True)
try:
    import server
    for i in server.inventory():
        if i.get('content_type')=='full' or not i.get('generated') or i.get('status')!='review':continue
        go('shelfmade '+i['id'][:10],i['folder'])
except Exception as e:print('ShelfMade list failed:',e)
try:
    from studio import mindlore_workflow as w, workspace
    for r in w.catalogue():
        if not r.get('video_available') or not str(r.get('status','')).endswith('unreviewed'):continue
        p=workspace.video_path(w.brand(),r['id'])
        go('mindlore '+r['id'][:10],Path(p).parent)
except Exception as e:print('MindLore list failed:',e)
print('DONE added',done,'skipped',skip,'failed',fail)
