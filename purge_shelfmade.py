"""One-off (owner request 2026-11-23): ShelfMade posts the new whiteboard videos FIRST. Every other scheduled Buffer post is removed and
every other waiting post is PARKED (restorable) in publish/approved-parked-oldstories.json. Nothing is lost.
To restore: move items from the parked file back into publish/approved.json."""
import json, sys, datetime
import publisher as P
KEEP = ('gh360', 'gh361')   # the two whiteboard Shorts built 2026-11-23
if not P.TOKEN: sys.exit('no BUFFER_TOKEN')
now = datetime.datetime.now(datetime.timezone.utc)
orgs = ((P.api('{account{organizations{id}}}').get('data') or {}).get('account') or {}).get('organizations') or []
res = P.api('query($i:PostsInput!){posts(first:100,input:$i){edges{node{id channelService dueAt status}}}}',
            {'i': {'organizationId': orgs[0]['id'], 'filter': {'channelIds': list(P.CHANNELS.values()), 'status': ['scheduled']}}})
edges = ((res.get('data') or {}).get('posts') or {}).get('edges', [])
state = P.load(P.STATE, {'done': {}}); bymeta = {v.get('remote'): k for k, v in state['done'].items()}
deleted = 0; kept = 0
for e in edges:
    n = e['node']; key = bymeta.get(n['id'])
    if key and key.split('-')[0] in KEEP: kept += 1; continue
    if n.get('dueAt') and datetime.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')) <= now + datetime.timedelta(minutes=30): kept += 1; continue
    r = P.api('mutation($i:DeletePostInput!){deletePost(input:$i){__typename ... on MutationError{message}}}', {'i': {'id': n['id']}})
    out = json.dumps(r)[:200]
    if 'MutationError' in out or r.get('errors'): print('delete FAILED', n['id'], out); continue
    deleted += 1; print('removed', key, n['dueAt'])
    if key: state['done'].pop(key)
P.STATE.write_text(json.dumps(state, indent=1))
parked, keep = [], []
ap = P.B / 'publish' / 'approved.json'; cur = json.loads(ap.read_text())
qp = P.B / 'publish' / 'queue.json'; q = json.loads(qp.read_text())
for src in (cur, q):
    for i in src['items']:
        if i['id'] in state['done'] and src is cur: keep.append(i)           # already handed to Buffer & still scheduled
        elif i['id'].split('-')[0] in KEEP and src is cur: keep.append(i)
        elif i['id'] in state['done']: continue
        else: parked.append(i)
cur['items'] = sorted(keep, key=lambda i: (i['id'].split('-')[0] not in KEEP,))   # whiteboard Shorts first
q['items'] = []
ap.write_text(json.dumps(cur, indent=1)); qp.write_text(json.dumps(q, indent=1))
pk = P.B / 'publish' / 'approved-parked-oldstories.json'; old = P.load(pk, {'items': []})
seen = {i['id'] for i in old['items']}
old['items'] += [i for i in parked if i['id'] not in seen]
old['note'] = 'Parked 2026-11-23 by owner request (whiteboard videos first). To restore: move items back into approved.json.'
pk.write_text(json.dumps(old, indent=1))
print('deleted from Buffer:', deleted, '| kept:', kept, '| parked:', len(parked), '| approved list now:', len(cur['items']))
