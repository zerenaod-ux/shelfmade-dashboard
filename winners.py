"""WINNERS LOOP. Uses the viewer numbers already collected (data/analytics/summary.json) so the channels double down on what viewers proved they like.
top_ids()        -> YouTube ids of the best videos (re-cut Shorts for these full videos first)
follow_up(brand) -> prompt text for the script writers: go deeper on a topic a winning video already proved (same audience question, NEW angle, never the same title).
Fail-soft: any problem returns [] / ''."""
import json, random, datetime
from pathlib import Path
B = Path(__file__).resolve().parent


def _top(brand, n=5, min_views=120):
    try:
        d = json.loads((B / 'data' / 'analytics' / 'summary.json').read_text())
        return [x for x in (d.get('top', {}).get(brand) or [])[:n] if int(x.get('views', 0)) >= min_views]
    except Exception:
        return []


def top_ids():
    out = []
    for b in ('mindlore', 'shelfmade', 'doodles'):
        out += [x['id'] for x in _top(b, 5, 1)]
    return out


def follow_up(brand):
    try:
        t = _top(brand)
        if not t:
            return ''
        w = random.Random(datetime.date.today().toordinal()).choice(t[:3])
        title = str(w.get('title', ''))[:120]
        return ('\nWINNER FOLLOW-UP (our viewers already proved this topic with %s views): the video "%s". Write about the SAME audience question or a close neighbour of it, '
                'but with a NEW angle and a NEW title; never repeat or paraphrase that title. Go deeper where it stopped.\n') % (w.get('views'), title)
    except Exception:
        return ''
