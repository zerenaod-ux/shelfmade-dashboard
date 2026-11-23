"""One-off (owner 2026-11-22): skip the AnimationDoodles videos booked for Chicago Nov 22 evening and Nov 23 (gh243, gh257, gh258),
and move every later video up into the freed slots (the studio-look videos from Nov 24 take their place). Creates each moved post at its new time FIRST,
then deletes the old one, so nothing is lost. Skipped videos are marked SKIPPED in publish/state-doodles.json so the publisher never re-queues them."""
import json, os, sys, datetime, collections
os.environ.setdefault('PUBLISH_BRAND', 'doodles')
import publisher as P
DRY = os.environ.get('DRY') == '1'
SKIP = ['gh243', 'gh257', 'gh258']
now = datetime.datetime.now(datetime.timezone.utc)
state = P.load(P.STATE, {'done': {}}); items = {i['id']: i for i in P.load(P.B / 'publish' / 'approved-doodles.json', {'items': []})['items']}
groups = collections.defaultdict(dict)
for k, v in state['done'].items():
    if '-dd-' not in k or str(v.get('remote', '')).startswith('SKIPPED') or not v.get('due'): continue
    n, plat = k.split('-dd-'); 
    if datetime.datetime.fromisoformat(v['due'].replace('Z', '+00:00')) > now: groups[n][plat] = (k, v)
order = sorted(groups, key=lambda n: min(x[1]['due'] for x in groups[n].values()))
skip = [n for n in order if n in SKIP]; keep = [n for n in order if n not in SKIP]
print('skip', skip); print('move order', keep)
def usable(n): return all(datetime.datetime.fromisoformat(x[1]['due'].replace('Z', '+00:00')) > now + datetime.timedelta(minutes=14) for x in groups[n].values())
slots = [n for n in order if usable(n)]
plan = []
for vid, slot in zip(keep, slots):
    if vid == slot: continue
    plan.append((vid, slot))
for vid, slot in plan: print('plan', vid, '->', slot, {p: groups[slot][p][1]['due'] for p in groups[slot]})
if DRY: sys.exit(0)
if not P.TOKEN: sys.exit('no BUFFER_TOKEN')
def delete(rid):
    d = P.api('mutation($i:DeletePostInput!){deletePost(input:$i){__typename ... on MutationError{message}}}', {'i': {'id': rid}}); out = json.dumps(d)[:200]
    return not ('MutationError' in out or d.get('errors')), out
def save(): P.STATE.write_text(json.dumps(state, indent=1))
stamp = now.isoformat(timespec='seconds')
for n in skip:
    for plat, (k, v) in groups[n].items():
        ok, out = delete(v['remote'])
        if ok: state['done'][k] = {'remote': 'SKIPPED by owner 2026-11-22', 'due': v['due'], 'at': stamp}; save(); print('skipped', k)
        else: print('skip delete FAILED', k, out)
newdue = {}
for vid, slot in plan:
    for plat, (k, v) in groups[vid].items():
        tgt = groups[slot].get(plat)
        if not tgt: print('no target slot for', k); continue
        due = newdue.get((slot, plat)) or tgt[1]['due']; item = items.get(k)
        if not item: print('skip', k, 'not approved item'); continue
        meta = {'youtube': {'title': item['title'], 'privacy': 'public', 'madeForKids': False, 'notifySubscribers': True, 'categoryId': '27'},
                'instagram': {'type': 'reel', 'shouldShareToFeed': True}, 'tiktok': {'title': item['title']}}[plat]
        inp = {'channelId': P.CHANNELS[plat], 'text': item['text'], 'schedulingType': 'automatic', 'mode': 'customScheduled', 'needsApproval': False, 'saveToDraft': False,
               'assets': [{'video': {'url': item['url'], 'metadata': {'thumbnailOffset': 1000}}}], 'metadata': {plat: meta}, 'dueAt': due}
        r = P.api('mutation($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{id status dueAt}} ... on MutationError{message}}}', {'input': inp})
        cp = ((r.get('data') or {}).get('createPost') or {})
        if not cp.get('post'): print('create FAILED', k, json.dumps(r)[:200]); continue
        ok, out = delete(v['remote'])
        if not ok: print('old delete FAILED (duplicate!)', k, out)
        state['done'][k] = {'remote': cp['post']['id'], 'due': due, 'at': stamp}; save(); print('moved', k, v['due'], '->', due)
