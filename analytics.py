"""Weekly analytics collector (GitHub, no Mac). For each channel: every uploaded video with views/likes/comments + (when the Analytics API is enabled) average watch time and subscribers gained.
Writes data/analytics/<brand>.json and data/analytics/summary.json (best videos per brand) for the learning + reuse steps."""
import json, os, sys, urllib.request, urllib.parse, urllib.error, datetime
from pathlib import Path

OUT = Path('data/analytics'); OUT.mkdir(parents=True, exist_ok=True)
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
today = datetime.date.today()


def get(url, token, data=None):
    req = urllib.request.Request(url, data, {'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def access(rt):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']


def brand(b):
    rt = os.environ.get('YT_REFRESH_TOKEN_' + b.upper(), '')
    if not rt:
        return 'no token'
    tok = access(rt)
    ch = get('https://www.googleapis.com/youtube/v3/channels?part=contentDetails,statistics,snippet&mine=true', tok)['items'][0]
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    ids, page = [], ''
    while len(ids) < 500:
        r = get('https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId=%s%s' % (up, page), tok)
        ids += [i['contentDetails']['videoId'] for i in r.get('items', [])]
        if not r.get('nextPageToken'):
            break
        page = '&pageToken=' + r['nextPageToken']
    vids = []
    for i in range(0, len(ids), 50):
        r = get('https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails,status&id=' + ','.join(ids[i:i + 50]), tok)
        for v in r.get('items', []):
            st = v.get('statistics', {})
            vids.append({'id': v['id'], 'title': v['snippet']['title'], 'published': v['snippet']['publishedAt'], 'duration': v['contentDetails']['duration'],
                         'privacy': v['status']['privacyStatus'], 'views': int(st.get('viewCount', 0)), 'likes': int(st.get('likeCount', 0)), 'comments': int(st.get('commentCount', 0))})
    extra, note = {}, ''
    try:
        q = urllib.parse.urlencode({'ids': 'channel==MINE', 'startDate': str(today - datetime.timedelta(days=90)), 'endDate': str(today), 'metrics': 'views,averageViewDuration,averageViewPercentage,subscribersGained', 'dimensions': 'video', 'sort': '-views', 'maxResults': 200})
        r = get('https://youtubeanalytics.googleapis.com/v2/reports?' + q, tok)
        for row in r.get('rows', []):
            extra[row[0]] = {'avgSeconds': row[2], 'avgPercent': row[3], 'subsGained': row[4]}
    except urllib.error.HTTPError as e:
        note = 'analytics API unavailable (HTTP %s): enable YouTube Analytics API in the Google Cloud project' % e.code
    for v in vids:
        v.update(extra.get(v['id'], {}))
    vids.sort(key=lambda v: -v['views'])
    doc = {'brand': b, 'channel': ch['snippet']['title'], 'subscribers': ch['statistics'].get('subscriberCount'), 'collected': str(today), 'note': note, 'videos': vids}
    (OUT / (b + '.json')).write_text(json.dumps(doc, indent=1))
    return '%d videos, %s subs%s' % (len(vids), ch['statistics'].get('subscriberCount'), ('; ' + note) if note else '')


bad, summ = [], {}
for b in ('mindlore', 'shelfmade', 'doodles'):
    try:
        print(b, brand(b))
        d = json.loads((OUT / (b + '.json')).read_text())
        summ[b] = [{k: v[k] for k in ('id', 'title', 'views', 'likes', 'avgPercent') if k in v} for v in d['videos'][:5]]
    except Exception as e:
        bad.append('%s: %s' % (b, str(e)[:120]))
(OUT / 'summary.json').write_text(json.dumps({'collected': str(today), 'top': summ}, indent=1))
open('alert.md', 'w').write('\n'.join('- ' + x for x in bad))
if bad:
    print('PROBLEMS', bad); sys.exit(1)
