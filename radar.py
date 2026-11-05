"""DAILY VIRAL RADAR (GitHub, no Mac). Every day, per brand: finds videos in our niche that are growing unusually FAST in the last 48 hours (views per hour) and
videos from SMALL channels that broke out (views vs subscribers: the most copyable signal, new channels are the ones exploding), asks an LLM WHY each works
(hook, topic, emotion, format) and writes a same-day brief. Output data/radar/<brand>.json (+ rolling history) is injected into every writer by learned.trending().
Inspiration only: never copy titles, scripts, footage or characters. Fail-soft: any problem keeps yesterday's brief."""
import datetime, json, os, sys, urllib.request, urllib.parse
from pathlib import Path
OUT = Path('data/radar'); OUT.mkdir(parents=True, exist_ok=True)
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
NOW = datetime.datetime.now(datetime.timezone.utc)
QUERIES = {
    'doodles': ['psychology animation', 'relatable animated skit', 'funny animation overthinking'],
    'mindlore': ['psychology facts', 'dark psychology', 'why your brain does this'],
    'shelfmade': ['stoicism quotes', 'book quotes life lessons', 'classic book wisdom'],
}
BRIEF = {'doodles': 'funny animated skits of two best friends (Leo and Mia) explaining psychology ideas',
         'mindlore': 'psychology Shorts and videos built from classic public-domain psychology books',
         'shelfmade': 'Shorts and videos built from public-domain classic books (quotes, lessons, summaries)'}
def get(url, tok):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok}), timeout=60))
def token(b):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': os.environ['YT_REFRESH_TOKEN_' + b.upper()], 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']
def ask(prompt):
    try:
        import ml_autoscripts as M
        return M._call(prompt)
    except Exception as e:
        print('  Gemini failed:', str(e)[:100])
    try:
        import llm
        return llm.json_call('You are a short-form video trend analyst. Reply with JSON only.', prompt, temperature=0.5)
    except Exception as e:
        print('  free fallback failed:', str(e)[:100])
        return None
def brand(b):
    tok = token(b); ids = {}
    for hours in (48, 96):   # widen only if the last 48 hours are thin
        after = (NOW - datetime.timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
        for q in QUERIES[b]:
            r = get('https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode({'part': 'id', 'type': 'video', 'q': q, 'order': 'viewCount', 'videoDuration': 'short',
                                                                                             'publishedAfter': after, 'relevanceLanguage': 'en', 'maxResults': 25}), tok)
            for i in r.get('items', []): ids.setdefault(i['id']['videoId'], hours)
        if len(ids) >= 25: break
    rows, idl = [], list(ids)
    for i in range(0, len(idl), 50):
        r = get('https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id=' + ','.join(idl[i:i + 50]), tok)
        for v in r.get('items', []):
            age_h = max((NOW - datetime.datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))).total_seconds() / 3600, 3)
            views = int(v['statistics'].get('viewCount', 0))
            rows.append({'id': v['id'], 'title': v['snippet']['title'][:100], 'channelId': v['snippet']['channelId'], 'channel': v['snippet']['channelTitle'], 'views': views,
                         'hours': round(age_h), 'vph': round(views / age_h, 1), 'likes': int(v['statistics'].get('likeCount', 0))})
    cids = list({r['channelId'] for r in rows}); subs = {}
    for i in range(0, len(cids), 50):
        r = get('https://www.googleapis.com/youtube/v3/channels?part=statistics&id=' + ','.join(cids[i:i + 50]), tok)
        for c in r.get('items', []):
            s = c['statistics']; subs[c['id']] = None if s.get('hiddenSubscriberCount') else int(s.get('subscriberCount', 0))
    for r in rows:
        s = subs.get(r['channelId']); r['subs'] = s
        r['breakout'] = round(r['views'] / max(s, 200), 1) if s is not None else None
    if len(rows) < 6: return 'only %d results: keeping yesterday\'s brief' % len(rows)
    fast = sorted(rows, key=lambda r: -r['vph'])[:8]
    small = sorted([r for r in rows if r['breakout'] and r['subs'] is not None and r['subs'] < 30000 and r['views'] >= 1000], key=lambda r: -r['breakout'])[:6]
    seen, spikes = set(), []
    for r in fast + small:
        if r['id'] not in seen: seen.add(r['id']); spikes.append(r)
    slim = [{k: r[k] for k in ('title', 'channel', 'views', 'hours', 'vph', 'subs', 'breakout')} for r in spikes]
    prompt = ('You are a short-form video trend analyst. Our channel makes: %s.\nThese niche videos are spiking in the LAST 48 HOURS (vph = views per hour; breakout = views divided by the channel\'s subscribers, '
              'a high breakout on a small channel means the IDEA won, not the channel):\n%s\n\n'
              'For the 4 most useful spikes explain WHY it works (hook, topic, emotion, pacing, format). Then write TODAY\'S BRIEF for OUR channel: one angle to try today and 3 concrete ideas in our style, '
              'plus 2 things to avoid (saturated or tired). Inspiration only: never copy a title, script, footage or character.\n'
              'Return ONLY JSON: {"why":[{"title":"...","why":"one sentence"}],"hook_patterns":[3 short descriptions],"todays_angle":"one sentence","ideas":[3 concrete ideas],"avoid":[2 short items]}') % (BRIEF[b], json.dumps(slim, indent=0))
    j = ask(prompt)
    if not j: return 'LLM unavailable: keeping yesterday\'s brief'
    j.update(updated=str(NOW.date()), sample=len(rows), spikes=slim[:10])
    (OUT / (b + '.json')).write_text(json.dumps(j, indent=1))
    hp = OUT / (b + '-history.json')
    try: h = json.loads(hp.read_text())
    except Exception: h = []
    h = [x for x in h if x.get('date') != str(NOW.date())][-29:] + [{'date': str(NOW.date()), 'angle': j.get('todays_angle'), 'top': [{'t': s['title'], 'vph': s['vph']} for s in slim[:5]]}]
    hp.write_text(json.dumps(h, indent=1))
    return 'brief from %d videos; fastest %s vph; %d small-channel breakouts' % (len(rows), fast[0]['vph'], len(small))
for b in ('mindlore', 'shelfmade', 'doodles'):
    try: print(b, '->', brand(b))
    except Exception as e: print(b, 'radar skipped:', str(e)[:200])
sys.exit(0)
