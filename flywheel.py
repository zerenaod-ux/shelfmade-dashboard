"""VIEWER FLYWHEEL (G3): one view -> many. Keeps ONE public Shorts playlist and ONE full-videos playlist per channel and adds every new public video to the right one,
so YouTube's autoplay keeps people inside the channel. (The Short -> full video pointer comment is first_comment.py.)
Safety: max 6 playlist additions per channel per run, never adds a video twice (data/growth/playlists.json), honours the kill switch, DRY unless FLYWHEEL_LIVE=1 (workflow sets it).
Needs the youtube.force-ssl permission (already authorized for all three channels)."""
import datetime, json, os, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path
F = Path('data/growth/playlists.json')
LIVE = os.environ.get('FLYWHEEL_LIVE') == '1'
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
MAXADD = 6
NAMES = {
    'shelfmade': {'best': ('ShelfMade: the most watched', 'Start here: the videos viewers watch the most.'), 'short': ('ShelfMade Shorts: classic books in a minute', 'Short lessons from classic books. Watch one, keep going.'),
                  'full': ('ShelfMade full lessons', 'Longer explanations of classic books, start to finish.')},
    'mindlore': {'best': ('MindLore: the most watched', 'Start here: the ideas viewers watch the most.'), 'short': ('MindLore Shorts: psychology in a minute', 'Quick ideas about how your mind works, from real research.'),
                 'full': ('MindLore full videos', 'Deeper explanations of how your mind works, from real research.')},
    'doodles': {'best': ('Leo & Mia: fan favorites', 'Start here: the skits viewers watch the most.'), 'short': ('Leo & Mia: all the skits', 'Leo and Mia, two best friends, one psychology idea at a time. Watch them in order.'),
                'full': ('Leo & Mia: full episodes', 'The longer Leo and Mia episodes.')},
}


def kind(v):
    return 'full' if re.search(r'PT(\d+H|([3-9]|\d\d)M)', v.get('duration') or '') else 'short'


def access(rt):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']


def yt(tok, path, body=None):
    req = urllib.request.Request('https://www.googleapis.com/youtube/v3/' + path, json.dumps(body).encode() if body else None, {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))


def plan(videos, state):
    """Pure: -> {'short': [ids to add], 'full': [ids to add]} (public, not yet added, oldest first so the playlist reads in order)."""
    out = {'short': [], 'full': []}
    pub = sorted([v for v in videos if v.get('privacy', 'public') == 'public' and v.get('id') and v.get('published')], key=lambda v: v['published'])
    for v in pub:
        k = kind(v)
        if v['id'] not in (state.get(k, {}).get('added') or []):
            out[k].append(v['id'])
    return out


def main():
    try:
        import guard
    except Exception:
        guard = None
    state = json.loads(F.read_text()) if F.is_file() else {}
    status = {}
    for brand in ('shelfmade', 'mindlore', 'doodles'):
        try:
            if guard and guard.killed(brand):
                status[brand] = 'kill switch on'; continue
            d = json.loads(Path('data/analytics/%s.json' % brand).read_text())
            st = state.setdefault(brand, {})
            todo = plan(d.get('videos', []), st)
            try:   # H6: a 'most watched' playlist from our own scoreboard (top 5 by views/day), the best front door for new viewers
                top = [x['id'] for x in json.loads(Path('data/growth/scoreboard.json').read_text())['brands'][brand].get('top', [])[:5] if x.get('id')]
                todo['best'] = [i for i in top if i not in (st.get('best', {}).get('added') or [])]
            except Exception:
                todo['best'] = []
            rt = os.environ.get('YT_REFRESH_TOKEN_' + brand.upper(), '')
            tok = access(rt) if (LIVE and rt) else None
            n = 0
            for k in ('short', 'full', 'best'):
                ks = st.setdefault(k, {'id': None, 'added': []})
                ids = todo[k][:MAXADD]
                if not ids:
                    continue
                if not LIVE or not tok:
                    print('DRY', brand, k, 'would add', len(ids)); continue
                if not ks['id']:
                    t, ds = NAMES[brand][k]
                    ks['id'] = yt(tok, 'playlists?part=snippet,status', {'snippet': {'title': t, 'description': ds}, 'status': {'privacyStatus': 'public'}})['id']
                    print('created playlist', brand, k, ks['id'])
                for vid in ids:
                    try:
                        yt(tok, 'playlistItems?part=snippet', {'snippet': {'playlistId': ks['id'], 'resourceId': {'kind': 'youtube#video', 'videoId': vid}}})
                        ks['added'].append(vid); n += 1
                    except urllib.error.HTTPError as e:
                        msg = e.read()[:150].decode('utf8', 'ignore')
                        if e.code == 409 or 'duplicate' in msg.lower():
                            ks['added'].append(vid)   # already in the playlist
                        else:
                            status[brand] = 'HTTP %s %s' % (e.code, msg); print(brand, status[brand]); break
            status.setdefault(brand, '%s %d video(s)' % ('added' if LIVE else 'would add', n))
        except Exception as e:
            status[brand] = 'error: %s' % str(e)[:100]; print(brand, status[brand])
    F.parent.mkdir(parents=True, exist_ok=True)
    F.write_text(json.dumps(state, indent=1))
    (F.parent / 'flywheel-status.json').write_text(json.dumps({'at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='minutes'), 'live': LIVE, 'brands': status}, indent=1))
    print(status)


if __name__ == '__main__':
    main()
