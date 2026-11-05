"""Self-learning for ShelfMade hooks (Mac, read-only on metrics). Looks at views per hook type and writes hook-weights.json:
types that earn more views are picked more often, weak ones less, but never below 0.4 (every type keeps being tested).
Needs enough data (>=30 measured posts, >=6 per type) else all weights stay 1. Smoothed 50/50 with the last weights so one lucky post cannot swing it.
push() copies the file into the GitHub clone so GitHub builds use it. Nothing is posted by this file."""
import collections, glob, json, sqlite3, shutil, subprocess, time
from pathlib import Path
B = Path(__file__).resolve().parent
OUT = B / 'hook-weights.json'
OLD = (('contrarian', 'misreads'), ('warning', 'nobody warns'), ('myth', 'not what you think'), ('sting', 'hits hard'), ('contrarian', 'almost everyone'))
TYPES = ['quote', 'contrarian', 'warning', 'myth', 'sting', 'curiosity', 'author']


def _hooks():
    h = {}
    for pat in ('generated/*/*/content-review.json', 'generated/*/content-review.json'):
        for f in glob.glob(str(B / pat)):
            try:
                j = json.load(open(f))
                t = (j.get('hook') or '').strip().lower()
                if t and j.get('hook_type') and j['hook_type'] != 'none':
                    h[t] = j['hook_type']
            except Exception:
                pass
    return h


def compute():
    hooks = _hooks()
    c = sqlite3.connect('file:%s?mode=ro' % (B / 'decisions.sqlite3'), uri=True, timeout=10)
    rows = c.execute('''select p.title,max(o.views) from audience_posts p join audience_observations o
        on o.platform=p.platform and o.post_key=p.post_key group by p.platform,p.post_key''').fetchall()
    by = collections.defaultdict(list)
    for t, v in rows:
        t = (t or '').lower().strip()
        kind = next((k for h, k in hooks.items() if t.startswith(h[:40])), None) or next((k for k, p in OLD if p in t), None)
        if kind in TYPES:
            by[kind].append(int(v or 0))
    n = sum(len(v) for v in by.values())
    allavg = (sum(sum(v) for v in by.values()) / n) if n else 0
    prev = {}
    try:
        prev = json.loads(OUT.read_text()).get('weights', {})
    except Exception:
        pass
    w = {}
    for k in TYPES:
        v = by.get(k, [])
        target = 1.0
        if n >= 30 and len(v) >= 6 and allavg > 0:
            target = max(0.4, min(2.0, (sum(v) / len(v)) / allavg))
        w[k] = round(0.5 * prev.get(k, 1.0) + 0.5 * target, 3)
    data = {'updated': int(time.time()), 'measured_posts': n, 'avg_views': round(allavg, 1),
            'per_type': {k: {'posts': len(v), 'avg': round(sum(v) / len(v), 1) if v else 0} for k, v in by.items()},
            'active': n >= 30, 'weights': w}
    OUT.write_text(json.dumps(data, indent=1))
    return data


def push():
    """Recompute at most every 12 h, then copy into the GitHub clone and push when it changed."""
    try:
        if time.time() - json.loads(OUT.read_text()).get('updated', 0) < 12 * 3600:
            return False
    except Exception:
        pass
    d = compute()
    repo = Path.home() / 'Dev/repos/shelfmade-dashboard'
    if not (repo / 'hook_rules.py').is_file():
        return False
    dst = repo / 'hook-weights.json'
    try:
        if json.loads(dst.read_text()).get('weights') == d['weights']:
            return False
    except Exception:
        pass
    shutil.copy(OUT, dst)
    for cmd in (['git', 'pull', '--rebase', '--autostash', '-q'], ['git', 'add', '-f', 'hook-weights.json'],
                ['git', 'commit', '-qm', 'hook weights (learned from views)'], ['git', 'push', '-q']):
        subprocess.run(cmd, cwd=str(repo), timeout=120, capture_output=True)
    print('hook_learn: pushed weights', d['weights'], flush=True)
    return True


if __name__ == '__main__':
    print(json.dumps(compute(), indent=1))
