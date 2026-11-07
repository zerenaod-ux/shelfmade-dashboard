"""GROWTH SCOREBOARD + FEATURE LIFTS (GitHub, no Mac; runs inside learn.yml).
Reads data/analytics/<brand>.json (YouTube numbers per video) and writes:
  data/growth/scoreboard.json  per brand: totals, subs, top/bottom videos by views per day, feature lifts, change vs 3 / 7 days ago
  data/growth/history.json     one row per day per brand (views, likes, subs) so growth can be measured against the 2026-11-06 baseline
guidance(brand) turns clear feature lifts into plain prompt lines for the writers (learned.guidance appends it). Small data = noisy, so a feature needs
>=5 videos with it AND >=5 without it before it is reported, and only lifts >=1.6x or <=0.6x of the channel median count."""
import datetime, json, re, statistics
from pathlib import Path

BRANDS = ('shelfmade', 'mindlore', 'doodles')
A, OUT = Path('data/analytics'), Path('data/growth')
MINAGE, MINN = 3, 5
UP, DOWN = 1.6, 0.6
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
CMD = re.compile(r'^(know|stop|don\'t|dont|never|why|how|what|where|when|who|your|you|this|these|do|try|ask|learn|read|watch|think|remember|forget)\b', re.I)


def secs(d):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0) if m else 0


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def feats(v):
    t = v.get('title', '') or ''
    d = secs(v.get('duration'))
    w = len(re.findall(r"[\w']+", t))
    out = {
        'format': 'short (up to 75s)' if d <= 75 else 'full video',  # used only to split Shorts from full videos
        'title length': 'short title (1-5 words)' if w <= 5 else 'medium title (6-8 words)' if w <= 8 else 'long title (9+ words)',
        'question title': 'question title' if '?' in t else 'not a question',
        'speaks to "you"': 'title says you/your' if re.search(r'\byou(r|rs|\'re|\'ve)?\b', t, re.I) else 'no you/your',
        'number in title': 'has a number' if re.search(r'\d', t) else 'no number',
        'emoji': 'has emoji' if EMOJI.search(t) else 'no emoji',
        'command/hook opener': 'opens with a direct word (know, stop, why, how, your...)' if CMD.match(t.strip()) else 'other opener',
    }
    if d and d <= 75:
        out['short length'] = 'up to 30s' if d <= 30 else '31-45s' if d <= 45 else '46-75s'
    try:
        p = datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00')) - datetime.timedelta(hours=6)
        out['publish time (Chicago)'] = 'morning (5-11)' if 5 <= p.hour < 11 else 'midday (11-17)' if 11 <= p.hour < 17 else 'evening (17-23)' if p.hour >= 17 else 'night (0-5)'
    except Exception:
        pass
    return out


def rows(brand):
    try:
        d = json.loads((A / (brand + '.json')).read_text())
    except (OSError, ValueError):
        return None, []
    out = []
    for v in d.get('videos', []):
        if v.get('privacy') != 'public':
            continue
        try:
            age = (now() - datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00'))).total_seconds() / 86400
        except Exception:
            continue
        if age < MINAGE:
            continue
        views = int(v.get('views') or 0)
        out.append({'id': v['id'], 'title': v.get('title', ''), 'views': views, 'vpd': round(views / max(age, 1), 2), 'age_days': round(age, 1),
                    'avg_percent': v.get('avgPercent'), 'subs': int(v.get('subsGained') or 0), 'likes': int(v.get('likes') or 0), 'f': feats(v)})
    return d, out


def lifts(rs):
    if len(rs) < 2 * MINN:
        return []
    med = statistics.median(r['vpd'] for r in rs) or 0.01
    groups = {}
    for r in rs:
        for k, val in r['f'].items():
            groups.setdefault((k, val), []).append(r['vpd'])
    res = []
    for (k, val), vs in groups.items():
        rest = [r['vpd'] for r in rs if r['f'].get(k) != val and k in r['f']]
        if len(vs) < MINN or len(rest) < MINN:
            continue
        m = statistics.median(vs)
        res.append({'feature': k, 'value': val, 'n': len(vs), 'median_vpd': round(m, 2), 'lift': round(m / med, 2), 'rest_median_vpd': round(statistics.median(rest), 2)})
    return sorted(res, key=lambda x: -x['lift'])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        hist = json.loads((OUT / 'history.json').read_text())
    except (OSError, ValueError):
        hist = []
    today = now().date().isoformat()
    hist = [h for h in hist if h.get('date') != today]
    row = {'date': today}
    board = {'updated': now().isoformat(timespec='seconds'), 'brands': {}}
    for b in BRANDS:
        d, rs = rows(b)
        if d is None:
            continue
        vids = d.get('videos', [])
        tot = {'videos': len(vids), 'views': sum(int(v.get('views') or 0) for v in vids), 'likes': sum(int(v.get('likes') or 0) for v in vids), 'subs': int(str(d.get('subscribers') or 0) or 0)}
        row[b] = tot
        hrs = round(sum(int(v.get('views') or 0) * float(v.get('avgSeconds') or 0) for v in vids) / 3600, 1)   # ESTIMATE: lifetime views x average seconds watched (YouTube counts the last 12 months)
        tot['est_watch_hours'] = hrs
        ranked = sorted(rs, key=lambda x: -x['vpd'])
        slim = lambda r: {k: r[k] for k in ('id', 'title', 'views', 'vpd', 'age_days', 'avg_percent', 'subs')}
        board['brands'][b] = {'totals': tot, 'measured_videos': len(rs), 'median_views_per_day': round(statistics.median([r['vpd'] for r in rs]), 2) if rs else None,
                              'top': [slim(r) for r in ranked[:5]], 'bottom': [slim(r) for r in ranked[-5:]] if len(ranked) > 5 else [], 'feature_lifts': lifts([r for r in rs if r['f']['format'].startswith('short')]), 'monetization': {'subs_needed': 1000, 'subs_now': tot['subs'], 'subs_pct': round(100 * tot['subs'] / 1000, 1), 'watch_hours_needed': 4000, 'est_watch_hours': hrs, 'hours_pct': round(100 * hrs / 4000, 1), 'note': 'YouTube Partner Program: 1,000 subscribers AND 4,000 public watch hours in 12 months (or 10 million Shorts views in 90 days). Hours here are an estimate.'}, 'lifts_scope': 'Shorts only (full videos behave differently, mixing them fooled the numbers)'}
    hist.append(row); hist = sorted(hist, key=lambda h: h['date'])[-400:]
    for b, bd in board['brands'].items():
        for days in (3, 7):
            old = next((h for h in reversed(hist[:-1]) if (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(h['date'])).days >= days and b in h), None)
            if old:
                bd['change_%dd' % days] = {k: bd['totals'][k] - old[b].get(k, 0) for k in ('views', 'likes', 'subs', 'videos')}
    (OUT / 'history.json').write_text(json.dumps(hist, indent=1))
    (OUT / 'scoreboard.json').write_text(json.dumps(board, indent=1))
    print('growth scoreboard:', {b: (v['totals']['views'], v['measured_videos'], len(v['feature_lifts'])) for b, v in board['brands'].items()})


def guidance(brand):
    """Plain lines for the writers: only clear, repeated patterns (see module note)."""
    try:
        bd = json.loads((OUT / 'scoreboard.json').read_text())['brands'][brand]
    except Exception:
        return ''
    more = ['%s (%s): %.1fx the channel median views/day, %d videos' % (x['feature'], x['value'], x['lift'], x['n']) for x in bd.get('feature_lifts', []) if x['lift'] >= UP][:3]
    less = ['%s (%s): only %.1fx the median, %d videos' % (x['feature'], x['value'], x['lift'], x['n']) for x in sorted(bd.get('feature_lifts', []), key=lambda x: x['lift']) if x['lift'] <= DOWN][:3]
    if not (more or less):
        return ''
    t = '\nHARD NUMBERS FROM OUR CHANNEL (measured, small data, use as a nudge not a law): '
    if more:
        t += 'WORKS BETTER: ' + ' | '.join(more) + '. '
    if less:
        t += 'WORKS WORSE: ' + ' | '.join(less) + '. '
    return t + '\n'


if __name__ == '__main__':
    main()
