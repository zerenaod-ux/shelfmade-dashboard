"""MindLore 2D builder (GitHub): picks the next unused checked MindLore script (numbered-series scripts first), renders the 2D explainer, zips it as mlfull-2d-<id>.zip
so the existing review step opens a 'Review this FULL video' Issue. Usage: python gh_ml2d_build.py [count]"""
import json, sys, os, shutil, subprocess
from pathlib import Path
os.environ['BRAND'] = 'mindlore'; os.environ.setdefault('CE_VOICE_ENGINE', 'edge')
sys.path.insert(0, '.')
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def main(n):
    state = Path('gh-state/built-2d-mindlore.json'); state.parent.mkdir(exist_ok=True); built = load(state, [])
    series = [e['file'].replace('.json', '') for e in load('data/mindlore/series.json', {}).get('episodes', [])]
    allf = sorted(p.stem for p in Path('cinematic-scripts-mindlore').glob('*.json'))
    order = [s for s in series if s in allf] + [s for s in allf if s not in series]
    todo = [s for s in order if s not in built]; Path('out').mkdir(exist_ok=True); made = 0
    import ml2d
    for sid in todo[:n]:
        folder = Path('out/d_' + sid)
        shutil.rmtree(folder, ignore_errors=True)
        print('=== Building 2D MindLore video', sid, flush=True)
        try: ml2d.build(sid, folder)
        except Exception as e:
            print('FAILED', sid, str(e)[:400], flush=True); continue
        z = Path('out/mlfull-2d-' + sid + '.zip')
        extra = ''
        try:   # vertical 2D Short from the same script (kept inside the zip for review; not auto-posted)
            ml2d.build(sid, folder / 'short', vert=True)
            shutil.copy(folder / 'short' / 'ml2d_SHORT.mp4', folder / 'ml2d_SHORT.mp4'); extra = ' ml2d_SHORT.mp4'
        except Exception as e: print('2D short skipped:', str(e)[:300], flush=True)
        subprocess.run('cd %s && zip -q ../%s ml2d_LONGFORM.mp4 THUMBNAIL.jpg POST_THIS.txt ml2d-plan.json%s' % (folder, z.name, extra), shell=True, check=True)
        built.append(sid); state.write_text(json.dumps(built)); made += 1; print('BUILT', sid, flush=True)
        shutil.rmtree(folder, ignore_errors=True)
    print('made', made); sys.exit(0 if made else 1)
if __name__ == '__main__': main(max(1, min(int(sys.argv[1]) if len(sys.argv) > 1 else 1, 3)))
