"""Variety guard (policy + quality): keeps new hooks from being near-duplicates of recent ones. YouTube penalises mass-produced videos that differ only superficially,
and viewers swipe past a hook they have just seen. Recent hooks = published video titles (data/analytics) + hooks recorded by the builders (gh-state/used-*.json 'hooks') + this run."""
import json, re
from pathlib import Path

STOP = set('a an the of to and or is are was be it this that you your in on for with as at by not but what why how do does i we they he she its'.split())
_SESSION = {}


def _words(t):
    return [w for w in re.findall(r"[a-z']+", (t or '').lower()) if w not in STOP]


def recent(brand, limit=60):
    out = list(_SESSION.get(brand, []))
    try:
        d = json.loads(Path('data/analytics/%s.json' % brand).read_text())
        vs = sorted(d.get('videos', []), key=lambda v: v.get('published', ''), reverse=True)[:limit]
        out += [v['title'] for v in vs]
    except Exception:
        pass
    for f in ('gh-state/used-gh.json', 'gh-state/used-mindlore.json'):
        try:
            if ('mindlore' in f) == (brand == 'mindlore'):
                out += json.loads(Path(f).read_text()).get('hooks', [])[-limit:]
        except Exception:
            pass
    return out


def too_close(hook, brand):
    w = set(_words(hook))
    if len(w) < 2:
        return False
    first = tuple(re.findall(r"[a-z']+", hook.lower())[:3])
    same_open = 0
    for i, r in enumerate(recent(brand)):
        rw = set(_words(r))
        if rw and len(w & rw) / len(w | rw) >= 0.55:
            return True
        if i < 14 and tuple(re.findall(r"[a-z']+", r.lower())[:3]) == first:
            same_open += 1
    return same_open >= 2


def note(brand, hook):
    _SESSION.setdefault(brand, []).append(hook)
