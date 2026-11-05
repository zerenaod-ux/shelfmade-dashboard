"""Trend radar (GitHub, no Mac). Twice a week, per brand: searches YouTube for what is getting views RIGHT NOW in the niche (last 14 days, short videos, by views),
works out views per day, and asks an LLM to turn the winners into rising themes / hook patterns. Output data/trends/<brand>.json, read by learned.guidance()
as 'TRENDING NOW' (inspiration for topic and angle only: never copy titles, scripts or footage). Fail-soft: any problem leaves the previous trend notes in place."""
import datetime, json, os, sys, urllib.request, urllib.parse, urllib.error
from pathlib import Path
OUT = Path('data/trends'); OUT.mkdir(parents=True, exist_ok=True)
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
NOW = datetime.datetime.now(datetime.timezone.utc)
QUERIES = {
    'doodles': ['psychology animation shorts', 'relatable animated skit friends', 'overthinking funny animation', 'funny animated conversation anxious friend'],
    'mindlore': ['psychology facts shorts', 'psychology tricks mind', 'dark psychology facts', 'why your brain does this'],
    'shelfmade': ['stoicism quotes shorts', 'book quotes life lessons', 'classic book wisdom', 'philosophy quotes motivation'],
}
BRIEF = {'doodles': 'funny animated skits of two best friends explaining psychology ideas', 'mindlore': 'psychology shorts and videos built from classic public-domain psychology books',
         'shelfmade': 'shorts and videos built from public-domain classic books (quotes, lessons)'}


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
        return llm.json_call('You are a short-form video trend analyst. Reply with JSON only.', prompt, temperature=0.4)
    except Exception as e:
        print('  free fallback failed:', str(e)[:100])
        return None


def brand(b):
    tok = token(b)
    after = (NOW - datetime.timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')
    ids = {}
    for q in QUERIES[b]:
        r = get('https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode({'part': 'id', 'type': 'video', 'q': q, 'order': 'viewCount', 'videoDuration': 'short',
                                                                                         'publishedAfter': after, 'relevanceLanguage': 'en', 'maxResults': 15}), tok)
        for i in r.get('items', []):
            ids[i['id']['videoId']] = q
    rows = []
    idl = list(ids)
    for i in range(0, len(idl), 50):
        r = get('https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id=' + ','.join(idl[i:i + 50]), tok)
        for v in r.get('items', []):
            age = max((NOW - datetime.datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))).total_seconds() / 86400, 1)
            views = int(v['statistics'].get('viewCount', 0))
            rows.append({'title': v['snippet']['title'][:100], 'channel': v['snippet']['channelTitle'], 'views': views, 'days': round(age, 1), 'vpd': round(views / age)})
    rows.sort(key=lambda r: -r['vpd'])
    top = rows[:14]
    if len(top) < 5:
        return 'only %d results: keep previous notes' % len(top)
    prompt = ('You are a short-form video trend analyst. Our channel makes: %s.\nThese videos in our niche are getting the most views per day in the last 14 days:\n%s\n\n'
              'Find the rising THEMES, emotional angles and hook patterns that are working right now, and turn them into ideas for OUR channel. Inspiration only: never copy a title, script or footage. '
              'Return ONLY JSON: {"hot_themes":[4-6 short phrases],"hook_patterns":[3 short descriptions],"ideas_for_us":[4 concrete episode/topic ideas in our style]}') % (BRIEF[b], json.dumps(top, indent=0))
    j = ask(prompt)
    if not j:
        return 'LLM unavailable: keep previous notes'
    j.update(updated=str(NOW.date()), sample=len(rows), top_vpd=top[0]['vpd'])
    (OUT / (b + '.json')).write_text(json.dumps(j, indent=1))
    return 'trends from %d videos (top %d views/day)' % (len(rows), top[0]['vpd'])


for b in ('mindlore', 'shelfmade', 'doodles'):
    try:
        print(b, '->', brand(b))
    except Exception as e:
        print(b, 'trend radar skipped:', str(e)[:150])
sys.exit(0)
