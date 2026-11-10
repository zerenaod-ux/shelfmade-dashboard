"""Daily table: views, likes, comments, subscribers per channel and platform. REAL numbers only, read from the files the collectors saved
(YouTube API + Buffer). A number the source does not give is shown as n/a, never guessed. Keeps a history so each day shows the change since the last snapshot."""
import json, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
A, OUT = B / 'data' / 'analytics', B / 'data' / 'daily'
BR = ('shelfmade', 'mindlore', 'doodles')


def load(p):
    try: return json.loads(p.read_text())
    except Exception: return None


def collect():
    snap = {}
    for b in BR:
        y = load(A / (b + '.json'))
        if y:
            v = y.get('videos', [])
            snap[b + '/youtube'] = {'views': sum(x.get('views', 0) for x in v), 'likes': sum(x.get('likes', 0) for x in v), 'comments': sum(x.get('comments', 0) for x in v),
                                    'subs': int(y['subscribers']) if str(y.get('subscribers', '')).isdigit() else None, 'videos': len(v), 'as_of': y.get('collected')}
        s = load(A / ('social-%s.json' % b))
        if s:
            for pl in ('instagram', 'tiktok'):
                ps = [p for p in s.get('posts', []) if p.get('platform') == pl and p.get('status') in ('sent', 'published')]
                snap[b + '/' + pl] = {'views': sum(p.get('views', 0) or 0 for p in ps), 'likes': sum(p.get('likes', 0) or 0 for p in ps),
                                      'comments': sum(p.get('comments', 0) or 0 for p in ps), 'subs': None, 'videos': len(ps), 'as_of': (s.get('collected') or '')[:10]}
    return snap


def fmt(n): return 'n/a' if n is None else format(n, ',')


def delta(now, old, k):
    if old is None or now.get(k) is None or old.get(k) is None: return ''
    d = now[k] - old[k]
    return ' (%+d)' % d if d else ' (0)'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    hist = load(OUT / 'history.json') or {}
    snap = collect()
    prev_days = sorted(d for d in hist if d < today)
    prev = hist[prev_days[-1]] if prev_days else {}
    hist[today] = snap
    for d in sorted(hist)[:-120]: hist.pop(d)
    (OUT / 'history.json').write_text(json.dumps(hist, indent=1))
    lines = ['# Daily numbers %s' % today, '', 'Real data only (YouTube API and Buffer). n/a = the platform does not give that number. In brackets = change since %s.' % (prev_days[-1] if prev_days else 'first snapshot'), '',
             '| Channel | Platform | Views | Likes | Comments | Subscribers | Posts | Data from |', '|---|---|---|---|---|---|---|---|']
    for k in sorted(snap):
        n, o = snap[k], prev.get(k)
        lines.append('| %s | %s | %s%s | %s%s | %s%s | %s%s | %s | %s |' % (k.split('/')[0], k.split('/')[1], fmt(n['views']), delta(n, o, 'views'), fmt(n['likes']), delta(n, o, 'likes'),
                                                                          fmt(n['comments']), delta(n, o, 'comments'), fmt(n['subs']), delta(n, o, 'subs'), n['videos'], n['as_of']))
    (OUT / 'latest.md').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines))


if __name__ == '__main__': main()
