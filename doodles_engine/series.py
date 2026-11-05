"""SERIES BIBLE for AnimationDoodles: turns random one-off skits into ONE ongoing show people follow (recurring cast, running gags, callbacks, episode numbers).
brief(kind) -> text appended to the writers' prompts (same text for every call until record() is called, so the scenes of one episode agree).
record(id, title, concept, kind) -> logs the finished episode and advances the gag rotation.  title(id, title, kind) -> 'Title | Leo & Mia #N' for the published title.
State: data/doodles/series.json (committed by the Doodles workflows). Every function fails soft: no bible problem can ever break a build."""
import json, random, datetime
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent; F = ROOT / 'data/doodles/series.json'
DEFAULT = {
    'show': 'Leo & Mia',
    'arc': "Leo's Big Plan: become 'a person who has it together' this season. Mia keeps score and is rarely impressed.",
    'cast': [
        {'name': 'Greg', 'desc': "Leo's boss, who only ever emails one word: 'Noted.' or 'Per my last email.' (seen small in the background, never in front of the faces)"},
        {'name': 'Brenda', 'desc': 'the nosy neighbour with a clipboard and opinions'},
        {'name': 'Dev', 'desc': "the barista who misspells Leo's name every single time (Leeo, Lyle, Leonard)"},
        {'name': 'Gerald', 'desc': "Leo's houseplant, whose health is a running worry"},
    ],
    'gags': [
        {'id': 'battery', 'text': "Mia's phone is always at 3% battery at the worst moment", 'uses': 0, 'last': 0},
        {'id': 'minute', 'text': "Leo says 'just one more minute' and it is never one minute", 'uses': 0, 'last': 0},
        {'id': 'gerald', 'text': "a quick status update on Gerald the plant (thriving, dramatic, or dying)", 'uses': 0, 'last': 0},
        {'id': 'greg', 'text': "Greg's one-word email arrives at the worst possible moment ('Noted.')", 'uses': 0, 'last': 0},
        {'id': 'dev', 'text': "the barista writes Leo's name wrong on the cup, again", 'uses': 0, 'last': 0},
        {'id': 'scoreboard', 'text': "Mia announces her 'I told you so' scoreboard", 'uses': 0, 'last': 0},
    ],
    'catch': {'mia': 'Anyway.', 'leo': 'Okay but hear me out.'},
    'episodes': [],
}
_CUR = {}
def load():
    try: return json.loads(F.read_text())
    except Exception: return json.loads(json.dumps(DEFAULT))
def save(b):
    F.parent.mkdir(parents=True, exist_ok=True); F.write_text(json.dumps(b, indent=1))
def _n(b, kind): return 1 + sum(1 for e in b['episodes'] if e.get('kind') == kind)
def brief(kind='short'):
    try:
        if kind in _CUR: return _CUR[kind]['text']
        b = load(); eps = b['episodes']; recent = [e.get('gag') for e in eps[-2:]]
        pool = [g for g in b['gags'] if g['id'] not in recent] or b['gags']
        g = sorted(pool, key=lambda g: (g.get('uses', 0), g.get('last', 0)))[0]
        rng = random.Random(len(eps) * 7919 + (1 if kind == 'full' else 0))
        cb = ''
        if eps and rng.random() < .6:
            e = rng.choice(eps[-6:]); cb = "a quick nod to the earlier episode '%s' (one short line a NEW viewer still understands)" % e['title']
        score = 7 + 2 * len(eps)
        text = ("\nSERIES BIBLE (AnimationDoodles is ONE ongoing show; viewers follow Leo and Mia, so continuity makes them subscribe. Keep it light, never the main plot, and always understandable to a NEW viewer):\n"
                "SEASON ARC: %s\nRECURRING PEOPLE (mention them or show them small in the background, never in front of the faces): %s\n"
                "RUNNING GAG TO WEAVE IN THIS TIME (one quick bit): %s.\nCALLBACK: %s.\nCATCHPHRASES (use each at most once, only if natural): Mia says '%s' / Leo says '%s'\n"
                "MIA'S 'TOLD YOU SO' SCOREBOARD currently stands at %d (she may announce it, it always goes up).\n") % (
                b['arc'], '; '.join('%s = %s' % (c['name'], c['desc']) for c in b['cast']), g['text'], cb or 'none this time', b['catch']['mia'], b['catch']['leo'], score)
        _CUR[kind] = {'text': text, 'gag': g['id'], 'cb': cb}
        return text
    except Exception:
        return ''
def record(item_id, title, concept, kind='short'):
    try:
        b = load(); cur = _CUR.pop(kind, None) or {}
        n = _n(b, kind)
        b['episodes'].append({'n': n, 'kind': kind, 'id': item_id, 'title': title, 'concept': concept, 'gag': cur.get('gag'), 'callback': bool(cur.get('cb')), 'date': datetime.date.today().isoformat()})
        total = len(b['episodes'])
        for g in b['gags']:
            if g['id'] == cur.get('gag'): g['uses'] = g.get('uses', 0) + 1; g['last'] = total
        b['episodes'] = b['episodes'][-300:]; save(b)
    except Exception:
        pass
def title(item_id, base, kind='short'):
    try:
        for e in load()['episodes']:
            if e['id'] == item_id and e.get('kind') == kind:
                return ('%s | %s %s' % (base, load()['show'], ('#%d' % e['n']) if kind == 'short' else ('Ep. %d' % e['n'])))[:100]
    except Exception:
        pass
    return base
