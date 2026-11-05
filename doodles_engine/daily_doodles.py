"""Nightly AnimationDoodles batch: makes today's Shorts (default 3), writing new stories first when the pool is low.
Run with the img-lab python. Resumable: if it is interrupted, run it again - finished Shorts are kept.
Usage: daily_doodles.py [N]"""
import datetime,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;DATA=ROOT/'data/doodles';sys.path.insert(0,str(HERE))
LOG=DATA/'daily.log'
def log(m):
    line=time.strftime('%Y-%m-%d %H:%M:%S ')+m;print(line,flush=True)
    with open(LOG,'a') as f:f.write(line+'\n')
def unused():
    import make_short
    used=json.loads(make_short.USED.read_text()) if make_short.USED.exists() else []
    return [s for s in make_short.all_stories() if s['id'] not in used]
def made_today():
    day=datetime.date.today().isoformat();return [p for p in DATA.glob(day+'-*') if (p/'short.mp4').is_file() and not p.name.endswith(('-front','-front2'))]
def main():
    a=[x for x in sys.argv[1:] if not x.startswith('--')]
    if '--extra' in sys.argv:n=int(sys.argv[sys.argv.index('--extra')+1]);todo=n
    else:n=int(a[0]) if a else 3;todo=n-len(made_today())
    if todo<=0:log('already made '+str(n)+' Shorts today');return
    if len(unused())<todo:
        log('writing new stories...');subprocess.run([sys.executable,str(HERE/'story_writer.py'),str(todo+3)])
    import make_short
    for i in range(todo):
        pool=unused()
        if not pool:log('no stories left (writer failed?)');break
        s=pool[0];log('making '+s['id']);t=time.time()
        try:make_short.make(s);log(f"done {s['id']} in {time.time()-t:.0f}s")
        except SystemExit as e:log('failed '+s['id']+': '+str(e)[:300]);break
        except Exception as e:log('failed '+s['id']+': '+repr(e)[:300]);break
    log('batch finished; ready: '+', '.join(p.name for p in made_today()))
if __name__=='__main__':main()
