"""One-off (owner request 2026-11-09): from the 3 live-demo videos onward, MindLore posts only NEW-look videos.
Deletes every scheduled MindLore Buffer post that is not one of the 3 live-demo posts (ids gh131/132/133), and PARKS the old-look approved posts
(waiting + deleted) in publish/approved-mindlore-parked-oldlook.json (nothing is lost; to restore, move the items back into approved-mindlore.json)."""
import json, os, sys, datetime
import publisher as P
LIVE = ('gh131', 'gh132', 'gh133')
if not P.TOKEN: sys.exit('no BUFFER_TOKEN')
now = datetime.datetime.now(datetime.timezone.utc)
orgs = ((P.api('{account{organizations{id}}}').get('data') or {}).get('account') or {}).get('organizations') or []
res = P.api('query($i:PostsInput!){posts(first:100,input:$i){edges{node{id channelService dueAt status}}}}', {'i': {'organizationId': orgs[0]['id'], 'filter': {'channelIds': list(P.CHANNELS.values()), 'status': ['scheduled']}}})
edges = ((res.get('data') or {}).get('posts') or {}).get('edges', [])
if not edges: sys.exit('could not read Buffer posts: ' + json.dumps(res)[:300])
state = P.load(P.STATE, {'done': {}}); bymeta = {v.get('remote'): k for k, v in state['done'].items()}
deleted = set(); kept = 0
for e in edges:
    n = e['node']; key = bymeta.get(n['id'])
    if not key or key.split('-')[0] in LIVE: kept += 1; continue
    if not n.get('dueAt') or datetime.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')) <= now + datetime.timedelta(minutes=45): kept += 1; continue
    r = P.api('mutation($i:DeletePostInput!){deletePost(input:$i){__typename ... on MutationError{message}}}', {'i': {'id': n['id']}})
    out = json.dumps(r)[:200]
    if 'MutationError' in out or r.get('errors'): print('delete FAILED', n['id'], out); continue
    deleted.add(key); state['done'].pop(key); print('removed', key, n['dueAt'])
P.STATE.write_text(json.dumps(state, indent=1))
ap = P.B / 'publish' / 'approved-mindlore.json'; cur = json.loads(ap.read_text())
keep, parked = [], []
for i in cur['items']:
    live = i['id'].split('-')[0] in LIVE
    (keep if (live or i['id'] in state['done']) else parked).append(i)
pk = P.B / 'publish' / 'approved-mindlore-parked-oldlook.json'; old = P.load(pk, {'items': []})
old['items'] = old['items'] + parked; old['note'] = 'Parked 2026-11-09 by owner request (new live-demo look only). To restore: move items back into approved-mindlore.json.'
pk.write_text(json.dumps(old, indent=1)); cur['items'] = keep; ap.write_text(json.dumps(cur, indent=1))
print('deleted from Buffer:', len(deleted), '| kept scheduled:', kept, '| parked approved posts:', len(parked), '| approved list now:', len(keep))
