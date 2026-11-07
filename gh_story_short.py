"""Renders every not-yet-built MindLore story Short (story-shorts/mindlore/*.json) as a vertical 2D stick-man video and zips it for the review step: ml-story-<id>.zip (final.mp4, POST_THIS.txt)."""
import json, sys, os, shutil, subprocess
from pathlib import Path
BRAND = os.environ.get('BRAND', 'mindlore'); os.environ['BRAND'] = BRAND; os.environ.setdefault('CE_VOICE_ENGINE', 'edge'); sys.path.insert(0, '.')
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def _ft(t):
    try:
        import growth; return growth.fix_title(BRAND, t)
    except Exception: return t

def main(n):
    state = Path('gh-state/built-story-shorts.json' if BRAND == 'mindlore' else 'gh-state/built-story-shorts-%s.json' % BRAND); state.parent.mkdir(exist_ok=True); built = load(state, [])
    todo = [p for p in sorted(Path('story-shorts/%s' % BRAND).glob('*.json')) if p.stem not in built][:n]
    Path('out').mkdir(exist_ok=True); made = 0
    import ml2d
    for p in todo:
        sid = p.stem; folder = Path('out/s_' + sid); shutil.rmtree(folder, ignore_errors=True); print('=== Building story Short', sid, flush=True)
        try: ml2d.build(str(p), folder, vert=True)
        except Exception as e: print('FAILED', sid, str(e)[:400], flush=True); continue
        s = load(p, {}); import story_rules
        tags = ''
        try:
            import hashtags; tags = (hashtags.shelfmade if BRAND == 'shelfmade' else hashtags.mindlore)(s.get('hook', ''), 'short')
        except Exception: tags = '#psychology #MindLore #shorts'
        ev = story_rules.evidence_lines(s)
        text = _ft(s['public_title']) + '\n\n' + s['hook'] + '\n\n' + ('Evidence: ' + '; '.join(ev) + '\n\n' if ev else '') + ('Book: %s by %s. Classic books, explained on ShelfMade.\n\n' % (s.get('title', ''), s.get('author', '')) if BRAND == 'shelfmade' else 'MindLore: how your mind works, from real research.\n\n') + tags
        z = folder / 'zip'; z.mkdir(exist_ok=True); shutil.copy(folder / 'ml2d_SHORT.mp4', z / 'final.mp4'); (z / 'POST_THIS.txt').write_text(text)
        subprocess.run('cd %s && zip -q %s final.mp4 POST_THIS.txt' % (z, Path('out').resolve() / ('%s-story-%s.zip' % ('sm' if BRAND == 'shelfmade' else 'ml', sid))), shell=True, check=True)
        try:   # learning log: which scenes / actions / props this video used (story_learn.py matches it to real views later)
            plan = load(folder / 'ml2d-plan.json', {}).get('beats', []); lg = Path('data/story-learn-log-%s.json' % BRAND); L = load(lg, {'items': []})
            L['items'].append({'id': sid, 'title': s.get('public_title', ''), 'theme': s.get('theme', ''), 'acts': sorted({b['act'] for b in plan}), 'bgs': sorted({b['bg'] for b in plan}), 'props': sorted({p['k'] for b in plan for p in b.get('props', [])})})
            L['items'] = L['items'][-300:]; lg.parent.mkdir(exist_ok=True); lg.write_text(json.dumps(L, indent=1))
        except Exception as e: print('learn log skipped:', str(e)[:100])
        built.append(sid); state.write_text(json.dumps(built)); made += 1; print('BUILT', sid, flush=True); shutil.rmtree(folder, ignore_errors=True)
    print('made', made); sys.exit(0 if made else 1)
if __name__ == '__main__': main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
