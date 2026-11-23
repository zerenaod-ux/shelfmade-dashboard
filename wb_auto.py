"""Autonomous topic picker for whiteboard videos: invents a fresh, creative topic in ANY category, never repeating (history file).
Usage: python wb_auto.py  -> prints one topic line (also records it). Free AI via llm.json_call."""
import json, random, sys
from pathlib import Path

HIST = Path(__file__).parent / 'data' / 'wb-history.json'
CATS = ['money habits', 'how everyday things work', 'science and nature', 'history turning points', 'health and sleep habits', 'psychology of choices',
        'animals and how they live', 'space and the planet', 'food and where it comes from', 'tiny stories with a big lesson', 'work and career skills',
        'technology made simple', 'buildings, cities and transport', 'language and learning', 'myths people believe', 'big ideas from classic books explained simply']


def history():
    try: return json.loads(HIST.read_text())
    except Exception: return []


def pick_cat(h):
    """Explore every category, but favour ones whose videos did better (wb_learn weights); never the same category twice in a row."""
    try:
        import wb_learn; wt = wb_learn.weights()
    except Exception:
        wt = {}
    last = h[-1]['cat'] if h else None
    pool = [c for c in CATS if c != last]
    return random.choices(pool, weights=[wt.get(c, 1.0) for c in pool])[0]


def pick(llm=None):
    if llm is None:
        import llm as _l; llm = _l
    h = history(); cat = pick_cat(h); extra = ''
    try:
        import learned, winners
        extra = (learned.trending('shelfmade') or '')[:900] + (winners.follow_up('shelfmade') or '')[:500]
    except Exception:
        pass
    p = ('Invent 6 fresh whiteboard-explainer video topics in the category "%s". Each must be a concrete, curious, true idea a general viewer wants to learn in 6-8 minutes, '
         'drawable with simple pictures, no politics, no medical or investment advice. Do NOT repeat or resemble these already made: %s. '
         '%s Return {"topics":["plain-words topic",...]}.' % (cat, '; '.join(x['topic'] for x in h[-60:]) or 'none', extra))
    d = llm.json_call('You are a creative director for explainer videos. Return ONLY JSON.', p, temperature=1.0, max_tokens=800)
    low = [x['topic'].lower() for x in h]
    for t in d.get('topics', []):
        t = str(t).strip()[:140]
        if t and t.lower() not in low:
            HIST.parent.mkdir(exist_ok=True); h.append({'topic': t, 'cat': cat}); HIST.write_text(json.dumps(h[-300:], indent=1)); return t
    raise ValueError('no fresh topic')


if __name__ == '__main__':
    print(pick())
