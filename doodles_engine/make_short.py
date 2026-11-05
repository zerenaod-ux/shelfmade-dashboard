"""Make one AnimationDoodles Short end-to-end, free, on this Mac.
   story -> voices (Qwen3-TTS) -> pictures (FLUX.2 klein edit of the approved Leo & Mia reference) -> render (camera, captions, music)
Usage: <img-lab python> make_short.py [--story ID] [--all-new N]
Resumable: finished pictures/voices are reused. Output: data/doodles/<day>-<id>/short.mp4 (+ package.json)"""
import datetime,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE))
import stories
HOME=Path.home()
IMG_PY=HOME/'Dev/_ops/img-lab/bin/python3';TTS_PY=HOME/'Dev/_ops/tts-lab/bin/python3'
REF=ROOT/'data/production/reference-v1/Opening-frame.png'
DATA=ROOT/'data/doodles';DATA.mkdir(parents=True,exist_ok=True)
USED=DATA/'used.json'
FRONT=(" IMPORTANT FRAMING: both characters look straight toward the camera (front view, face fully visible, head upright and level, not tilted or turned away), "
       "faces large and well lit, mouths ALWAYS CLOSED (lips together, no open mouth, no teeth showing, even when shouting or explaining), hands and props never covering the faces.")
EXPLAIN={'sunk-cost-soup':3,'zeigarnik-tabs':2,'choice-overload':3}
def log(msg):print(time.strftime('%H:%M:%S'),msg,flush=True)
def progress(work,step,pct):(work/'progress.json').write_text(json.dumps({'step':step,'pct':pct,'at':datetime.datetime.now().isoformat()}))
POOL=DATA/'story_pool.json'
def all_stories():
    pool=json.loads(POOL.read_text()) if POOL.exists() else []
    return list(stories.STORIES)+pool
def pick(want=None):
    used=json.loads(USED.read_text()) if USED.exists() else []
    if want:
        s=next((x for x in all_stories() if x['id']==want),None)
        if not s:raise SystemExit('Unknown story '+want)
        return s
    for s in all_stories():
        if s['id'] not in used:return s
    raise SystemExit('All stories are used. Add new ones (stories.py) or let the writer create more.')
def make(story):
    day=datetime.date.today().isoformat();tag=sys.argv[sys.argv.index('--tag')+1] if '--tag' in sys.argv else '';work=DATA/f"{day}-{story['id']}{('-'+tag) if tag else ''}";work.mkdir(exist_ok=True)
    st=dict(story);st['explain_shot']=story.get('explain_shot',EXPLAIN.get(story['id'],4))
    (work/'story.json').write_text(json.dumps(st,indent=1))
    # 0 optional: voices + pictures + word timing on the FREE Kaggle GPU (python kaggle_make.py). Falls back to the local steps on any failure.
    if '--kaggle-make' in sys.argv:
        r=subprocess.run([str(IMG_PY),str(HERE/'kaggle_make.py'),str(work)])
        if r.returncode:log('Kaggle stage 1 failed; using the local Mac engines')
    # 1 voices
    progress(work,'Recording Leo and Mia',5);log('voices...')
    vj=[{'who':l['who'],'text':l['text'],'feel':l['feel'],'wav':str(work/f'line_{si:02d}_{li:02d}.wav')} for si,sh in enumerate(story['shots']) for li,l in enumerate(sh['lines'])]
    if not all(Path(v['wav']).is_file() for v in vj):
        r=subprocess.run([str(TTS_PY),str(HERE/'voices.py')],input=json.dumps({'jobs':vj}),text=True,capture_output=True,env={**clean_env(),'HF_HUB_OFFLINE':'1'})
        print(r.stdout[-600:])
        if r.returncode:raise SystemExit('Voices failed: '+r.stderr[-800:])
    # 2 pictures
    progress(work,'Drawing the scenes',25);log('pictures (about 80 s each)...')
    jobs=[{'prompt':stories.LOOK+sh['scene']+FRONT,'out':str(work/f'shot_{i:02d}.png'),'seed':100+i,'w':576,'h':1024} for i,sh in enumerate(story['shots'])]
    r=subprocess.run([str(IMG_PY),str(HERE/'imager.py')],input=json.dumps({'ref':[str(REF)],'jobs':jobs}),text=True) if not all(Path(j['out']).is_file() for j in jobs) else subprocess.CompletedProcess([],0)
    if r.returncode or not all((work/f'shot_{i:02d}.png').is_file() for i in range(len(jobs))):raise SystemExit('Picture step failed')
    # 2b lip-sync (approved local JoyVASA engine). A failure never blocks the video.
    if '--ai-lipsync' in sys.argv:
        progress(work,'Lip-syncing Leo and Mia',50);log('lip-sync...')
        r=subprocess.run([str(ROOT/'.venv/bin/python'),str(HERE/'lipsync.py'),str(work)],cwd=str(ROOT))
        if r.returncode:log('lip-sync step failed; rendering without mouth motion')
    # 2b3 AI lip-sync on the FREE Kaggle GPU (LatentSync). Skipped when there is no Kaggle token; any failure falls back to the local mouths below.
    ls_ok=False
    if '--no-ls' not in sys.argv and ((HOME/'.kaggle/access_token').exists() or (HOME/'.kaggle/kaggle.json').exists()):
        progress(work,'AI lip-sync on free cloud GPU (about 1 hour)',55);log('cloud lip-sync (Kaggle, about 1 hour)...')
        try:
            r=subprocess.run([str(IMG_PY),str(HERE/'ls_cloud.py'),str(work)],timeout=6*3600)
            ls_ok=(r.returncode==0 and (work/'ls_out'/'DONE').is_file())
        except Exception as ex:log('cloud lip-sync failed: '+str(ex))
        if not ls_ok:log('cloud lip-sync incomplete; using the local mouth system')
    # 2c real lip-sync (Wav2Lip, free, local, fast). A failure never blocks the video.
    if not ls_ok:
        progress(work,'Lip-syncing Leo and Mia',60);log('lip-sync (Wav2Lip)...')
        r=subprocess.run([str(IMG_PY),str(HERE/'w2l_lips.py'),str(work)],cwd=str(ROOT))
        if r.returncode:log('lip-sync failed; rendering without mouth motion')
    # 2c2 word/sound timing so the mouth follows the real speech (free wav2vec2). A failure never blocks the video.
    progress(work,'Timing the words',61);log('word timing...')
    r=subprocess.run([str(IMG_PY),str(HERE/'align.py'),str(work)],cwd=str(ROOT))
    if r.returncode:log('word timing failed; mouth will follow loudness')
    # 2d real drawn open-mouth pictures (FLUX edit) so the mouth is the character's own drawn mouth. A failure never blocks the video.
    if not ls_ok:
        progress(work,'Drawing real mouths',62);log('real mouths (about 90 s per picture)...')
        r=subprocess.run([str(IMG_PY),str(HERE/'mouthvar.py'),str(work)],cwd=str(ROOT))
        if r.returncode:log('mouth pictures failed; rendering with the lip-sync patch')
    # 3 render
    progress(work,'Animating, captions and music',75);log('render...')
    r=subprocess.run([str(IMG_PY),str(HERE/'render.py'),str(work)])
    if r.returncode or not (work/'short.mp4').is_file():raise SystemExit('Render failed')
    (work/'package.json').write_text(json.dumps({'id':work.name,'title':story['title'],'concept':story['concept'],'caption':story['caption']+'\n\n#psychology #mindset #animation #relatable #AnimationDoodles','status':'ready','created':datetime.datetime.now().isoformat(),'video':'short.mp4','engine':'doodles-still-motion-v1'},indent=1))
    progress(work,'Ready for review',100)
    used=json.loads(USED.read_text()) if USED.exists() else []
    if story['id'] not in used:used.append(story['id']);USED.write_text(json.dumps(used))
    log('DONE '+str(work/'short.mp4'));return work
def clean_env():
    import os
    return {k:v for k,v in os.environ.items() if k not in ('HF_HOME','XDG_CACHE_HOME','HF_HUB_CACHE','TRANSFORMERS_CACHE')}
if __name__=='__main__':
    a=sys.argv[1:];sid=a[a.index('--story')+1] if '--story' in a else None
    n=int(a[a.index('--all-new')+1]) if '--all-new' in a else 1
    for _ in range(n):make(pick(sid))
