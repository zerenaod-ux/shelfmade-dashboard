"""First comment on new public Shorts (GitHub, no laptop). Daily: for each channel, every public Short from the last 7 days that has no channel comment yet gets ONE comment from the channel
pointing to the channel's newest public FULL video. YouTube's API cannot pin comments: pinning (one tap in Studio) stays optional and manual.
Safety: max 3 comments per channel per run, never twice on the same video, never on a full video, no comment at all when there is no full video to point to.
Dry run unless FIRST_COMMENT_LIVE=1. Needs the youtube.force-ssl permission (all three channels re-authorized 2026-11-06)."""
import datetime, hashlib, json, os, re, urllib.error, urllib.parse, urllib.request
from pathlib import Path

NOW = datetime.datetime.now(datetime.timezone.utc)
DONE_F, STATUS_F = Path('data/replies/commented.json'), Path('data/replies/first-comment-status.json')
LIVE = os.environ.get('FIRST_COMMENT_LIVE') == '1'
MAX_PER_RUN, MAX_AGE_DAYS, MIN_AGE_H = 5, 14, 1
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
TEMPLATES = {
    'shelfmade': ['Want the whole lesson? Watch the full video here: {u}', 'There is a longer version of this idea. Full video: {u}', 'Liked this one? The full video goes deeper: {u}'],
    'mindlore': ['Want the full explanation? Watch the full video: {u}', 'There is a longer, deeper version of this. Full video: {u}', 'If this made you curious, the full video goes further: {u}'],
    'doodles': ['Want more of Leo and Mia? Watch the full episode: {u}', 'The full episode has even more chaos. Watch it here: {u}', 'Liked this skit? The full episode is here: {u}'],
}
FULL_TEMPLATES = {
    'shelfmade': ['Did this book idea make you think? Tell us in the comments which part hit home.', 'Found this interesting? Comment which line you would remember, and what book should we do next?'],
    'mindlore': ['Did this change how you see your own mind? Tell us in the comments which part surprised you.', 'Found this interesting? Comment your own example, and what should we explain next?'],
    'doodles': ['Did this feel like your life? Tell us in the comments who you are, Leo or Mia.', 'Found this funny? Comment the argument you have had the most, and we may turn it into an episode.'],
}
ASK = {'shelfmade': ' Which line stayed with you? Tell us below.', 'mindlore': ' Found it interesting? Tell us in the comments what surprised you.', 'doodles': ' Which one are you, Leo or Mia? Tell us below.'}


def is_full(dur):
    return bool(re.search(r'PT(\d+H|([3-9]|\d\d)M)', dur or ''))


def when(v):
    return datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00'))


def plan(brand, videos, done):
    """-> (link, [video dicts to comment on]). Pure function, no network."""
    pub = [v for v in videos if v.get('privacy', 'public') == 'public' and v.get('id') and v.get('published')]
    fulls = sorted([v for v in pub if is_full(v.get('duration'))], key=when, reverse=True)
    link = ('https://youtu.be/' + fulls[0]['id']) if fulls else None
    out = []
    for v in sorted(pub, key=when, reverse=True):
        age = NOW - when(v)
        if v['id'] in done or age > datetime.timedelta(days=MAX_AGE_DAYS) or age < datetime.timedelta(hours=MIN_AGE_H):
            continue
        if not is_full(v.get('duration')) and not link:
            continue   # a Short needs a full video to point to
        out.append(v)
    return link, out[:MAX_PER_RUN]


def text(brand, vid, link, full=False):
    h = int(hashlib.md5(vid.encode()).hexdigest(), 16)
    if full:
        t = FULL_TEMPLATES[brand]; return t[h % len(t)]
    t = TEMPLATES[brand]
    return t[h % len(t)].format(u=link) + ASK[brand]


def access(rt):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']


def post(tok, vid, msg):
    body = json.dumps({'snippet': {'videoId': vid, 'topLevelComment': {'snippet': {'textOriginal': msg}}}}).encode()
    req = urllib.request.Request('https://www.googleapis.com/youtube/v3/commentThreads?part=snippet', body,
                                 {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))


def main():
    done = json.loads(DONE_F.read_text()) if DONE_F.is_file() else {}
    status = {'when': NOW.isoformat()[:16], 'live': LIVE, 'brands': {}}
    for brand in ('shelfmade', 'mindlore', 'doodles'):
        try:
            d = json.loads(Path('data/analytics/%s.json' % brand).read_text())
            link, todo = plan(brand, d.get('videos', []), done.get(brand, {}))
            rt = os.environ.get('YT_REFRESH_TOKEN_' + brand.upper(), '')
            n = 0
            for v in todo:
                msg = text(brand, v['id'], link, is_full(v.get('duration')))
                if not LIVE:
                    print('DRY', brand, v['id'], v.get('title', '')[:40], '->', msg); n += 1; continue
                if not rt:
                    status['brands'][brand] = 'no token'; break
                try:
                    post(access(rt), v['id'], msg)
                    done.setdefault(brand, {})[v['id']] = NOW.isoformat()[:16]; n += 1; print('POSTED', brand, v['id'])
                except urllib.error.HTTPError as e:
                    status['brands'][brand] = 'HTTP %s %s' % (e.code, e.read()[:120].decode('utf8', 'ignore')); print(brand, status['brands'][brand]); break
            status['brands'].setdefault(brand, '%s %d comment(s)' % ('would post' if not LIVE else 'posted', n))
        except Exception as e:
            status['brands'][brand] = 'error: %s' % str(e)[:100]; print(brand, status['brands'][brand])
    DONE_F.parent.mkdir(parents=True, exist_ok=True)
    DONE_F.write_text(json.dumps(done, indent=1)); STATUS_F.write_text(json.dumps(status, indent=1))


if __name__ == '__main__':
    main()
