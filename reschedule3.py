"""One-off (owner 2026-11-09): publish the 3 new pipeline videos TOMORROW (Tue Nov 10, Chicago) instead of Tue night/Wed.
Creates each post at its new time FIRST, then deletes the old scheduled one, then updates publish/state-mindlore.json."""
import json, sys, datetime
import publisher as P
if not P.TOKEN: sys.exit('no BUFFER_TOKEN')
NEW = {   # item number -> platform -> due (UTC; Chicago is UTC-6 now)
    'gh138': {'youtube': '2026-11-10T21:00:00.000Z', 'instagram': '2026-11-10T21:00:00.000Z', 'tiktok': '2026-11-10T22:00:00.000Z'},   # 15:00 / 15:00 / 16:00 CT
    'gh139': {'youtube': '2026-11-11T00:00:00.000Z', 'instagram': '2026-11-10T23:30:00.000Z', 'tiktok': '2026-11-11T01:00:00.000Z'},   # 18:00 / 17:30 / 19:00 CT
    'gh140': {'youtube': '2026-11-11T03:00:00.000Z', 'instagram': '2026-11-11T02:00:00.000Z', 'tiktok': '2026-11-11T03:30:00.000Z'},   # 21:00 / 20:00 / 21:30 CT
}
state = P.load(P.STATE, {'done': {}}); items = {i['id']: i for i in P.load(P.B / 'publish' / 'approved-mindlore.json', {'items': []})['items']}
for num, byp in NEW.items():
    for plat, due in byp.items():
        iid = '%s-ml-%s' % (num, plat); item = items.get(iid); old = state['done'].get(iid)
        if not item or not old: print('skip', iid, 'missing'); continue
        if old.get('due') == due: print('already', iid); continue
        meta = {'youtube': {'title': item['title'], 'privacy': 'public', 'madeForKids': False, 'notifySubscribers': True, 'categoryId': '27'}, 'instagram': {'type': 'reel', 'shouldShareToFeed': True}, 'tiktok': {'title': item['title']}}[plat]
        inp = {'channelId': P.CHANNELS[plat], 'text': item['text'], 'schedulingType': 'automatic', 'mode': 'customScheduled', 'needsApproval': False, 'saveToDraft': False,
               'assets': [{'video': {'url': item['url'], 'metadata': {'thumbnailOffset': 1000}}}], 'metadata': {plat: meta}, 'dueAt': due}
        r = P.api('mutation($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{id status dueAt}} ... on MutationError{message}}}', {'input': inp})
        cp = ((r.get('data') or {}).get('createPost') or {})
        if not cp.get('post'): print('create FAILED', iid, json.dumps(r)[:200]); continue
        d = P.api('mutation($i:DeletePostInput!){deletePost(input:$i){__typename ... on MutationError{message}}}', {'i': {'id': old['remote']}}); out = json.dumps(d)[:200]
        if 'MutationError' in out or d.get('errors'): print('old delete FAILED (duplicate!)', iid, out)
        state['done'][iid] = {'remote': cp['post']['id'], 'due': due, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        P.STATE.write_text(json.dumps(state, indent=1)); print('moved', iid, old['due'], '->', due)
