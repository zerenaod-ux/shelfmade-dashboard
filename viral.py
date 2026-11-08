"""VIRAL DNA (weekly, GitHub, no Mac). Per brand: finds the biggest hits of the last 12 months in our niche (Shorts + long, mixed channel sizes),
reads their top comments, asks an LLM what PATTERNS made them work, and counts how common simple features are among hits.
Output: data/viral/<brand>-library.json (the hits, no usernames) and data/viral/<brand>.json (patterns + shares + comment themes).
Read by learned.guidance() as LOW-WEIGHT 'from other channels, unproven' hints. Inspiration only: patterns, never titles/scripts/footage/characters.
Quota: <=3 search.list (100 units each) + ~40 cheap calls per brand per week. Fail-soft: any problem keeps last week's files."""
import datetime, json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path
OUT = Path('data/viral')
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
NOW = datetime.datetime.now(datetime.timezone.utc)
QUERIES = {   # (query, duration filter) -> 2 Shorts searches + 1 long-form search per brand
    'doodles': [('psychology animation skit', 'short'), ('relatable animated overthinking', 'short'), ('two friends animated psychology', 'short')],
    'mindlore': [('psychology facts', 'short'), ('why your brain does this', 'short'), ('psychology explained classic books', 'medium')],
    'shelfmade': [('stoicism quotes life lessons', 'short'), ('classic book wisdom', 'short'), ('classic books explained summary', 'medium')],
}
BRIEF = {'doodles': 'funny animated skits of two best friends (Leo and Mia) explaining psychology ideas',
         'mindlore': 'psychology Shorts and videos built from classic public-domain psychology books',
         'shelfmade': 'Shorts and videos built from public-domain classic books (quotes, lessons, summaries)'}
NOCOPY = {'doodles': 'Never use another channel\'s characters, catchphrases, art style tricks that identify them, or music. Our cast is only Leo and Mia.',
          'mindlore': 'Never present medical claims, diagnoses or miracle outcomes; no shock-bait about injuries; psychology ideas must stay grounded in our public-domain classic sources.',
          'shelfmade': 'Never quote copyrighted books or other creators\' compilations; only public-domain classics; no fake "stop doing X after 60" medical or financial promises.'}
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')

def get(url, tok):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok}), timeout=60))
def token(b):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': os.environ['YT_REFRESH_TOKEN_' + b.upper()], 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']
def ask(prompt):
    try:
        import ml_autoscripts as M
        r = M._call(prompt)
        if r: return r
    except Exception as e: print('  Gemini failed:', str(e)[:100])
    try:
        import llm
        return llm.json_call('You are a short-form video analyst. Reply with JSON only.', prompt, temperature=0.4)
    except Exception as e: print('  free fallback failed:', str(e)[:100]); return None
def secs(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else 0
def feats(r):
    t = r['title']; d = r['secs']
    return {'question title': t.strip().endswith('?') or bool(re.match(r'(why|how|what|do|does|is|are|can|did|who)\b', t.lower())),
            'speaks to "you"': bool(re.search(r"\b(you|your|you're)\b", t.lower())), 'number in title': bool(re.search(r'\d', t)), 'has emoji': bool(EMOJI.search(t)),
            'ALL-CAPS word': bool(re.search(r'\b[A-Z]{4,}\b', t)), 'title <= 6 words': len(t.split()) <= 6,
            'video <= 30s': d <= 30, 'video 30-60s': 30 < d <= 60, 'video > 60s': d > 60}
def brand(b):
    tok = token(b); ids = {}
    after = (NOW - datetime.timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
    for q, dur in QUERIES[b]:
        r = get('https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode({'part': 'id', 'type': 'video', 'q': q, 'order': 'viewCount', 'videoDuration': dur,
                                                                                         'publishedAfter': after, 'relevanceLanguage': 'en', 'maxResults': 25}), tok)
        for i in r.get('items', []): ids.setdefault(i['id']['videoId'], dur)
    rows, idl = [], list(ids)
    for i in range(0, len(idl), 50):
        r = get('https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id=' + ','.join(idl[i:i + 50]), tok)
        for v in r.get('items', []):
            s = v['statistics']; views = int(s.get('viewCount', 0)); age = max((NOW - datetime.datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))).days, 1)
            rows.append({'id': v['id'], 'title': v['snippet']['title'][:100], 'channelId': v['snippet']['channelId'], 'views': views, 'likes': int(s.get('likeCount', 0)),
                         'comments': int(s.get('commentCount', 0)), 'secs': secs(v['contentDetails'].get('duration')), 'age_days': age, 'vpd': round(views / age, 1)})
    cids = list({r['channelId'] for r in rows}); subs = {}
    for i in range(0, len(cids), 50):
        for c in get('https://www.googleapis.com/youtube/v3/channels?part=statistics&id=' + ','.join(cids[i:i + 50]), tok).get('items', []):
            st = c['statistics']; subs[c['id']] = None if st.get('hiddenSubscriberCount') else int(st.get('subscriberCount', 0))
    for r in rows:
        r['subs'] = subs.get(r['channelId']); r['like_rate'] = round(r['likes'] / max(r['views'], 1), 4); r['comment_rate'] = round(r['comments'] / max(r['views'], 1), 5)
        r['breakout'] = round(r['views'] / max(r['subs'], 200), 1) if r['subs'] is not None else None
    rows = sorted([r for r in rows if r['views'] >= 5000], key=lambda r: -r['views'])[:30]
    if len(rows) < 10: return 'only %d hits: keeping last week\'s files' % len(rows)
    for r in rows[:12]:   # comments = why people reacted (1 unit each; comments off -> skip)
        try:
            c = get('https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&order=relevance&maxResults=15&textFormat=plainText&videoId=' + r['id'], tok)
            r['top_comments'] = [x['snippet']['topLevelComment']['snippet']['textDisplay'][:160] for x in c.get('items', [])][:8]
        except Exception: r['top_comments'] = []
    shares = {}
    for r in rows:
        for k, v in feats(r).items(): shares[k] = shares.get(k, 0) + (1 if v else 0)
    shares = {k: round(100 * v / len(rows)) for k, v in shares.items()}
    slim = [{'title': r['title'], 'views': r['views'], 'secs': r['secs'], 'subs': r['subs'], 'breakout': r['breakout'], 'like_rate': r['like_rate'], 'comment_rate': r['comment_rate'],
             'comments': (r.get('top_comments') or [])[:5]} for r in rows[:14]]
    prompt = ('You are a short-form video analyst. Our channel makes: %s.\nThese are among the BIGGEST hits of the last 12 months in our niche, with stats and what viewers said in comments:\n%s\n\n'
              'Share of hits with simple features (percent): %s\n\n'
              'Find the PATTERNS that made these work (hook type, title formula, what the first 3 seconds promise, emotion, payoff, length) and what viewers loved or asked for in the comments. '
              'Inspiration only: describe patterns in your own words; never repeat a title, script, footage or character. OUR RULES FOR THIS CHANNEL: ' + NOCOPY[b] + ' '
              'Return ONLY JSON: {"patterns":[5 short pattern descriptions],"title_formulas":[3 short fill-in-the-blank formulas],"opening_3s":[3 short ideas],"comment_themes":[4 short items: what viewers loved/asked for],'
              '"avoid":[3 short items],"try_next":[3 concrete ideas in our style]}') % (BRIEF[b], json.dumps(slim, indent=0)[:14000], json.dumps(shares))
    j = ask(prompt)
    if not isinstance(j, dict) or not j.get('patterns'): return 'LLM unavailable: keeping last week\'s files'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / (b + '-library.json')).write_text(json.dumps({'updated': str(NOW.date()), 'hits': [{k: v for k, v in r.items() if k not in ('channelId',)} for r in rows]}, indent=1))
    j.update(updated=str(NOW.date()), n_hits=len(rows), shares=shares, median_hit_views=sorted(r['views'] for r in rows)[len(rows) // 2])
    (OUT / (b + '.json')).write_text(json.dumps(j, indent=1))
    return '%d hits, patterns saved, top shares %s' % (len(rows), sorted(shares.items(), key=lambda x: -x[1])[:3])

FEATURE_MAP = {'has emoji': ('emoji', 'has emoji'), 'question title': ('question title', 'question title'), 'speaks to "you"': ('speaks to "you"', 'title says you/your'),
               'number in title': ('number in title', 'has a number'), 'title <= 6 words': ('title length', 'short title (1-5 words)'), 'video <= 30s': ('short length', 'up to 30s')}

def proof(b):
    """V4 PROOF LOOP: compare how common a feature is among big hits with how it does on OUR videos (growth scoreboard lifts).
    confirmed = hits use it (>=50%) AND our lift >= 1.6; contradicted = hits use it (>=50%) but our lift <= 0.6 (our audience punishes it); our_edge = we win with it though hits rarely use it (<35%)."""
    try:
        shares = json.loads((OUT / (b + '.json')).read_text()).get('shares', {})
        lifts = {(x['feature'], x['value']): x for x in json.loads(Path('data/growth/scoreboard.json').read_text())['brands'][b].get('feature_lifts', [])}
    except Exception:
        return []
    out = []
    for name, key in FEATURE_MAP.items():
        sh, mine = shares.get(name), lifts.get(key)
        if sh is None or not mine or mine.get('n', 0) < 5: out.append({'feature': name, 'hits_pct': sh, 'verdict': 'untested'}); continue
        v = 'confirmed' if sh >= 50 and mine['lift'] >= 1.6 else 'contradicted' if sh >= 50 and mine['lift'] <= 0.6 else 'our_edge' if sh < 35 and mine['lift'] >= 1.6 else 'mixed'
        out.append({'feature': name, 'hits_pct': sh, 'our_lift': mine['lift'], 'our_n': mine['n'], 'verdict': v})
    return out

def guidance(b):
    """LOW-WEIGHT hints for writers. Labelled unproven until our own results confirm (see roadmap V4)."""
    try: j = json.loads((OUT / (b + '.json')).read_text())
    except Exception: return ''
    pats = [str(x)[:140] for x in (j.get('patterns') or [])[:3]]; forms = [str(x)[:110] for x in (j.get('title_formulas') or [])[:2]]; avoid = [str(x)[:100] for x in (j.get('avoid') or [])[:2]]
    if not pats: return ''
    pr = proof(b); conf = [x['feature'] for x in pr if x['verdict'] == 'confirmed']; bad = [x['feature'] for x in pr if x['verdict'] == 'contradicted']
    extra = ((' CONFIRMED on our own channel too: ' + ', '.join(conf) + '.') if conf else '') + ((' DO NOT copy (big hits do it but OUR audience punishes it): ' + ', '.join(bad) + '.') if bad else '')
    return ('\nFROM OTHER CHANNELS (big hits in our niche, UNPROVEN for us, low weight: take ONE idea at most, never copy words): patterns: ' + ' | '.join(pats) +
            ('. title shapes: ' + ' | '.join(forms) if forms else '') + ('. avoid: ' + ' | '.join(avoid) if avoid else '') + extra + '\n')

if __name__ == '__main__':
    for b in ('mindlore', 'shelfmade', 'doodles'):
        try: print(b, '->', brand(b), flush=True)
        except Exception as e: print(b, 'viral skipped:', str(e)[:200], flush=True)
    sys.exit(0)
