"""STORY LEARNING: matches our posted story Shorts to their real YouTube views (data/analytics/<brand>.json) and learns which THEMES and which visual choices (acts, scenes, props) got the most views.
Writes data/story-learn-<brand>.json, read by story_short.py (theme choice) and ml2d.py (director choices, with 30% exploration). Needs >=3 matched posts before it influences anything.
  python story_learn.py [brand]"""
import json, re, sys, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def norm(t): return re.sub(r'[^a-z0-9 ]', '', t.lower()).strip()
def run(brand):
    log = load(B / ('data/story-learn-log-%s.json' % brand), {'items': []})['items']
    vids = load(B / ('data/analytics/%s.json' % brand), {}).get('videos', [])
    got = []
    for it in log:
        t = norm(it.get('title', ''))
        if not t: continue
        v = next((v for v in vids if t[:40] and (norm(v.get('title', '')).startswith(t[:40]) or t[:40] in norm(v.get('title', '')))), None)
        if v: got.append((it, float(v.get('views', 0))))
    out = {'brand': brand, 'n': len(got), 'updated': datetime.date.today().isoformat(), 'theme': {}, 'act': {}, 'bg': {}, 'prop': {}}
    if len(got) >= 3:
        for kind, key in (('theme', 'theme'), ('act', 'acts'), ('bg', 'bgs'), ('prop', 'props')):
            sums = {}
            for it, views in got:
                vals = [it.get(key)] if kind == 'theme' else sorted(set(it.get(key) or []))
                for x in vals:
                    if x: s = sums.setdefault(x, [0.0, 0]); s[0] += views; s[1] += 1
            avg = {k: s[0] / s[1] for k, s in sums.items() if s[1] >= 1}
            top = max(avg.values()) if avg else 1.0
            out[kind] = {k: round(v / top, 3) for k, v in avg.items()}
    (B / ('data/story-learn-%s.json' % brand)).write_text(json.dumps(out, indent=1))
    print('story_learn: %s matched %d posts%s' % (brand, len(got), '' if len(got) >= 3 else ' (needs 3 to start learning)'))
if __name__ == '__main__':
    for b in (sys.argv[1:] or ['mindlore', 'shelfmade']): run(b)
