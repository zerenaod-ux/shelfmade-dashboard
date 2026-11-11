"""Lists MindLore full videos (>=2 min) with their YouTube status/schedule. If UNSCHEDULE=1, takes OLD-look scheduled ones OFF the schedule
(they stay private, nothing is deleted, restorable). KEEP = comma list of video ids to leave alone (new look)."""
import json, os, re
import yt_publish as Y
KEEP = set(x for x in os.environ.get('KEEP', '').split(',') if x)
GO = os.environ.get('UNSCHEDULE') == '1'

def sec(s):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s or ''); h, mi, se = [int(x or 0) for x in m.groups()]; return h * 3600 + mi * 60 + se

a = Y.token(); h = {'Authorization': 'Bearer ' + a}
pl = 'UU' + Y.CHANNEL[2:]; ids = []; tok = ''
while len(ids) < 300:
    with Y.http('https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId=%s%s' % (pl, tok), headers=h) as r:
        j = json.load(r)
    ids += [i['contentDetails']['videoId'] for i in j.get('items', [])]
    if not j.get('nextPageToken'): break
    tok = '&pageToken=' + j['nextPageToken']
rows = []
for k in range(0, len(ids), 50):
    with Y.http('https://www.googleapis.com/youtube/v3/videos?part=status,snippet,contentDetails&id=' + ','.join(ids[k:k + 50]), headers=h) as r:
        rows += json.load(r)['items']
for v in sorted(rows, key=lambda v: v['snippet']['publishedAt']):
    d = sec(v['contentDetails']['duration'])
    if d < 120: continue
    st = v['status']; pa = st.get('publishAt')
    print('AUDIT', v['id'], st['privacyStatus'], 'publishAt=%s' % pa, 'pub=%s' % v['snippet']['publishedAt'][:16], v['snippet']['title'][:50], 'KEEP' if v['id'] in KEEP else '')
    if GO and pa and v['id'] not in KEEP:
        body = {'id': v['id'], 'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': st.get('selfDeclaredMadeForKids', False)}}
        with Y.http('https://www.googleapis.com/youtube/v3/videos?part=status', json.dumps(body).encode(), {**h, 'Content-Type': 'application/json'}, 'PUT') as r:
            print('UNSCHEDULED', v['id'], r.status)
