"""Daily playlist keeper (GitHub, no Mac). Per channel keeps two playlists up to date: '<Channel> | Full videos' and '<Channel> | Shorts'.
Idempotent: creates a playlist when missing, adds only videos not in it yet (cap per run keeps the daily YouTube quota safe)."""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
CAP = int(os.environ.get('PLAYLIST_ADDS', '60'))
API = 'https://www.googleapis.com/youtube/v3/'


def call(tok, path, body=None):
    req = urllib.request.Request(API + path, json.dumps(body).encode() if body is not None else None,
                                 {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def pages(tok, path):
    out, tk = [], ''
    while True:
        r = call(tok, path + tk)
        out += r.get('items', [])
        if not r.get('nextPageToken'):
            return out
        tk = '&pageToken=' + r['nextPageToken']


def secs(d):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d)
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def run(b, budget):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': os.environ['YT_REFRESH_TOKEN_' + b.upper()], 'grant_type': 'refresh_token'}).encode()
    tok = json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']
    ch = call(tok, 'channels?part=contentDetails,snippet&mine=true')['items'][0]
    name = ch['snippet']['title']
    ids = [i['contentDetails']['videoId'] for i in pages(tok, 'playlistItems?part=contentDetails&maxResults=50&playlistId=' + ch['contentDetails']['relatedPlaylists']['uploads'])]
    vids = {}
    for i in range(0, len(ids), 50):
        for v in call(tok, 'videos?part=contentDetails&id=' + ','.join(ids[i:i + 50]))['items']:
            vids[v['id']] = 'Shorts' if secs(v['contentDetails']['duration']) <= 180 else 'Full videos'
    have = {p['snippet']['title']: p['id'] for p in pages(tok, 'playlists?part=snippet&mine=true&maxResults=50')}
    added = 0
    for kind in ('Full videos', 'Shorts'):
        title = '%s | %s' % (name, kind)
        want = [v for v in ids if vids.get(v) == kind]
        if not want:
            continue
        if title not in have:
            have[title] = call(tok, 'playlists?part=snippet,status', {'snippet': {'title': title, 'description': '%s: %s' % (name, kind)}, 'status': {'privacyStatus': 'public'}})['id']
            print(b, 'created playlist', title)
        pid = have[title]
        inpl = {i['contentDetails']['videoId'] for i in pages(tok, 'playlistItems?part=contentDetails&maxResults=50&playlistId=' + pid)}
        for v in want:
            if v in inpl or budget <= 0:
                continue
            try:
                call(tok, 'playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': v}}})
                added += 1; budget -= 1
            except urllib.error.HTTPError as e:
                print(b, 'skip', v, e.code)
    print(b, 'added', added, 'videos')
    return budget


bad, budget = [], CAP
for b in ('mindlore', 'shelfmade', 'doodles'):
    try:
        budget = run(b, budget)
    except Exception as e:
        bad.append('%s: %s' % (b, str(e)[:120]))
open('alert.md', 'w').write('\n'.join('- ' + x for x in bad))
if bad:
    print('PROBLEMS', bad); sys.exit(1)
