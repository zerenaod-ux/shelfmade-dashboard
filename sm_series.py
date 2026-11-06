"""SHELFMADE SERIES 'Book vs Today': what a classic book said, and what research says now. Every full video gets an episode number in its description. Fails soft.
State: gh-state/series-shelfmade.json (committed by full-video.yml)."""
import json, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
F = B / 'gh-state' / 'series-shelfmade.json'
SHOW = 'Book vs Today'
def load():
    try: return json.loads(F.read_text())
    except Exception: return {'show': SHOW, 'episodes': []}
def footer(script):
    try:
        s = load(); t = script.get('public_title', '')
        e = next((x for x in s['episodes'] if x['title'] == t), None)
        if not e:
            e = {'n': len(s['episodes']) + 1, 'title': t, 'date': datetime.date.today().isoformat()}
            s['episodes'].append(e); F.parent.mkdir(parents=True, exist_ok=True); F.write_text(json.dumps(s, indent=1))
        nxt = '' if e['n'] % 5 else ' Milestone episode.'
        return '\n\nPart of the series "%s": what a classic book said, and what research says now. Episode %d.%s New episodes every day.' % (SHOW, e['n'], nxt)
    except Exception:
        return ''
