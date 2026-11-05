"""STRICT STORYTELLING RULES (MindLore + ShelfMade). Every new script, full video or Short, must be told this way.
The model that writes the script gets RULES text in its prompt; check() then rejects any draft that breaks the rules and the writer retries with the exact complaints.
verify_claims() asks Wikipedia whether the researchers/groups the script names exist, so an invented study is caught before anything is built.

Reference style (owner-approved):
  "You work 40 hours a week. Ancient humans worked way less than you think. In the 1960s, anthropologist Richard Lee studied the Kalahari !Kung people ... and tracked exactly how
   they spent their time. The result? Adults spent only about 15 to 20 hours a week finding food. That's it. ... So why do we assume ancient life was constant struggle? Because ...
   So next time you're exhausted after a 9-to-5, remember ... You work"      (the last words echo the opening, so it loops)
"""
import re, json, urllib.request, urllib.parse

CORE = (
    '\nSTORY STYLE (STRICT, no exceptions):\n'
    '1. OPENING: first a plain claim about the viewer\'s OWN life using "you" or "your" (for example "You work 40 hours a week."), then the surprise: the past, ancient people or real research say something different. Never start with a greeting, the channel name or "In this video".\n'
    '2. SHORT SPOKEN SENTENCES: one idea each, 6-14 words on average. Plain words. Use the pivot lines "The result?" and "That\'s it." at least once.\n'
    '3. REAL EVIDENCE: name a researcher or institution, the place or group studied, a year or decade, and a number ("about 15 to 20 hours a week"). Say "about" for approximate figures. Use ONLY findings you are certain are real and well known. If you are not sure, leave it out. Never invent a study, a name, a quote or a number.\n'
    '4. WIDE VIEW: after the first study add that it was not one group (other studies or societies show the same), and give the name of the idea if it has one.\n'
    '5. THE VIEWER\'S DOUBT: ask the question the viewer is thinking ("So why do we assume ...?") and answer it with a fact, not an opinion.\n'
    '6. CLOSE: bring it back to the viewer\'s life today ("So next time you ..., remember ...") and make the LAST WORDS repeat the first words of the opening line, so the video loops.\n'
    '7. NEVER write: welcome, in this video, let\'s dive, delve, in conclusion, subscribe, thanks for watching, stay tuned, without further ado.\n'
    '8. Return an extra JSON field "claims": [{"claim":"what the study found","who":"researcher or group, e.g. Richard Lee","year":"1966 or 1960s","place":"where"}] with at least 2 real, checkable claims that you actually use in the narration.\n')
SHELF = ('\nSHELFMADE ANGLE: the video is "a book vs today". Open with a claim about the viewer\'s life, then show what the old book said about it and what later research found (named researcher, year, number). '
         'Be fair to the book: say what it got right and where research differs.\n')
MIND = ('\nMINDLORE ANGLE: the video is "what ancient humans / old thinkers knew vs what you do now", backed by named real studies.\n')
BANNED = re.compile(r"\b(welcome|in this video|let'?s dive|delve|in conclusion|subscribe|thanks? for watching|stay tuned|without further ado|today we(?: are|'re)? going to)\b", re.I)
CONTRAST = re.compile(r"\b(ancient|past|years? ago|centur(?:y|ies)|then|once|used to|history|historic\w*|today|now|modern|really|actually|wrong|myth|less|more than|fewer|decades?|old(?:er)?|before|warned|wrote|said|knew|believed|thought|claimed|argued|predicted|saw|researchers?|studies|study|scientists?|psycholog\w+|anthropolog\w+)\b", re.I)
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])s?\b")
STOP = set('a an the and or but of to in on at for with from by is are was were be been it its this that these those you your we our they their he she his her i me my as if so than then there here do does did not no yes can could would should will just very really also about into over under up down out more most some any all each every one what why how who when'.split())

def sentences(t): return [s.strip() for s in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', t).strip()) if s.strip()]
def toks(t): return [w for w in re.findall(r"[a-z']+", t.lower()) if w not in STOP and len(w) > 2]

def rules(brand, short=False):
    txt = CORE + (SHELF if brand == 'shelfmade' else MIND)
    if short: txt += 'SHORT FORMAT: ONE narration of 150-190 words (about 60-70 seconds), same style, same loop ending.\n'
    return txt

def check(d, brand='mindlore', short=False):
    """Returns a list of problems (empty = the draft follows the storytelling rules)."""
    bad = []
    secs = d.get('sections') or []
    narr = ' '.join(str(s.get('narration', '')) for s in secs) if secs else str(d.get('narration', ''))
    sents = sentences(narr)
    if len(sents) < 6: return ['too few sentences']
    avg = sum(len(s.split()) for s in sents) / len(sents)
    if avg > (15 if short else 17): bad.append('sentences are too long (average %.0f words); use short spoken sentences of 6-14 words' % avg)
    first = (secs[0].get('narration') if secs else narr) or ''
    fs = sentences(first)[:3]; head = ' '.join(fs)
    if not re.search(r"\b(you|your|you're)\b", fs[0] if fs else '', re.I) and not re.search(r'\d', fs[0] if fs else ''): bad.append('the FIRST sentence must be a claim about the viewer\'s own life using you/your')
    if not CONTRAST.search(head) and not YEAR.search(head): bad.append('within the first 3 sentences give the surprise: the past/ancient people/research says something different')
    if BANNED.search(narr): bad.append('remove filler openers/closers: "%s"' % BANNED.search(narr).group(0))
    years = set(m.group(0) for m in YEAR.finditer(narr))
    if len(years) < (1 if short else 2): bad.append('name at least %d real year(s) or decade(s) of the evidence' % (1 if short else 2))
    if not re.search(r"\d|percent|million|billion|hours|times as", narr): bad.append('include at least one real number')
    q = sum(1 for s in sents if s.endswith('?'))
    if q < (1 if short else 3): bad.append('ask the viewer\'s doubt as a question (at least %d question sentences) and answer it' % (1 if short else 3))
    if not re.search(r"\bThat's it\b|\bThat is it\b|\bThe result\b", narr): bad.append('use the pivot "The result?" or "That\'s it."')
    hook = d.get('hook') or (sents[0] if sents else '')
    last = ' '.join(sents[-2:]); ht = set(toks(hook)); lt = set(toks(last))
    if ht and len(ht & lt) < 1: bad.append('the last words must echo the opening line (reuse its key words) so the video loops')
    cl = d.get('claims')
    if not isinstance(cl, list) or len([c for c in cl if isinstance(c, dict)]) < 2: bad.append('add "claims": at least 2 real checkable claims with who/year/place')
    else:
        used = 0
        for c in cl:
            who = str(c.get('who', '')).strip(); yr = str(c.get('year', ''))
            if len(who) < 3 or not YEAR.search(yr): bad.append('each claim needs a real "who" and a year'); break
            last_w = re.findall(r"[A-Za-z!'À-ɏ-]+", who)[-1].lower() if re.findall(r"[A-Za-z!'À-ɏ-]+", who) else ''
            if last_w and last_w in narr.lower(): used += 1
        if used < 1 and not bad: bad.append('the researchers/groups in "claims" must be named in the narration')
    return bad

def _wiki(query):
    url = 'https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch=' + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={'User-Agent': 'MindLoreFactCheck/1.0 (public educational channel)'})
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read().decode('utf-8', 'ignore'))['query']['search']

def verify_claims(d):
    """Soft fact check: every named researcher/group should turn up on Wikipedia. Returns (problems, report). Network trouble = no verdict (never blocks a build)."""
    cl = [c for c in (d.get('claims') or []) if isinstance(c, dict)]
    report = []; missing = []; checked = 0
    for c in cl[:5]:
        who = str(c.get('who', '')).strip(); place = str(c.get('place', '')).strip(); parts = re.findall(r"[A-Za-z!'À-ɏ-]+", who)
        if not parts: continue
        sur = parts[-1].lower()
        try: res = _wiki(('%s %s' % (who, place)).strip())
        except Exception: return [], ['fact check skipped (Wikipedia not reachable)']
        checked += 1
        hit = any(sur in (r.get('title', '') + ' ' + re.sub('<[^>]+>', '', r.get('snippet', ''))).lower() for r in res)
        report.append('%s: %s' % (who, 'found on Wikipedia' if hit else 'NOT FOUND'))
        if not hit: missing.append(who)
    bad = []
    if checked and len(missing) * 2 > checked: bad.append('these named researchers/groups could not be verified, replace them with well-known real studies you are certain of: ' + ', '.join(missing))
    return bad, report

def evidence_lines(d):
    out = []
    for c in (d.get('claims') or []):
        if isinstance(c, dict) and c.get('who'): out.append('%s (%s%s): %s' % (c.get('who'), c.get('year', ''), ', ' + c['place'] if c.get('place') else '', str(c.get('claim', ''))[:160]))
    return out
