"""H1c: did the ~30s story Shorts (exp='s30', story_short.py) beat the normal 60-70s ones? Joins story history (title) to YouTube analytics (views/day, age>=3d),
following retitles via data/growth/title_log.json. Writes data/growth/exp-s30.json; story_short.py reads the verdict:
win (>=1.5x median views/day) -> 7 short ones per 14 days; lose (<=0.67x) -> stop the test; tie/collecting -> 3 per 14 days."""
import datetime, json, re, statistics
from pathlib import Path
OUT = Path('data/growth/exp-s30.json')
HIST = {'shelfmade': 'data/story-shorts-shelfmade.json', 'mindlore': 'data/mindlore/story-shorts.json'}
def jl(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def norm(t): return re.sub(r'[^a-z0-9 ]', '', str(t).lower()).strip()
def run():
    now = datetime.datetime.now(datetime.timezone.utc); log = jl('data/growth/title_log.json', []); res = {}
    for b, hp in HIST.items():
        vids = jl('data/analytics/%s.json' % b, {}).get('videos', []); by_title = {norm(v['title']): v for v in vids if v.get('title')}; by_id = {v['id']: v for v in vids}
        old2id = {norm(e['old']): e['id'] for e in log if e.get('brand') == b and e.get('old') and e.get('id')}
        grp = {'s30': [], 'normal': []}
        for it in jl(hp, {'items': []}).get('items', []):
            t = norm(it.get('title', '')); v = by_title.get(t) or by_id.get(old2id.get(t))
            if not v or not v.get('published'): continue
            try: age = (now - datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00'))).total_seconds() / 86400
            except Exception: continue
            if age < 3: continue
            grp['s30' if it.get('exp') == 's30' else 'normal'].append(float(v.get('views', 0)) / age)
        m = {k: (round(statistics.median(x), 3) if x else None) for k, x in grp.items()}; n = {k: len(x) for k, x in grp.items()}
        verdict = 'collecting'
        if n['s30'] >= 3 and n['normal'] >= 5 and m['normal']:
            r = (m['s30'] or 0) / m['normal']; verdict = 'win' if r >= 1.5 else 'lose' if r <= 0.67 else 'tie'
        res[b] = {'n': n, 'median_vpd': m, 'verdict': verdict}
    res['at'] = now.strftime('%Y-%m-%dT%H:%MZ'); OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(res, indent=1)); return res
def quota(brand):
    v = jl(str(OUT), {}).get(brand, {}).get('verdict')
    return 7 if v == 'win' else 0 if v == 'lose' else 3
if __name__ == '__main__': print(run())
