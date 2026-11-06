"""GitHub-side hook learning (no laptop). Reads YouTube views per video from data/analytics/shelfmade.json,
recognizes the hook type from the title (templates in hook_rules.LINES), and writes hook-weights.json with the same rules as hook_learn.py:
>=30 measured posts and >=6 per type before weights move; never below 0.4; smoothed 50/50 with the previous weights."""
import collections, json, re, time
from pathlib import Path
import hook_rules
B = Path(__file__).resolve().parent
OUT = B / 'hook-weights.json'
TYPES = hook_rules.TYPES
OLD = (('contrarian', 'misreads'), ('warning', 'nobody warns'), ('myth', 'not what you think'), ('sting', 'hits hard'), ('contrarian', 'almost everyone'))


def _rx():
    out = []
    for kind, lines in hook_rules.LINES.items():
        for l in lines:
            p = re.escape(l).replace(re.escape('{T}'), '.+').replace(re.escape('{A}'), r'[\w\'-]+')
            out.append((kind, re.compile('^' + p + '$', re.I)))
    return out


def kind_of(title):
    t = (title or '').strip()
    for k, r in _rx():
        if r.match(t):
            return k
    low = t.lower()
    return next((k for k, p in OLD if p in low), None)


def compute():
    vids = json.load(open(B / 'data/analytics/shelfmade.json')).get('videos', [])
    by = collections.defaultdict(list)
    for v in vids:
        k = kind_of(v.get('title'))
        if k in TYPES:
            by[k].append(int(v.get('views') or 0))
    n = sum(len(x) for x in by.values())
    allavg = (sum(sum(x) for x in by.values()) / n) if n else 0
    try:
        prev = json.loads(OUT.read_text()).get('weights', {})
    except Exception:
        prev = {}
    w = {}
    for k in TYPES:
        x = by.get(k, [])
        target = 1.0
        if n >= 30 and len(x) >= 6 and allavg > 0:
            target = max(0.4, min(2.0, (sum(x) / len(x)) / allavg))
        w[k] = round(0.5 * prev.get(k, 1.0) + 0.5 * target, 3)
    data = {'updated': int(time.time()), 'measured_posts': n, 'avg_views': round(allavg, 1),
            'per_type': {k: {'posts': len(x), 'avg': round(sum(x) / len(x), 1) if x else 0} for k, x in by.items()},
            'active': n >= 30, 'weights': w, 'source': 'github youtube analytics'}
    OUT.write_text(json.dumps(data, indent=1))
    return data


if __name__ == '__main__':
    print(json.dumps(compute(), indent=1))
