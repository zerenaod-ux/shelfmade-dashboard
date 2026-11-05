"""WEEKLY EXPERIMENT LOOP (runs inside learn.yml, GitHub, no Mac). For every brand+format keeps ONE experiment running: variant A vs variant B of one factor
(hook style, music energy ...). When each variant has >= MIN_N videos at least 3 days old, compares views per day: a variant that wins by >= 20% becomes the CHAMPION
(exp.choose uses it ~85% of the time, 15% keeps exploring), a draw is recorded as 'no clear difference'. Then the next experiment in the queue starts.
Writes data/experiments/{active,defaults,history}.json and report.md (opened as a phone-visible Issue by the workflow)."""
import datetime, json, re
from pathlib import Path
import exp
D = Path('data/experiments'); D.mkdir(parents=True, exist_ok=True)
NOW = datetime.datetime.now(datetime.timezone.utc); TODAY = NOW.date().isoformat()
MIN_N, WIN, MAXDAYS = 4, 1.2, 28
def norm(t): return re.sub(r'[^a-z0-9]+', ' ', (t or '').lower()).strip()[:60]
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def vpds(brand, kind, factor, since):
    log = load('review/music-log.json', {}); an = load('data/analytics/%s.json' % brand, {}); by = {norm(t): e for t, e in log.items()}
    out = {}
    for v in an.get('videos', []):
        e = by.get(norm(v.get('title')))
        if not e or e.get('brand') != brand or e.get('kind') != kind or (e.get('date') or '') < since or v.get('privacy') != 'public': continue
        var = (e.get('exp') or {}).get(factor)
        if not var: continue
        try: age = (NOW - datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00'))).total_seconds() / 86400
        except Exception: continue
        if age >= 3: out.setdefault(var, []).append(v.get('views', 0) / max(age, 1))
    return out
def main():
    active, defaults, hist = load(D / 'active.json', {}), load(D / 'defaults.json', {}), load(D / 'history.json', [])
    lines = ['# Weekly experiment report - %s' % TODAY, '']
    for key, queue in exp.QUEUE.items():
        brand, kind = key.split(':'); a = active.get(key)
        if a:
            r = vpds(brand, kind, a['factor'], a['started']); ns = {v: len(r.get(v, [])) for v in a['variants']}
            means = {v: (sum(r[v]) / len(r[v])) for v in a['variants'] if r.get(v)}
            enough = all(ns[v] >= MIN_N for v in a['variants'])
            days = (NOW.date() - datetime.date.fromisoformat(a['started'])).days
            if enough:
                best = max(means, key=means.get); worst = min(means, key=means.get)
                ratio = means[best] / max(means[worst], .01)
                res = {'key': key, 'factor': a['factor'], 'variants': a['variants'], 'n': ns, 'vpd': {v: round(m, 2) for v, m in means.items()}, 'ended': TODAY}
                if ratio >= WIN:
                    defaults['%s:%s' % (key, a['factor'])] = best; res['winner'] = best
                    lines.append('- **%s** %s: **%s wins** (%.0f%% more views/day; n=%s). It is now the default.' % (key, a['factor'], best, (ratio - 1) * 100, ns))
                else:
                    res['winner'] = None; lines.append('- **%s** %s: no clear difference (n=%s). Moving on.' % (key, a['factor'], ns))
                hist.append(res); active.pop(key); a = None
            elif days > MAXDAYS:
                hist.append({'key': key, 'factor': a['factor'], 'variants': a['variants'], 'n': ns, 'ended': TODAY, 'winner': None, 'note': 'not enough videos'})
                lines.append('- **%s** %s: stopped after %d days (n=%s, not enough videos). Moving on.' % (key, a['factor'], days, ns)); active.pop(key); a = None
            else:
                lines.append('- **%s** %s: testing %s vs %s, so far n=%s (needs %d each), day %d.' % (key, a['factor'], a['variants'][0], a['variants'][1], ns, MIN_N, days))
        if not a:
            done = {(h['key'], h['factor'], tuple(h['variants'])) for h in hist}
            nxt = next(((f, v) for f, v in queue if (key, f, tuple(v)) not in done), None)
            if nxt:
                active[key] = {'factor': nxt[0], 'variants': list(nxt[1]), 'started': TODAY}
                lines.append('- **%s**: NEW experiment %s: %s vs %s.' % (key, nxt[0], nxt[1][0], nxt[1][1]))
            else:
                lines.append('- **%s**: queue finished; champions in use (%s).' % (key, ', '.join('%s=%s' % (k.split(':', 2)[2], v) for k, v in defaults.items() if k.startswith(key + ':')) or 'none yet'))
    (D / 'active.json').write_text(json.dumps(active, indent=1)); (D / 'defaults.json').write_text(json.dumps(defaults, indent=1)); (D / 'history.json').write_text(json.dumps(hist, indent=1))
    (D / 'report.md').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines))
main()
