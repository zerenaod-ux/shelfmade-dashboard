"""MindLore STORY SHORTS: ~65-second vertical stories told in the strict storytelling style (story_rules.py): a claim about YOUR life, the surprising past/research, named real evidence,
the viewer's doubt answered, a loop ending. Writes scripts to story-shorts/mindlore/<id>.json; gh_story_short.py renders them with the 2D stick-man engine.
  python story_short.py <count>"""
import json, os, re, sys, random, hashlib, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
BRAND = os.environ.get('BRAND', 'mindlore'); SM = BRAND == 'shelfmade'
OUT = B / 'story-shorts' / BRAND; HIST = B / ('data/mindlore/story-shorts.json' if BRAND == 'mindlore' else 'data/story-shorts-%s.json' % BRAND)
THEMES = ['working hours and rest', 'sleep', 'attention and distraction', 'memory', 'stress and fear', 'friendship and group size', 'music and emotion', 'food and mood', 'loneliness', 'boredom', 'habits',
          'crowds and strangers', 'a deadline and the knot in your stomach', 'why your heart pounds before you speak', 'why your hands sweat when you are nervous', 'why a song gives you chills', 'why you cannot fall asleep when you are tired', 'why bad news makes your chest tight', 'why you blush when someone looks at you', 'why waiting makes your skin crawl', 'why you yawn when others yawn', 'why you get hungry when you are stressed', 'time in nature', 'laughter and play', 'anger', 'curiosity', 'gratitude', 'multitasking', 'social media comparison', 'decision fatigue', 'creativity', 'dreams', 'community and belonging',
          'storytelling', 'morning light and body clock', 'silence and noise', 'learning a language', 'walking and thinking', 'money and happiness', 'touch and hugs', 'smiling and mood', 'procrastination',
          'first impressions', 'jealousy', 'trust', 'kindness', 'nostalgia', 'risk and thrill', 'sharing food', 'handwriting vs typing']

MORE_THEMES = ['why you replay embarrassing moments at night', 'why a smell can throw you back ten years', 'why you forget why you walked into a room', 'why you check your phone with no notification', 'why cold water wakes you up', 'why you talk to yourself', 'why you laugh at funerals', 'why a stranger smile feels good', 'why you get goosebumps from music', 'why the last bite tastes best', 'why you cannot tickle yourself', 'why time flies when you are busy', 'why you feel watched when alone', 'why your name catches your ear in a noisy room', 'why you crave sugar when tired', 'why you wake up just before the alarm', 'why you hold your breath when concentrating', 'why bad memories feel louder than good ones', 'why a messy desk changes your thinking', 'why you say yes when you want to say no', 'why queues feel longer than they are', 'why red makes you hungry', 'why you feel déjà vu', 'why you get a second wind', 'why your mind wanders in the shower', 'why you hate the sound of your own voice', 'why lists feel good to finish', 'why you see faces in clouds', 'why sad songs feel good', 'why you eat more with friends', 'why a deadline makes you suddenly productive', 'why you remember where you were on a big day', 'why you feel braver in a group', 'why you crave a nap at 3 pm', 'why you rewatch the same show', 'why a free sample makes you buy', 'why you cannot ignore a ringing phone', 'why gifts feel better to give', 'why you get stuck on a song', 'why you blame the weather for your mood', 'why you doubt yourself after a compliment', 'why you feel lighter after a good cry', 'why you walk faster when you are worried', 'why you open the fridge and stare', 'why you avoid the thing you love to do', 'why a pet calms you down', 'why you fidget when you are bored', 'why you remember insults for years', 'why a clean room clears your head', 'why you copy the people near you', 'why you feel sleepy after a big meal', 'why your first idea is rarely your best', 'why you feel guilty over small things', 'why you hum without noticing', 'why you pick the middle option', 'why you trust a confident voice', 'why you feel dizzy when you stand up fast', 'why you can read a mood from a face in a blink', 'why you get hiccups', 'why rain makes you sleepy', 'why you picture the worst before good news']
THEMES += MORE_THEMES
_WIN = {'on': False}
_STOP = set('why your you the and that this with from when what have does about into they them their there then than make makes feel feels'.split())
def _main_words(t): return set(w for w in re.findall(r'[a-z]{4,}', str(t).lower()) if w not in _STOP)
def _blocked(theme, h):
    # owner 2026-11-23: block any topic whose main words match the last 10 videos
    mw = _main_words(theme)
    if not mw: return False
    for i in h['items'][-10:]:
        if mw & (_main_words(i.get('theme', '')) | _main_words(i.get('title', ''))): return True
    return False
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def hist(): return load(HIST, {'items': []})
def pick_theme(h):
    used = [i.get('theme') for i in h['items'][-30:]]
    try:   # G4: a cloned winner idea goes first (MindLore)
        wf = B / ('data/winner-ideas-%s.json' % BRAND); q = load(wf, [])
        # owner 2026-11-23: a copied winner idea is used at most once in every 20 videos, and never if it matches the last 10 videos
        if q and not SM and not any(i.get('winner') for i in h['items'][-20:]):
            for k, t0 in enumerate(q):
                if not _blocked(t0, h):
                    q.pop(k); wf.write_text(json.dumps(q, indent=1)); _WIN['on'] = True; print('winner idea theme:', t0, flush=True); return t0
    except Exception: pass
    if SM:   # ShelfMade: "a classic book vs today"
        if len(h['items']) >= 1 and h['items'][-1].get('theme') and h['items'][-1].get('part', 1) < 3 and h['items'][-1].get('date', '') >= (datetime.date.today() - datetime.timedelta(days=3)).isoformat():
            return h['items'][-1]['theme']   # SERIES (owner OK 2026-11-11): the same book for 3 Shorts in a row, "Part 1/2/3"
        books = load(B / 'books.json', []); cand = [b for b in books if ('%s by %s' % (b['title'], b['author'])) not in used] or books
        b = random.choice(cand); return '%s by %s' % (b['title'], b['author'])
    used = [i.get('theme') for i in h['items'][-60:]]
    cand = [t for t in THEMES if t not in used and not _blocked(t, h)] or [t for t in THEMES if t not in used] or THEMES
    w = load(B / ('data/story-learn-%s.json' % BRAND), {}).get('theme') or {}   # learned from real views (story_learn.py); mostly exploration now (owner 2026-11-23: always new ideas)
    if w and random.random() > .75:
        best = sorted(cand, key=lambda t: -float(w.get(t, 0)))
        if w.get(best[0]): return best[0]
    return random.choice(cand)
def one(llm_call):
    import story_rules
    h = hist(); theme = pick_theme(h)
    part = (h['items'][-1].get('part', 1) + 1) if (SM and h['items'] and h['items'][-1].get('theme') == theme) else 1
    recent = [i['title'] for i in h['items'][-15:]]
    _recent_words = set(w for t in recent[-10:] for w in re.findall(r'[a-z]{4,}', t.lower()))   # DIVERSITY (owner 2026-11-15: topics and openings repeated)
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
            'Titles already used, do not repeat: %s.\nDIVERSITY (STRICT): the subject must be clearly DIFFERENT from every one of the last 10 titles above (different body part, animal, event or habit; no repeated key words such as face, shock, surprise, play, joy, kids if they appear above). Also vary the opening angle: study, history fact or everyday habit.\n' % (chan, theme, radar, recent) + (story_rules.rules('shelfmade' if SM else 'mindlore', short=True).replace('ONE narration of 150-190 words (about 60-70 seconds)', 'ONE narration of 70-90 words (about 30 seconds, ONE idea only, hook in the first 5 words)') if exp else story_rules.rules('shelfmade' if SM else 'mindlore', short=True)) +
            'Return JSON: {"public_title": "a \"How X works\" or \"Why X ...\" title, 4-8 words, plain words, ending with ONE fitting emoji (for example How Habits Really Form 🤔, Why Your Stomach Knots Up 😬); owner decision 2026-11-11: this style is what people want to hear; never a yes/no question, no hashtags", "hook": "the exact first sentence of the narration", "thumb": "2-5 WORD CAPS HEADLINE", '
            '"narration": "'+("70-90" if exp else "150-190")+' words, first sentence EXACTLY the hook", "claims": [{"claim":"...","who":"...","year":"...","place":"..."}]}.')
    if SM: base += '\nSERIES: this is Part %d of 3 about the same book. %s Put "Part %d" at the end of public_title. Use a different famous line or idea than the earlier parts (titles so far: %s).\n' % (part, 'Start with the most famous idea of the book.' if part == 1 else 'End with a hook that makes the viewer want Part %d.' % min(part + 1, 3) if part < 3 else 'Close the series with the takeaway.', part, recent[-3:])
    base += '\nONE OPTIONAL STYLE (use it ONLY if none of the last 5 titles used a body feeling; our best MindLore Short, 2026-11-09, "Why a deadline makes your stomach knot"): start from an everyday BODY FEELING the viewer has had (knot in the stomach, racing heart, sweaty hands, chills), speak straight to them ("You feel..."), give a surprising reason from real research with TWO real numbers, and keep it about 55 seconds. When the theme allows, a title like "Why a deadline makes your stomach knot" (Why + everyday thing + makes your + body feeling) is welcome; it is a statement about the viewer, not a yes/no question.\n'
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
        _tw = set(re.findall(r'[a-z]{4,}', str(d.get('public_title', '')).lower())) - {'your', 'why', 'how', 'what', 'that', 'this', 'with', 'from', 'when'}
        _hit = sorted(_tw & _recent_words)
        if not SM and len(_hit) >= 2: bad.append('the title repeats key words from recent videos (%s); choose a clearly different subject' % ', '.join(_hit[:4]))
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
    h['items'].append({'id': sid, 'title': out['public_title'], 'theme': theme, 'part': part, 'exp': exp, 'winner': bool(_WIN['on']), 'date': datetime.date.today().isoformat()}); h['items'] = h['items'][-200:]
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
