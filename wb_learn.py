"""Learning loop for whiteboard videos: matches our published ShelfMade videos (data/analytics/summary.json top list) to the topics in data/wb-history.json
and turns views into category weights (winners get picked more, losers less, everything keeps a floor so we keep exploring). Fail-soft: no data = equal weights."""
import json
from pathlib import Path
B = Path(__file__).resolve().parent


def _words(s):
    import re
    return {w for w in re.findall(r'[a-z]{4,}', s.lower())}


def weights():
    try:
        hist = json.loads((B / 'data' / 'wb-history.json').read_text())
        summ = json.loads((B / 'data' / 'analytics' / 'summary.json').read_text())
        vids = (summ.get('top', {}).get('shelfmade') or []) + (summ.get('recent', {}).get('shelfmade') or [])
    except Exception:
        return {}
    score, n = {}, {}
    for h in hist:
        hw = _words(h['topic'])
        for v in vids:
            if len(hw & _words(str(v.get('title', '')))) >= 2:
                score[h['cat']] = score.get(h['cat'], 0) + int(v.get('views', 0)); n[h['cat']] = n.get(h['cat'], 0) + 1
    if not score: return {}
    avg = {c: score[c] / n[c] for c in score}; mean = sum(avg.values()) / len(avg)
    return {c: max(0.4, min(3.0, avg[c] / mean)) for c in avg}
