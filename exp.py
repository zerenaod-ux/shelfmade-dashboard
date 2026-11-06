"""EXPERIMENT ENGINE helpers (used inside the builders). One experiment per brand+format at a time, so results are clean.
choose(brand, kind, factor, key) -> variant name or None.  While `factor` is the ACTIVE experiment for brand:kind, videos get variants in a balanced pseudo-random split.
After a winner is found, the CHAMPION is used ~85% of the time (the rest keeps exploring). note()/take() carry the variants of the video being built into its music info,
which flows into review/music-log.json, where experiments.py reads them. Never raises into a build."""
import json, hashlib, random
from pathlib import Path
RUN = Path('.exp_run.json')
HOOK_STYLES = {
    'question': 'HOOK STYLE FOR THIS VIDEO: make the opening line a sharp question aimed straight at the viewer.',
    'claim': 'HOOK STYLE FOR THIS VIDEO: make the opening line a bold, slightly contrarian claim (still supported by the passage).',
    'story': 'HOOK STYLE FOR THIS VIDEO: open in the middle of a tiny scene or story moment, as if the viewer just walked in.',
    'command': 'HOOK STYLE FOR THIS VIDEO: make the opening line a direct, urgent instruction to the viewer.',
}
# experiment queue per brand:kind -> list of (factor, (variant_a, variant_b))
QUEUE = {
    'shelfmade:short': [('hook_style', ('question', 'story')), ('music_energy', ('calm', 'lively')), ('hook_style', ('story', 'command'))],
    'mindlore:short': [('hook_style', ('claim', 'question')), ('music_energy', ('calm', 'lively')), ('hook_style', ('story', 'command'))],
    'doodles:short': [('music_energy', ('calm', 'lively'))],
    'shelfmade:full': [('music_energy', ('calm', 'lively'))],
    'mindlore:full': [('music_energy', ('calm', 'lively'))],
    'doodles:full': [('music_energy', ('calm', 'lively'))],
}
def _load(p, d):
    for base in (Path('.'), Path(__file__).resolve().parent):
        try: return json.loads((base / p).read_text())
        except Exception: continue
    return d
def choose(brand, kind, factor, key=''):
    try:
        k = '%s:%s' % (brand, kind); a = _load('data/experiments/active.json', {}).get(k)
        h = int(hashlib.md5(('%s|%s|%s' % (key, k, factor)).encode()).hexdigest(), 16)
        v = None
        if a and a.get('factor') == factor:
            v = a['variants'][h % len(a['variants'])]
        else:
            d = _load('data/experiments/defaults.json', {}).get('%s:%s' % (k, factor))
            if d and random.Random(h).random() < .85: v = d
        if v: note(factor, v)
        else: _drop(factor)
        return v
    except Exception:
        return None
def _drop(factor):
    try:
        if RUN.is_file():
            d = json.loads(RUN.read_text()); d.pop(factor, None); RUN.write_text(json.dumps(d))
    except Exception: pass
def note(factor, variant):
    try:
        d = json.loads(RUN.read_text()) if RUN.is_file() else {}
        d[factor] = variant; RUN.write_text(json.dumps(d))
    except Exception: pass
def take():
    try:
        d = json.loads(RUN.read_text()) if RUN.is_file() else {}
        RUN.unlink(missing_ok=True); return d
    except Exception: return {}
