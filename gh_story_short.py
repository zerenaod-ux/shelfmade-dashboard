"""Renders every not-yet-built MindLore story Short (story-shorts/mindlore/*.json) as a vertical 2D stick-man video and zips it for the review step: ml-story-<id>.zip (final.mp4, POST_THIS.txt)."""
import json, sys, os, shutil, subprocess
from pathlib import Path
os.environ['BRAND'] = 'mindlore'; os.environ.setdefault('CE_VOICE_ENGINE', 'edge'); sys.path.insert(0, '.')
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def main(n):
    state = Path('gh-state/built-story-shorts.json'); state.parent.mkdir(exist_ok=True); built = load(state, [])
    todo = [p for p in sorted(Path('story-shorts/mindlore').glob('*.json')) if p.stem not in built][:n]
    Path('out').mkdir(exist_ok=True); made = 0
    import ml2d
    for p in todo:
        sid = p.stem; folder = Path('out/s_' + sid); shutil.rmtree(folder, ignore_errors=True); print('=== Building story Short', sid, flush=True)
        try: ml2d.build(str(p), folder, vert=True)
        except Exception as e: print('FAILED', sid, str(e)[:400], flush=True); continue
        s = load(p, {}); import story_rules
        tags = ''
        try:
            import hashtags; tags = hashtags.mindlore(s.get('hook', ''), 'short')
        except Exception: tags = '#psychology #MindLore #shorts'
        ev = story_rules.evidence_lines(s)
        text = s['public_title'] + '\n\n' + s['hook'] + '\n\n' + ('Evidence: ' + '; '.join(ev) + '\n\n' if ev else '') + 'MindLore: how your mind works, from real research.\n\n' + tags
        z = folder / 'zip'; z.mkdir(exist_ok=True); shutil.copy(folder / 'ml2d_SHORT.mp4', z / 'final.mp4'); (z / 'POST_THIS.txt').write_text(text)
        subprocess.run('cd %s && zip -q %s final.mp4 POST_THIS.txt' % (z, Path('out').resolve() / ('ml-story-%s.zip' % sid)), shell=True, check=True)
        built.append(sid); state.write_text(json.dumps(built)); made += 1; print('BUILT', sid, flush=True); shutil.rmtree(folder, ignore_errors=True)
    print('made', made); sys.exit(0 if made else 1)
if __name__ == '__main__': main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
