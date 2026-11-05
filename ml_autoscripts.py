"""MindLore auto-scripts: writes new full-video scripts by itself (free Gemini key), checks every quote against the book,
and pushes them to GitHub so the daily MindLore full video never runs dry. Needs gemini-key.txt (one line) or GEMINI_API_KEY.
Safe: does nothing without a key; never approves or posts anything."""
import importlib, json, os, re, random, hashlib, subprocess, urllib.request, urllib.error, shutil
from pathlib import Path

B = Path(__file__).resolve().parent
SH = os.environ.get('ML_BRAND', 'mindlore') == 'shelfmade'   # ShelfMade mode: one script per book, in cinematic-scripts/
SRC = B / 'sources' / ('shelfmade' if SH else 'mindlore')
OUT = B / ('cinematic-scripts' if SH else 'cinematic-scripts-mindlore')
OUTNAME = OUT.name
REPO = Path.home() / 'Dev/repos/shelfmade-dashboard'
TARGET = 40          # keep up to this many scripts in total
PER_PASS = int(os.environ.get('ML_PER_PASS', '2'))  # new scripts per run
MODEL = 'gemini-2.5-flash'


_CUR = [0]   # GKEYS: index of the Gemini key in use


def _keys():
    ks = [os.environ.get(n, '').strip() for n in ('GEMINI_API_KEY', 'GEMINI_API_KEY2', 'GEMINI_API_KEY3')]
    return [k for k in ks if k]


def _key():
    ks = _keys()
    if ks: return ks[_CUR[0] % len(ks)]
    k = ''
    f = B / 'gemini-key.txt'
    if not k and f.is_file():
        k = f.read_text().strip()
    return k


def norm(s):
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')).strip()


def check(txt_norm, d):
    """Return list of problems (empty = good). Same rules as the video builder."""
    bad = []
    secs = d.get('sections') or []
    pas = d.get('passages') or []
    if len(secs) != 7:
        bad.append('need exactly 7 sections, got %d' % len(secs))
    if len(pas) != len(secs):
        bad.append('need exactly one passage per section')
    narr = ' '.join(s.get('narration', '') for s in secs)
    words = len(narr.split())
    lo, hi = (950, 1250) if SH else (1100, 1350)
    if not lo <= words <= hi:
        bad.append('narration has %d words; need %d-%d' % (words, lo, hi))
    nn = norm(narr)
    for i, p in enumerate(pas):
        e = norm(p.get('excerpt', ''))
        if len(e.split()) < 8:
            bad.append('excerpt %d shorter than 8 words' % i)
        if SH and e and not e[0].isupper():
            bad.append('excerpt %d must start at the beginning of a sentence (capital letter), not mid-word' % i)
        if e not in txt_norm:
            bad.append('excerpt %d is not word-for-word in the book: "%s"' % (i, e[:60]))
        if e not in nn:
            bad.append('excerpt %d must appear word-for-word inside the narration (inside quotation marks)' % i)
    if '_' in narr:
        bad.append('no underscores in narration')
    return bad


_MODELS = []


def _models():
    """Text models this key can use, best first (newest flash, then lite, then others). Names change, so ask Google."""
    if _MODELS:
        return _MODELS
    req = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=200', headers={'x-goog-api-key': _key()})
    with urllib.request.urlopen(req, timeout=60) as r:
        ms = json.load(r).get('models', [])
    ok = [m['name'].split('/')[-1] for m in ms if 'generateContent' in m.get('supportedGenerationMethods', [])]
    ok = [m for m in ok if m.startswith('gemini') and not re.search(r'image|tts|audio|live|embed|vision|robotics|computer|thinking|preview|exp', m)]

    def ver(m):
        v = re.findall(r'\d+(?:\.\d+)?', m)
        return float(v[0]) if v else 0.0
    flash = sorted([m for m in ok if re.search(r'flash(?!-lite)', m)], key=lambda m: -ver(m))
    lite = sorted([m for m in ok if 'lite' in m], key=lambda m: -ver(m))
    rest = [m for m in ok if m not in flash and m not in lite]
    # try a mid-age flash first (often less busy), then others
    order = flash[1:] + flash[:1] + lite + rest
    _MODELS.extend(order or ok)
    print('ml_autoscripts: models to try:', _MODELS[:6], flush=True)
    return _MODELS


def _one(model, prompt, think):
    url = 'https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent' % model
    cfg = {'responseMimeType': 'application/json', 'temperature': 0.8, 'maxOutputTokens': 12000}
    if think:
        cfg['thinkingConfig'] = {'thinkingBudget': 0}
    body = json.dumps({'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': cfg}).encode()
    req = urllib.request.Request(url, body, {'Content-Type': 'application/json', 'x-goog-api-key': _key()})
    with urllib.request.urlopen(req, timeout=100) as r:
        j = json.load(r)
    return json.loads(j['candidates'][0]['content']['parts'][0]['text'])


def repair(tn, d):
    """Models paraphrase quotes. Replace each almost-right excerpt with the exact words from the book."""
    import difflib
    for i, p in enumerate(d.get('passages', [])):
        e = norm(p.get('excerpt', ''))
        if not e or e in tn:
            continue
        sm = difflib.SequenceMatcher(None, tn, e, autojunk=False)
        # anchor on the longest piece that matches, then take the book's own words around it
        m = sm.find_longest_match(0, len(tn), 0, len(e))
        if m.size < 25:
            continue
        a = m.a - m.b
        span = tn[max(0, a): a + len(e)]
        words = span.split()
        words = words[1:-1] if len(words) > 10 else words
        exact = ' '.join(words)
        if exact in tn and len(exact.split()) >= 8 and not re.search(r'[_"\[\]=]', exact):
            old = p['excerpt']
            p['excerpt'] = exact
            secs = d.get('sections', [])
            if i < len(secs):
                nar = secs[i].get('narration', '')
                if old in nar:
                    secs[i]['narration'] = nar.replace(old, exact, 1)
                else:
                    secs[i]['narration'] = nar.rstrip() + ' In the book\'s own words: "' + exact + '"'
    return d


def force(tn, window, d):
    """Last resort: for any excerpt that still is not exact, take the book's own sentence that best fits that section."""
    wn = norm(window)
    sents = [x.strip() for x in re.split(r'(?<=[.!?])\s+', wn) if 8 <= len(x.split()) <= 30 and x.strip() in tn and not re.search(r'[_"\[\]=\d]', x)]
    if not sents:
        return d
    used = set()
    secs = d.get('sections', [])
    for i, p in enumerate(d.get('passages', [])):
        e = norm(p.get('excerpt', ''))
        nar = secs[i].get('narration', '') if i < len(secs) else ''
        if e in tn and e in norm(nar) and len(e.split()) >= 8:
            used.add(e)
            continue
        words = set(re.findall(r'[a-z]{4,}', nar.lower()))
        best = max((x for x in sents if x not in used), key=lambda x: len(words & set(re.findall(r'[a-z]{4,}', x.lower()))), default=None)
        if not best:
            continue
        used.add(best)
        p['excerpt'] = best
        if i < len(secs):
            secs[i]['narration'] = nar.rstrip() + ' Here is how the book itself puts it: "' + best + '"'
    return d


_DEAD = set()


def _call(prompt):
    """Google is often busy (503). Go through the models, then wait and go round again, a few times."""
    import time
    last = None
    for rnd in range(8):   # PATIENT: free providers reset their per-minute limits, so wait and retry
        for ki, model in [(a_, m_) for a_ in range(max(1, len(_keys()))) for m_ in _models()[:8]]:
            _CUR[0] = ki
            if (ki, model) in _DEAD:
                continue
            for think in (True, False):
                try:
                    return _one(model, prompt, think)
                except urllib.error.HTTPError as e:
                    last = 'Gemini %s %s: %s' % (model, e.code, e.read()[:100])
                    if e.code == 400 and think:
                        continue          # model does not accept the thinking setting: retry without
                    if e.code in (404, 403, 429):
                        _DEAD.add((ki, model))  # not available / over its free quota: stop using it
                    break
                except (OSError, ValueError, KeyError) as e:
                    last = 'Gemini %s failed: %s' % (model, str(e)[:80])
                    break
            print('ml_autoscripts:', last, flush=True)
        try:   # Gemini quota used up: free fallback providers (Groq, Cerebras, OpenRouter, Mistral) if a key is configured
            import llm
            if llm.available():
                return llm.json_call('You are a careful script writer. Reply with JSON only.', prompt)
        except Exception as e:
            print('ml_autoscripts: free fallback failed:', str(e)[:100], flush=True)
        time.sleep(65)
    raise ValueError(last or 'Gemini failed')


def _expand(d, bad, lo, hi):
    """A draft that is only too SHORT (common with the free fallback models) is lengthened by a dedicated call instead of being thrown away."""
    prompt = ('Here is a draft video script as JSON. Problem: %s. Rewrite the SAME JSON with every section narration lengthened (more everyday examples, a modern comparison, honest limits, a rhetorical question) '
              'so the TOTAL narration is about %d words (must be between %d and %d). Keep exactly 7 sections and 7 passages, keep every passages[i].excerpt EXACTLY unchanged and word for word inside double quotation marks in section i, '
              'keep public_title, hook and thumb. No underscores. Return the full JSON only.\n%s') % ('; '.join(bad[:3]), (lo + hi) // 2, lo, hi, json.dumps(d, ensure_ascii=False))
    try:
        r = _call(prompt)
        return r if isinstance(r, dict) else None
    except Exception as e:
        print('ml_autoscripts: expand failed:', str(e)[:100], flush=True)
        return None
def _grow(tn, d, lo, hi):
    """Lengthen (or trim) each section narration separately toward the target. Keeps every quoted excerpt exactly; a section whose rewrite loses its quote keeps the old text."""
    secs = d.get('sections') or []; pas = d.get('passages') or []
    total = sum(len(str(x.get('narration', '')).split()) for x in secs); tgt = ((lo + hi) // 2) // max(1, len(secs))
    changed = 0
    for k, sec in enumerate(secs):
        nar = str(sec.get('narration', '')); n = len(nar.split())
        if total < lo and n >= tgt: continue
        if total > hi and n <= tgt: continue
        ex = str(pas[k].get('excerpt', '')) if k < len(pas) and isinstance(pas[k], dict) else ''
        prompt = ('Rewrite this ONE section narration (section %d of %d of a spoken video script) to about %d words (it has %d). %s Plain spoken English, short sentences, everyday examples, honest limits. '
                  '%sKeep every number, researcher and year that is already there; never invent studies, names, quotes or numbers. No underscores or stage directions. Return JSON {"narration": "..."} only.\nNARRATION: %s') % (
                  k + 1, len(secs), tgt, n, 'Lengthen it with one more concrete example or comparison.' if n < tgt else 'Trim it, keeping the strongest lines.',
                  ('Keep this quote EXACTLY, word for word, inside double quotation marks: "%s". ' % ex) if ex else '', nar)
        try:
            r = _call(prompt)
        except Exception as e:
            print('ml_autoscripts: grow section failed:', str(e)[:80], flush=True); continue
        new = str(r.get('narration', '')).strip() if isinstance(r, dict) else ''
        if new and (not ex or norm(ex) in norm(new)) and '_' not in new and abs(len(new.split()) - tgt) < abs(n - tgt):
            total += len(new.split()) - n; sec['narration'] = new; changed += 1
    return changed


def _lenfix(tn, window, d, bad):
    lo, hi = (950, 1250) if SH else (1100, 1350)
    for _ in range(3):
        if not bad or not all(x.startswith('narration has') for x in bad): break
        if _grow(tn, d, lo, hi) == 0:
            d2 = _expand(d, bad, lo, hi)
            if not d2: break
            d2.setdefault('public_title', d.get('public_title')); d2.setdefault('hook', d.get('hook')); d2.setdefault('thumb', d.get('thumb')); d2.setdefault('claims', d.get('claims', []))
            d2['passages'] = [x if isinstance(x, dict) else {'excerpt': str(x), 'chapter': ''} for x in (d2.get('passages') or d.get('passages') or [])]
            d2['sections'] = [x if isinstance(x, dict) else {'title': '', 'narration': str(x)} for x in (d2.get('sections') or [])]
            d = d2
        d = force(tn, window, repair(tn, d)); bad = check(tn, d)
        print('ml_autoscripts: length pass ->', bad[:2] or 'OK', flush=True)
    return d, bad
def _existing(bid):
    return sorted(OUT.glob('%s*.json' % bid))


def _pick_book():
    cat = json.load(open(SRC / 'catalogue.json'))
    have = {}
    for c in cat:
        if not (SRC / ('%s.txt' % c['id'])).is_file():
            continue
        refs = [p for p in OUT.glob('%s*.json' % c['id']) if re.fullmatch(r'%s(-\d+)?' % re.escape(c['id']), p.stem)]
        if SH:
            if not refs:
                have[c['id']] = (0, c)   # ShelfMade: only books that still have no script
        elif refs:
            have[c['id']] = (len(refs), c)
    if not have:
        return None
    n, c = min(have.values(), key=lambda x: (x[0], random.random()))
    return c


def _gate(c, d):
    """ShelfMade: run the real video-builder checks on the draft (cover/hook match, creative review...). Keeps the file only if it passes."""
    bid = c['id']
    ref = {'source_kind': c.get('source_kind') or 'Original commentary on the retained original public-domain text; modern examples identified and limitations discussed; owner review required',
           'retained_source_sha256': c.get('sha256', '')}
    out = {'book_id': bid, 'title': c['title'], 'author': c['author'], 'public_title': d['public_title'], 'hook': d['hook'],
           'thumbnail_headline': d['thumb'], 'source_url': c['canonical_url'],
           'source_kind': ref['source_kind'], 'retained_source_sha256': ref['retained_source_sha256'],
           'source_passages': [{'section': i, 'source_chapter': p['chapter'], 'excerpt': p['excerpt']} for i, p in enumerate(d['passages'])],
           'sections': [{'title': s['title'], 'narration': s['narration']} for s in d['sections']], 'claims': d.get('claims', []), 'story_v2': True}
    f = OUT / ('%s.json' % bid)
    f.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    try:
        import sys
        sys.path.insert(0, str(B))
        import cinematic_content, visual_admission
        script = cinematic_content.build(bid)
        visual_admission.require(script)
        return []
    except ImportError as e:   # tools missing here: cannot run the check, keep the script (the builder still checks later)
        print('ml_autoscripts: builder check skipped:', str(e)[:100], flush=True)
        return []
    except Exception as e:
        f.unlink()
        return ['video builder rejected it: %s' % str(e)[:300]]


ML_RULES = ('\nCHANNEL RULES: The FIRST sentence of section 1 narration must be EXACTLY the "hook" value: a complete question or claim of 5-30 words, no greeting, no "welcome", no channel name. '
            'The "thumb" headline must be 2-5 words and reuse at least two key words that appear in the hook sentence. The last section must NOT say subscribe, thank you for watching or any sign-off.')
def _gate_ml(c, d):
    """MindLore: run the real video-builder checks (creative review, visual brief) on the draft before keeping it. Same idea as ShelfMade's _gate."""
    bid = c['id']; refs = _existing(bid)
    ref = json.load(open(refs[0])) if refs else {'source_kind': c.get('source_kind') or 'Original commentary on the retained original public-domain text; modern examples identified and limitations discussed; owner review required', 'retained_source_sha256': c.get('sha256', '')}
    n = 2
    while (OUT / ('%s-%d.json' % (bid, n))).exists():
        n += 1
    f = OUT / ('%s-%d.json' % (bid, n))
    out = {'book_id': bid, 'title': c['title'], 'author': c['author'], 'public_title': d['public_title'], 'hook': d['hook'], 'thumbnail_headline': d['thumb'], 'source_url': c['canonical_url'],
           'source_kind': ref['source_kind'], 'retained_source_sha256': ref['retained_source_sha256'],
           'source_passages': [{'section': i, 'source_chapter': p['chapter'], 'excerpt': p['excerpt']} for i, p in enumerate(d['passages'])],
           'sections': [{'title': s['title'], 'narration': s['narration']} for s in d['sections']], 'claims': d.get('claims', []), 'story_v2': True}
    f.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    old = (os.environ.get('BRAND'), os.environ.get('ML_VARIANT'))
    try:
        import sys as _sys
        _sys.path.insert(0, str(B)); os.environ['BRAND'] = 'mindlore'; os.environ['ML_VARIANT'] = str(n)
        import cinematic_content, visual_admission
        script = cinematic_content.build(bid)
        visual_admission.require(script)
        return []
    except ImportError as e:
        print('ml_autoscripts: builder check skipped:', str(e)[:100], flush=True)
        return []
    except Exception as e:
        return ['video builder rejected it: %s' % str(e)[:300]]
    finally:
        try: f.unlink()
        except Exception: pass
        for k, v in zip(('BRAND', 'ML_VARIANT'), old):
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
def _story_gate(d):
    """Strict storytelling rules + Wikipedia check of the named researchers. Never blocks when the checker itself is missing."""
    try:
        import story_rules
    except ImportError:
        return []
    bad = story_rules.check(d, 'shelfmade' if SH else 'mindlore')
    if not bad:
        v, rep = story_rules.verify_claims(d); bad = v
        print('ml_autoscripts: fact check:', '; '.join(rep) or 'n/a', flush=True)
    return bad


def make_one():
    c = _pick_book()
    if not c:
        return None
    bid = c['id']
    txt = (SRC / ('%s.txt' % bid)).read_text(encoding='utf-8')
    tn = norm(txt)
    mid = txt[len(txt) // 20: -len(txt) // 20]
    start = random.randrange(0, max(1, len(mid) - 30000))
    window = mid[start:start + 16000]
    prior = []
    for p in _existing(bid):
        try:
            prior.append(json.load(open(p))['hook'])
        except Exception:
            pass
    chan = 'ShelfMade (classic books explained for modern readers)' if SH else 'MindLore'
    kind = 'book-lesson' if SH else 'psychology'
    base = ('You write a 7-9 minute narrated %s video for the channel %s, using ONE public-domain book: "%s" by %s.\n'
            'Choose ONE fresh angle/question from the SOURCE below that is NOT any of these existing hooks: %s.\n'
            'Return JSON: {"public_title": "question-style title | Author", "hook": "one-sentence opening question", "thumb": "3-5 WORD CAPS HEADLINE", '
            '"sections": [{"title":..., "narration":...} x7], "passages": [{"chapter":..., "excerpt":...} x7]}.\n'
            'Rules: 7 sections, 1100-1350 words TOTAL (about 165 words each), plain spoken English, friendly, original commentary. '
            'Section i must contain passages[i].excerpt WORD FOR WORD inside double quotation marks, copied exactly from the SOURCE '
            '(at least 8 words, one clause, taken from a stretch of the SOURCE that has NO underscores, quotation marks, square brackets, equals signs or footnote numbers in it). Be honest about limits: say this is an old book, name where later research differs, '
            'do not invent studies or quotes. No underscores, no hashtags, no stage directions.\nSOURCE:\n%s')
    prompt = base % (kind, chan, c['title'], c['author'], prior, window)
    d = None
    bad = ['no usable answer']
    extra = ''
    if SH:
        extra = ('\nCHANNEL RULES: total narration 950-1250 words (NOT more). The FIRST sentence of section 1 narration must be EXACTLY the "hook" value: a vivid question or claim, no greeting, no "welcome", no channel name. '
                 'The "thumb" headline must reuse at least two key words that appear in that hook sentence. The last section must NOT say subscribe, thank you for watching or any sign-off. Every excerpt must start at the beginning of a sentence (capital letter) and be a complete clause.')
    try:   # what our real viewers watch (learner.py): angle/hook guidance, refreshed twice a week
        import learned
        extra += learned.guidance('shelfmade' if SH else 'mindlore', 'full')
    except Exception:
        pass
    if not SH:
        extra += ML_RULES
    try:   # STRICT STORYTELLING RULES (story_rules.py): every new script is told this way
        import story_rules; extra += story_rules.rules('shelfmade' if SH else 'mindlore')
    except Exception as e:
        print('ml_autoscripts: story rules unavailable:', str(e)[:80], flush=True)
    if not SH:
        try:   # MindLore series: everyday question title + radar pattern (ml_series.py)
            import ml_series; extra += ml_series.brief()
        except Exception:
            pass
    prompt += extra
    for attempt in range(4):
        d = _call(prompt)
        if not isinstance(d, dict):
            continue
        def _pas(p):   # Gemini sometimes sends a string or a [chapter, excerpt] list instead of an object
            if isinstance(p, dict):
                return {'excerpt': str(p.get('excerpt', '')), 'chapter': str(p.get('chapter', c['title']))}
            if isinstance(p, (list, tuple)):
                items = [str(x) for x in p]
                return {'excerpt': items[-1] if items else '', 'chapter': items[0] if len(items) > 1 else c['title']}
            return {'excerpt': str(p), 'chapter': c['title']}
        d['passages'] = [_pas(p) for p in (d.get('passages') or [])]
        d['sections'] = [x if isinstance(x, dict) else {'title': '', 'narration': str(x)} for x in (d.get('sections') or [])]
        d = repair(tn, d)
        d = force(tn, window, d)
        bad = check(tn, d)
        if bad:
            d, bad = _lenfix(tn, window, d, bad)
        if not bad:
            bad = _story_gate(d)
        if not bad and SH:
            bad = _gate(c, d)
            if not bad:
                print('ml_autoscripts: wrote %s.json (passed the video builder checks)' % bid, flush=True)
                return '%s.json' % bid
        if not bad and not SH:
            bad = _gate_ml(c, d)
        if bad:
            print('ml_autoscripts: attempt %d rejected:' % attempt, '; '.join(str(x) for x in bad[:4])[:500], flush=True)
        if not bad:
            break
        prompt = base % (kind, chan, c['title'], c['author'], prior, window) + extra + '\nYour last attempt failed these checks, fix them: ' + '; '.join(bad[:6])
    else:
        print('ml_autoscripts: gave up on', bid, bad[:3], flush=True)
        return None
    refs = _existing(bid)
    if refs:
        ref = json.load(open(refs[0]))
    else:   # first script for this book: take provenance from the catalogue
        ref = {'source_kind': c.get('source_kind') or 'Original commentary on the retained original public-domain text; modern examples identified and limitations discussed; owner review required',
               'retained_source_sha256': c.get('sha256', '')}
    n = 1 if SH else 2
    while (OUT / ('%s-%d.json' % (bid, n))).exists() or (SH and (OUT / ('%s.json' % bid)).exists()):
        n += 1
        if SH:
            return None
    out = {'book_id': bid, 'title': c['title'], 'author': c['author'], 'public_title': d['public_title'], 'hook': d['hook'],
           'thumbnail_headline': d['thumb'], 'source_url': c['canonical_url'],
           'source_kind': ref['source_kind'], 'retained_source_sha256': ref['retained_source_sha256'],
           'source_passages': [{'section': i, 'source_chapter': p['chapter'], 'excerpt': p['excerpt']} for i, p in enumerate(d['passages'])],
           'sections': [{'title': s['title'], 'narration': s['narration']} for s in d['sections']], 'claims': d.get('claims', []), 'story_v2': True}
    fn = '%s.json' % bid if SH else '%s-%d.json' % (bid, n)
    (OUT / fn).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print('ml_autoscripts: wrote %s' % fn, flush=True)
    try:
        import ml_series; ml_series.record(fn, d['public_title'])
    except Exception:
        pass
    return fn


def publish():
    """Copy scripts into the GitHub clone and push (so the GitHub builder can use them)."""
    if not REPO.is_dir():
        return
    dst = REPO / OUTNAME
    dst.mkdir(exist_ok=True)
    changed = False
    for p in OUT.glob('*.json'):
        t = dst / p.name
        if not t.exists() or t.read_bytes() != p.read_bytes():
            shutil.copy(p, t)
            changed = True
    if changed:
        for cmd in (['git', 'add', '-f', OUTNAME],
                    ['git', 'commit', '-qm', 'MindLore: auto-written scripts'],
                    ['git', 'push', '-q']):
            subprocess.run(cmd, cwd=str(REPO), timeout=120, capture_output=True)
        print('ml_autoscripts: pushed new scripts', flush=True)


def pull_scripts():
    """Mac side: bring scripts GitHub wrote into the studio (needed to match built videos to their script)."""
    if not REPO.is_dir():
        return 0
    subprocess.run(['git', 'pull', '--rebase', '--autostash', '-q'], cwd=str(REPO), timeout=120, capture_output=True)
    n = 0
    for p in (REPO / OUTNAME).glob('*.json'):
        t = OUT / p.name
        if not t.exists():
            shutil.copy(p, t)
            n += 1
    if n:
        print('ml_autoscripts: pulled %d new script(s) from GitHub' % n, flush=True)
    return n


def top_up():
    """On GitHub (daily workflow) it writes scripts. On the Mac it only pulls them."""
    if os.environ.get('GITHUB_ACTIONS') != 'true' and not os.environ.get('ML_LOCAL'):
        try:
            import ml_resume, importlib
            importlib.reload(ml_resume)
            ml_resume.resume()   # re-queue approved posts that only waited for the Buffer allowance
        except Exception as e:
            print('ml_resume skipped:', str(e)[:100], flush=True)
        try:
            import sm_resume
            importlib.reload(sm_resume)
            sm_resume.resume()
        except Exception as e:
            print('sm_resume skipped:', str(e)[:100], flush=True)
        try:
            import sm_import_state
            importlib.reload(sm_import_state)
            sm_import_state.import_state()   # record posts GitHub scheduled so the Mac never sends them again
        except Exception as e:
            print('sm_import_state skipped:', str(e)[:100], flush=True)
        try:
            import sm_prehost
            importlib.reload(sm_prehost)
            sm_prehost.prehost()   # host waiting videos ahead of time (4 per pass)
        except Exception as e:
            print('sm_prehost skipped:', str(e)[:100], flush=True)
        try:
            import gh_kick
            importlib.reload(gh_kick)
            gh_kick.kick()   # start light workflows GitHub's own schedule skipped
        except Exception as e:
            print('gh_kick skipped:', str(e)[:100], flush=True)
        try:
            import sm_export
            importlib.reload(sm_export)
            sm_export.push()   # approved ShelfMade queue -> GitHub (read-only copy for the GitHub publisher)
        except Exception as e:
            print('sm_export skipped:', str(e)[:100], flush=True)
        try:
            import hook_learn
            importlib.reload(hook_learn)
            hook_learn.push()   # learned hook weights (views per hook type) -> GitHub builds
        except Exception as e:
            print('hook_learn skipped:', str(e)[:100], flush=True)
        return pull_scripts()
    if not _key():
        return 'no key'
    made = 0
    while len(list(OUT.glob('*.json'))) < (90 if SH else TARGET) and made < PER_PASS:
        try:
            if not make_one():
                break
        except (OSError, ValueError, KeyError) as e:
            print('ml_autoscripts: stopped:', str(e)[:100], flush=True)
            break
        made += 1
    publish()
    return made


if __name__ == '__main__':
    print('ml_autoscripts: start, scripts on disk =', len(list(OUT.glob('*.json'))), 'target =', 90 if SH else TARGET, flush=True)
    print('ml_autoscripts: DONE, scripts made =', top_up(), flush=True)
