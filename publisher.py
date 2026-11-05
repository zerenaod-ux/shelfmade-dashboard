"""GitHub publisher for ShelfMade Shorts. DRY-RUN unless PUBLISH_LIVE=1.
Reads publish/queue.json (approved posts exported by the Mac), looks at what Buffer already holds, and gives each free slot to the next post.
Same rules as the Mac studio: slots per platform (posting-slots.json), cap buffer_queue_limit scheduled posts per channel, never double-post
(publish/state.json remembers every post id handed to Buffer)."""
import json, os, sys, datetime, urllib.request, urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo

B = Path(__file__).resolve().parent
BRAND = os.environ.get('PUBLISH_BRAND', 'shelfmade')
SUF = '' if BRAND == 'shelfmade' else '-' + BRAND   # mindlore -> posting-slots-mindlore.json, doodles -> posting-slots-doodles.json
CFG = json.loads((B / ('posting-slots%s.json' % SUF)).read_text())
CHANNELS = {
    'shelfmade': {'youtube': '6acef48c778b240e2f0201d8', 'instagram': '6acef38d778b240e2f01f97b', 'tiktok': '6acef41b778b240e2f01fe44'},
    'mindlore': {'youtube': '6ad2d9d4778b240e2f33343d', 'instagram': '6ad2d979778b240e2f3330c9', 'tiktok': '6ad2da89778b240e2f333abd'},
    'doodles': {'youtube': '6adecc262f1f5ed648d31a5c', 'instagram': '6adecbdb2f1f5ed648d318e9', 'tiktok': '6adecb442f1f5ed648d31611'},
}[BRAND]
LIVE = os.environ.get('PUBLISH_LIVE') == '1'
TOKEN = os.environ.get('BUFFER_TOKEN', '').strip()
STATE = B / 'publish' / ('state%s.json' % SUF)
MAX_CREATES = int(os.environ.get('PUBLISH_MAX', '12'))   # keeps the Buffer allowance safe per run


def api(doc, variables=None):
    req = urllib.request.Request('https://api.buffer.com', json.dumps({'query': doc, 'variables': variables or {}}).encode(),
                                 {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def load(p, d):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return d


def free_slots(platform, taken, now):
    tz = ZoneInfo(CFG.get('timezone', 'America/Chicago'))
    earliest = now.astimezone(tz) + datetime.timedelta(minutes=int(CFG.get('min_lead_minutes', 10)))
    out = []
    for off in range(0, 15):
        day = (now.astimezone(tz) + datetime.timedelta(days=off)).date()
        for t in CFG['slots'].get(platform, []):
            h, m = [int(x) for x in t.split(':')]
            s = datetime.datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            if s >= earliest:
                out.append(s.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'))
    return [s for s in sorted(out) if s not in taken]


def main():
    q = load(B / 'publish' / 'queue.json', {'items': []}) if BRAND == 'shelfmade' else {'items': []}
    q['items'] = list(q.get('items', [])) + list(load(B / 'publish' / ('approved%s.json' % SUF), {'items': []}).get('items', []))
    state = load(STATE, {'done': {}})
    if LIVE and BRAND == 'shelfmade' and load(B / 'publish' / 'queue.json', {}).get('owner') != 'github':
        print('LIVE but the queue was exported while the Mac still sent posts: waiting for a fresh export (prevents double posts).')
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    held = {p: [] for p in CHANNELS}
    if TOKEN:
        orgs = ((api('{account{organizations{id}}}').get('data') or {}).get('account') or {}).get('organizations') or []
        org = orgs[0]['id'] if orgs else ''
        res = api('query($i:PostsInput!){posts(first:100,input:$i){edges{node{channelService dueAt status}}}}',
                  {'i': {'organizationId': org, 'filter': {'channelIds': list(CHANNELS.values()), 'status': ['scheduled', 'sending']}}})
        if res.get('errors') and not res.get('data'):
            print('Buffer read failed:', json.dumps(res)[:300]); sys.exit(1)
        for e in ((res.get('data') or {}).get('posts') or {}).get('edges', []):
            n = e['node']
            if n['channelService'] in held and n.get('dueAt'):
                held[n['channelService']].append(n['dueAt'][:19] + '.000Z')
    else:
        print('No BUFFER_TOKEN: planning without Buffer data (slot list may differ).')
    cap = int(CFG.get('buffer_queue_limit', 9))
    plan, creates = [], 0
    for plat in CHANNELS:
        waiting = [i for i in q['items'] if i['platform'] == plat and i['id'] not in state['done']]
        taken = set(held[plat])
        room = max(0, cap - len(held[plat]))
        for item in waiting[:room]:
            slots = free_slots(plat, taken, now)
            if not slots:
                break
            due = slots[0]
            taken.add(due)
            plan.append((plat, item, due))
    print('%s: Buffer holds %s | queue %d | would schedule %d' % (
        'LIVE' if LIVE else 'DRY-RUN', {k: len(v) for k, v in held.items()}, len(q['items']), len(plan)))
    for plat, item, due in plan:
        print('  ', plat, due, (item['title'] or '')[:50])
        if not LIVE or creates >= MAX_CREATES:
            continue
        meta = {'youtube': {'title': item['title'], 'privacy': 'public', 'madeForKids': False, 'notifySubscribers': True, 'categoryId': '27'},
                'instagram': {'type': 'reel', 'shouldShareToFeed': True}, 'tiktok': {'title': item['title']}}[plat]
        inp = {'channelId': CHANNELS[plat], 'text': item['text'], 'schedulingType': 'automatic', 'mode': 'customScheduled', 'needsApproval': False,
               'saveToDraft': False, 'assets': [{'video': {'url': item['url'], 'metadata': {'thumbnailOffset': 1000}}}], 'metadata': {plat: meta}, 'dueAt': due}
        r = api('mutation($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{id status dueAt}} ... on MutationError{message}}}', {'input': inp})
        cp = ((r.get('data') or {}).get('createPost') or {})
        creates += 1
        if cp.get('post'):
            state['done'][item['id']] = {'remote': cp['post']['id'], 'due': due, 'at': now.isoformat(timespec='seconds')}
            print('    sent', cp['post']['id'])
            STATE.write_text(json.dumps(state, indent=1))   # remember at once: a crash must never cause a double post
        else:
            print('    NOT sent:', json.dumps(r)[:200])
            if 'limit' in json.dumps(r).lower() or 'allowance' in json.dumps(r).lower():
                break
    if LIVE:
        STATE.write_text(json.dumps(state, indent=1))


if __name__ == '__main__':
    main()
