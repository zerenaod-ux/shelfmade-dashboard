"""Which music holds viewers? Joins review/music-log.json (music used per video) with data/analytics/<brand>.json (views per day) and writes
data/learned/music-<brand>.json = {style: {n, vpd, bias}}. music_director adds `bias` to a style's score once it has >= 3 videos, so the library
steers toward the music that real viewers watch. Runs inside learn.yml (twice a week). Small data: bias is capped at +-0.35 so variety stays."""
import datetime, json, re
from pathlib import Path
NOW = datetime.datetime.now(datetime.timezone.utc)
def norm(t): return re.sub(r'[^a-z0-9]+', ' ', (t or '').lower()).strip()[:60]
def main():
    try: log = json.loads(Path('review/music-log.json').read_text())
    except Exception: print('no music log yet'); return
    by = {norm(k): v for k, v in log.items()}
    Path('data/learned').mkdir(parents=True, exist_ok=True)
    for b in ('shelfmade', 'mindlore', 'doodles'):
        try: d = json.loads(Path('data/analytics/%s.json' % b).read_text())
        except Exception: continue
        agg = {}
        for v in d.get('videos', []):
            m = by.get(norm(v.get('title')))
            if not m or v.get('privacy') != 'public': continue
            try: age = (NOW - datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00'))).total_seconds() / 86400
            except Exception: continue
            if age < 3: continue
            vpd = v.get('views', 0) / max(age, 1)
            for s in set(x.replace('ace_', '') for x in m.get('styles', [])):
                a = agg.setdefault(s, {'n': 0, 'sum': 0.0}); a['n'] += 1; a['sum'] += vpd
        if not agg: print(b, 'no matched videos yet'); continue
        mean = sum(a['sum'] for a in agg.values()) / max(1, sum(a['n'] for a in agg.values()))
        out = {}
        for s, a in agg.items():
            vpd = a['sum'] / a['n']
            bias = 0.0 if a['n'] < 3 or mean <= 0 else max(-.35, min(.35, (vpd / mean - 1) * .5))
            out[s] = {'n': a['n'], 'vpd': round(vpd, 2), 'bias': round(bias, 2)}
        Path('data/learned/music-%s.json' % b).write_text(json.dumps({'updated': NOW.date().isoformat(), 'styles': out}, indent=1)); print(b, out)
main()
