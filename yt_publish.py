"""GitHub side: uploads APPROVED MindLore full videos to YouTube (@mindloredaily), scheduled for 18:00 America/Chicago on the next free day.
Reads publish/approved-mlfull.json, remembers uploads in publish/state-mlfull.json (never uploads twice). One upload per run.
Secrets (env): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. DRY-RUN unless PUBLISH_LIVE=1."""
import json, os, re, subprocess, sys, tempfile, zipfile, datetime, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo

B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
KIND = os.environ.get('YT_KIND', 'mlfull')   # mlfull = MindLore, shfull = ShelfMade
CHANNEL = {'mlfull': 'UC0HKWwSPFOSG12--0dtp5Zw', 'shfull': 'UCI4dLh_Uz4HrNq7NOetzbxQ'}.get(KIND) or os.environ.get('YT_CHANNEL_ID', '')   # ddfull = AnimationDoodles: id comes from the repo variable YT_CHANNEL_DOODLES
LIVE = os.environ.get('PUBLISH_LIVE') == '1'
STATE = B / 'publish' / ('state-%s.json' % KIND)
TZ = ZoneInfo('America/Chicago')


def load(p, d):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return d


def http(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data, headers or {}, method=method)
    try:
        return urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        raise RuntimeError('HTTP %s %s' % (e.code, e.read(300).decode('utf-8', 'replace')))


def token():
    body = urllib.parse.urlencode({'client_id': os.environ['YT_CLIENT_ID'], 'client_secret': os.environ['YT_CLIENT_SECRET'],
                                   'refresh_token': os.environ['YT_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode()
    with http('https://oauth2.googleapis.com/token', body, {'Content-Type': 'application/x-www-form-urlencoded'}) as r:
        return json.load(r)['access_token']


def taken_days(access):
    """Days (Chicago) that already hold a scheduled or just-published full upload on the channel."""
    h = {'Authorization': 'Bearer ' + access}
    with http('https://www.googleapis.com/youtube/v3/channels?part=id&mine=true', headers=h) as r:
        ids = [i['id'] for i in json.load(r).get('items', [])]
    if ids != [CHANNEL]:
        raise RuntimeError('Token is not for the expected %s channel: %s' % (KIND, ids))
    pl = 'UU' + CHANNEL[2:]
    with http('https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=25&playlistId=' + pl, headers=h) as r:
        vids = [i['contentDetails']['videoId'] for i in json.load(r).get('items', [])]
    days = set()
    if vids:
        with http('https://www.googleapis.com/youtube/v3/videos?part=status&id=' + ','.join(vids), headers=h) as r:
            for v in json.load(r).get('items', []):
                pa = v.get('status', {}).get('publishAt')
                if pa:
                    days.add(datetime.datetime.fromisoformat(pa.replace('Z', '+00:00')).astimezone(TZ).date())
    return days


def next_slot(taken):
    now = datetime.datetime.now(TZ)
    day = now.date()
    while True:
        slot = datetime.datetime(day.year, day.month, day.day, 18, 0, tzinfo=TZ)
        if day not in taken and slot > now + datetime.timedelta(minutes=30):
            return day, slot.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        day += datetime.timedelta(days=1)


def upload(access, path, title, desc, publish_at):
    size = Path(path).stat().st_size
    meta = {'snippet': {'title': title, 'description': desc, 'categoryId': '27'},
            'status': {'privacyStatus': 'private', 'publishAt': publish_at, 'selfDeclaredMadeForKids': False}}
    with http('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', json.dumps(meta).encode(),
              {'Authorization': 'Bearer ' + access, 'Content-Type': 'application/json', 'X-Upload-Content-Type': 'video/mp4',
               'X-Upload-Content-Length': str(size)}) as r:
        session = r.headers['Location']
    with Path(path).open('rb') as f:
        with http(session, f, {'Authorization': 'Bearer ' + access, 'Content-Type': 'video/mp4', 'Content-Length': str(size)}, 'PUT') as r:
            return json.load(r)


def main():
    items = load(B / 'publish' / ('approved-%s.json' % KIND), {'items': []})['items']
    state = load(STATE, {'done': {}})
    todo = [i for i in items if i['id'] not in state['done']]
    print('%s: approved full videos waiting: %d' % ('LIVE' if LIVE else 'DRY-RUN', len(todo)))
    if not todo or not os.environ.get('YT_REFRESH_TOKEN'):
        if todo:
            print('No YT_REFRESH_TOKEN secret.')
        return
    access = token()
    taken = taken_days(access) | {datetime.date.fromisoformat(v['day']) for v in state['done'].values()}
    item = todo[0]
    day, when = next_slot(taken)
    print('next:', item['title'], '->', when)
    if not LIVE:
        return
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['gh', 'release', 'download', item['tag'], '--repo', REPO, '--pattern', item['zip'], '--dir', tmp], check=True, timeout=900)
        z = Path(tmp) / item['zip']
        with zipfile.ZipFile(z) as f:
            names = [n for n in f.namelist() if not n.startswith('/') and '..' not in Path(n).parts]
            f.extractall(tmp, members=names)
        vid = (sorted(Path(tmp).glob('*_LONGFORM.mp4')) or sorted(Path(tmp).glob('final.mp4')))[0]
        res = upload(access, vid, item['title'], item['description'], when)
        state['done'][item['id']] = {'video': res.get('id'), 'at': when, 'day': day.isoformat()}
        STATE.write_text(json.dumps(state, indent=1))     # remember at once: never upload twice
        print('uploaded', res.get('id'), 'scheduled', when)
        thumb = next(iter(sorted(Path(tmp).glob('*.jpg')) + sorted(Path(tmp).glob('thumbnail.png'))), None)
        if thumb and thumb.stat().st_size <= 2 * 1024 * 1024:
            try:
                http('https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=%s&uploadType=media' % res['id'], thumb.read_bytes(),
                     {'Authorization': 'Bearer ' + access, 'Content-Type': 'image/png' if thumb.suffix == '.png' else 'image/jpeg'}).close()
                print('thumbnail set')
            except Exception as e:
                print('thumbnail skipped:', str(e)[:120])


if __name__ == '__main__':
    main()
