"""GitHub runner: makes AnimationDoodles Shorts with NO Mac. story (Gemini) -> Kaggle free GPU (voices, pictures, word timing) -> Kaggle LatentSync lip-sync -> CPU render -> release doodles-*.
Usage: python doodles_engine/gh_doodles.py [N]   (env: GEMINI_API_KEY, KAGGLE_API_TOKEN). Posts nothing: a review Issue is opened afterwards by review_publish.py.
State committed by the workflow: data/doodles/used.json, data/doodles/story_pool.json."""
import datetime, json, os, shutil, subprocess, sys, time, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent; DATA = ROOT / 'data/doodles'; DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE)); import stories
USED = DATA / 'used.json'; POOL = DATA / 'story_pool.json'; OUT = ROOT / 'out'; OUT.mkdir(exist_ok=True)
EXPLAIN = {'sunk-cost-soup': 3, 'zeigarnik-tabs': 2, 'choice-overload': 3}
TAGS = '#psychology #mindset #animation #relatable #AnimationDoodles #Shorts'
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def jl(p, d):
    try: return json.loads(Path(p).read_text())
    except (OSError, ValueError): return d
def unused():
    used = set(jl(USED, [])); return [s for s in list(stories.STORIES) + jl(POOL, []) if s['id'] not in used]
def mark_used(sid):
    """Record the story as used BEFORE building and push at once, so a lost/late state push can never cause a rebuild."""
    used = jl(USED, [])
    if sid not in used: used.append(sid); USED.write_text(json.dumps(used))
    try:
        subprocess.run(['git', 'config', 'user.name', 'doodles-bot']); subprocess.run(['git', 'config', 'user.email', 'bot@users.noreply.github.com'])
        subprocess.run(['git', 'add', '-f', str(USED)])
        if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode:
            subprocess.run(['git', 'commit', '-qm', 'doodles: reserve ' + sid])
            for _ in range(4):
                if subprocess.run('git pull --rebase -q && git push -q', shell=True).returncode == 0: break
                subprocess.run('git rebase --abort', shell=True, stderr=subprocess.DEVNULL)
                try:
                    subprocess.run('git fetch -q origin', shell=True)
                    br = subprocess.run('git show origin/master:data/doodles/used.json', shell=True, capture_output=True, text=True).stdout
                    union = sorted(set(json.loads(br or '[]')) | set(jl(USED, [])))
                    subprocess.run('git reset -q --hard origin/master', shell=True)
                    USED.write_text(json.dumps(union)); subprocess.run(['git', 'add', '-f', str(USED)])
                    subprocess.run(['git', 'commit', '-qm', 'doodles: reserve ' + sid])
                except Exception as e: log('merge retry', e)
                time.sleep(4)
    except Exception as e: log('reserve push skipped', e)
def run(*a, **k): return subprocess.run([sys.executable, *map(str, a)], **k)
def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'data/secrets.json').write_text(json.dumps({'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY', '')}))
    if len(unused()) < n + 2:
        log('writing new stories...'); run(HERE / 'story_writer.py', n + 3)
    made = []
    for s in unused()[:n]:
        if s['id'] in set(jl(USED, [])): log('already used, skip', s['id']); continue
        day = datetime.date.today().isoformat(); work = DATA / f"{day}-{s['id']}"; work.mkdir(exist_ok=True)
        st = dict(s); st['explain_shot'] = s.get('explain_shot', EXPLAIN.get(s['id'], 4)); (work / 'story.json').write_text(json.dumps(st, indent=1))
        mark_used(s['id']); log('MAKING', s['id'])
        t = time.time()
        if run(HERE / 'kaggle_make.py', work).returncode: log('Kaggle stage 1 failed for', s['id'], '- skipping this story'); continue
        if run(HERE / 'ls_cloud.py', work).returncode: log('cloud lip-sync incomplete; render falls back to fast mouths'); os.environ['FASTLIP'] = '1'
        if run(HERE / 'render.py', work).returncode or not (work / 'short.mp4').is_file(): log('render failed for', s['id']); continue
        try:
            import series; title = series.title(s['id'], s['title'], 'short')
        except Exception:
            title = s['title']
        post = f"{title}\n\n{s['caption']}\n\n{TAGS}\n"
        z = OUT / f"doodles-{s['id']}.zip"
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED) as f:
            f.write(work / 'short.mp4', 'final.mp4'); f.writestr('POST_THIS.txt', post)
            if (work / 'bed.music.json').is_file(): f.write(work / 'bed.music.json', 'MUSIC.json')
        used = jl(USED, []); used.append(s['id']); USED.write_text(json.dumps(used))
        made.append(s['id']); log('DONE', s['id'], round(time.time() - t), 's')
        for junk in ('k1_in', 'k1_kernel', 'k1_dl', 'ls_in', 'ls_kernel', 'ls_dl', 'silent.mp4'):
            p = work / junk; shutil.rmtree(p, ignore_errors=True) if p.is_dir() else (p.unlink() if p.exists() else None)
    (OUT / 'made.txt').write_text('\n'.join(made)); log('made', made)
if __name__ == '__main__': main()
