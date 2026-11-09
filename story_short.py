"""MindLore STORY SHORTS: ~65-second vertical stories told in the strict storytelling style (story_rules.py): a claim about YOUR life, the surprising past/research, named real evidence,
the viewer's doubt answered, a loop ending. Writes scripts to story-shorts/mindlore/<id>.json; gh_story_short.py renders them with the 2D stick-man engine.
  python story_short.py <count>"""
import json, os, re, sys, random, hashlib, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
BRAND = os.environ.get('BRAND', 'mindlore'); SM = BRAND == 'shelfmade'
OUT = B / 'story-shorts' / BRAND; HIST = B / ('data/mindlore/story-shorts.json' if BRAND == 'mindlore' else 'data/story-shorts-%s.json' % BRAND)
THEMES = ['working hours and rest', 'sleep', 'attention and distraction', 'memory', 'stress and fear', 'friendship and group size', 'music and emotion', 'food and mood', 'loneliness', 'boredom', 'habits',
          'crowds and strangers', 'time in nature', 'laughter and play', 'anger', 'curiosity', 'gratitude', 'multitasking', 'social media comparison', 'decision fatigue', 'creativity', 'dreams', 'community and belonging',
          'storytelling', 'morning light and body clock', 'silence and noise', 'learning a language', 'walking and thinking', 'money and happiness', 'touch and hugs', 'smiling and mood', 'procrastination',
          'first impressions', 'jealousy', 'trust', 'kindness', 'nostalgia', 'risk and thrill', 'sharing food', 'handwriting vs typing']
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def hist(): return load(HIST, {'items': []})
def pick_theme(h):
    used = [i.get('theme') for i in h['items'][-30:]]
    try:   # G4: a cloned winner idea goes first (MindLore)
        wf = B / ('data/winner-ideas-%s.json' % BRAND); q = load(wf, [])
        if q and not SM: t0 = q.pop(0); wf.write_text(json.dumps(q, indent=1)); print('winner idea theme:', t0, flush=True); return t0
    except Exception: pass
    if SM:   # ShelfMade: "a classic book vs today"
        books = load(B / 'books.json', []); cand = [b for b in books if ('%s by %s' % (b['title'], b['author'])) not in used] or books
        b = random.choice(cand); return '%s by %s' % (b['title'], b['author'])
    cand = [t for t in THEMES if t not in used] or THEMES
    w = load(B / ('data/story-learn-%s.json' % BRAND), {}).get('theme') or {}   # learned from real views (story_learn.py); 30% exploration
    if w and random.random() > .3:
        best = sorted(cand, key=lambda t: -float(w.get(t, 0)))
        if w.get(best[0]): return best[0]
    return random.choice(cand)
def one(llm_call):
    import story_rules
    h = hist(); theme = pick_theme(h); recent = [i['title'] for i in h['items'][-15:]]
    # H1b TEST: our data says <=30s Shorts win ~7x; make the first 3 of every 14 days short (~30s), measured later by the scoreboard
    _lo, _hi, exp = 140, 200, ''
    try:
        try:
            import exp_eval; _q = exp_eval.quota(BRAND)   # H1c verdict: win -> 7, lose -> 0, else 3 per 14 days
        except Exception: _q = 3
        _cut = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
        if sum(1 for i in h['items'] if i.get('exp') == 's30' and i.get('date', '') >= _cut) < _q: exp = 's30'; _lo, _hi = 60, 100
    except Exception: pass
    radar = ''
    try:
        r = load(B / 'data/radar/mindlore.json', {}); radar = '\nToday\'s winning pattern on YouTube (borrow the pattern, never the words): %s' % ((r.get('hook_patterns') or [''])[0])
    except Exception: pass
    try:
        import growth; radar += growth.guidance(BRAND)   # H1: our own measured winners/losers, a nudge not a law
    except Exception: pass
    chan = ('ShelfMade, a channel that explains classic books for modern readers: the Short is "a classic book vs today", what this old book said and what later research found. THEME BOOK' if SM else 'MindLore, a psychology channel about how your mind works, explained with real research and how people lived long ago. THEME')
    base = ('You write a 60-70 second vertical Short for %s: %s.%s\n'
            'Titles already used, do not repeat: %s.\n' % (chan, theme, radar, recent) + (story_rules.rules('shelfmade' if SM else 'mindlore', short=True).replace('ONE narration of 150-190 words (about 60-70 seconds)', 'ONE narration of 70-90 words (about 30 seconds, ONE idea only, hook in the first 5 words)') if exp else story_rules.rules('shelfmade' if SM else 'mindlore', short=True)) +
            'Return JSON: {"public_title": "2 to 5 words, no emoji, a STATEMENT that starts with You or Your (our data: You/Your titles get about 4x the views of question titles), e.g. Your Brain Lies, You Forget Fast; never a yes/no question", "hook": "the exact first sentence of the narration", "thumb": "2-5 WORD CAPS HEADLINE", '
            '"narration": "'+("70-90" if exp else "150-190")+' words, first sentence EXACTLY the hook", "claims": [{"claim":"...","who":"...","year":"...","place":"..."}]}.')
    prompt = base; bad = ['no usable answer']; d = None
    for attempt in range(4):
        try: d = llm_call(prompt)
        except Exception as e: print('story_short: writer failed:', str(e)[:120], flush=True); continue
        if not isinstance(d, dict): continue
        nar = re.sub(r'\s+', ' ', str(d.get('narration', ''))).strip(); d['narration'] = nar; d['hook'] = str(d.get('hook', '')).strip()
        d['sections'] = [{'title': 'Story', 'narration': nar}]
        n = len(nar.split()); bad = []
        if not (_lo <= n <= _hi): bad.append('narration must be %s words (now %d)' % ('70-90' if exp else '150-190', n))
        if d['hook'] and not nar.startswith(d['hook']): bad.append('the narration must start with exactly the hook sentence')
        if re.search(r'[_#*]', nar): bad.append('no underscores, hashtags or stage directions')
        if not bad: bad = story_rules.check(d, 'shelfmade' if SM else 'mindlore', short=True)
        if not bad:
            v, rep = story_rules.verify_claims(d); bad = v; print('story_short: fact check:', '; '.join(rep), flush=True)
        if not bad: break
        print('story_short: attempt %d rejected: %s' % (attempt + 1, bad[:3]), flush=True)
        prompt = base + '\nYour last attempt failed these checks, fix them: ' + '; '.join(bad[:6])
    else:
        return None
    sid = 'st-%s-%s' % (datetime.date.today().strftime('%y%m%d'), hashlib.md5(d['hook'].encode()).hexdigest()[:5])
    bk = theme.split(' by ') if SM else ['', '']
    out = {'book_id': sid, 'title': bk[0], 'author': bk[-1] if SM else '', 'brand': BRAND, 'story_short': True, 'public_title': str(d.get('public_title') or d['hook'])[:95], 'hook': d['hook'], 'thumbnail_headline': str(d.get('thumb', ''))[:40].upper(),
           'sections': d['sections'], 'claims': d.get('claims', []), 'source_url': '', 'theme': theme, 'exp': exp}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / (sid + '.json')).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    h['items'].append({'id': sid, 'title': out['public_title'], 'theme': theme, 'exp': exp, 'date': datetime.date.today().isoformat()}); h['items'] = h['items'][-200:]
    HIST.parent.mkdir(parents=True, exist_ok=True); HIST.write_text(json.dumps(h, indent=1))
    print('story_short: wrote', sid, '-', out['public_title'], flush=True)
    return sid
def main(n):
    sys.path.insert(0, str(B))
    import ml_autoscripts as M
    made = 0
    for _ in range(n * 2):
        if made >= n: break
        if one(M._call): made += 1
    print('story_short: made', made); return made
if __name__ == '__main__':
    sys.exit(0 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 2) else 1)
