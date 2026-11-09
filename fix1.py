"""One-off: pull the first live-demo video (misleading bar chart) from Buffer and park its approved posts; its fixed re-cut st-261109-live4 goes through the normal pipeline."""
import json, os, sys, datetime
import publisher as P
if not P.TOKEN: sys.exit('no BUFFER_TOKEN')
orgs = ((P.api('{account{organizations{id}}}').get('data') or {}).get('account') or {}).get('organizations') or []
res = P.api('query($i:PostsInput!){posts(first:100,input:$i){edges{node{id channelService dueAt status}}}}', {'i': {'organizationId': orgs[0]['id'], 'filter': {'channelIds': list(P.CHANNELS.values()), 'status': ['scheduled']}}})
edges = ((res.get('data') or {}).get('posts') or {}).get('edges', [])
state = P.load(P.STATE, {'done': {}}); bymeta = {v.get('remote'): k for k, v in state['done'].items()}
NUM = None
for k in state['done']:
    pass
ap = P.B / 'publish' / 'approved-mindlore.json'; cur = json.loads(ap.read_text())
ids = [i['id'] for i in cur['items'] if i['title'] == 'Why a deadline ties your stomach in knots']
print('target ids', ids)
for e in edges:
    n = e['node']; key = bymeta.get(n['id'])
    if key in ids:
        r = P.api('mutation($i:DeletePostInput!){deletePost(input:$i){__typename ... on MutationError{message}}}', {'i': {'id': n['id']}}); out = json.dumps(r)[:200]
        if 'MutationError' in out or r.get('errors'): print('delete FAILED', key, out); continue
        state['done'].pop(key); print('removed', key, n['dueAt'])
P.STATE.write_text(json.dumps(state, indent=1))
pk = P.B / 'publish' / 'approved-mindlore-parked-oldlook.json'; old = P.load(pk, {'items': []})
old['items'] += [i for i in cur['items'] if i['id'] in ids]; pk.write_text(json.dumps(old, indent=1))
cur['items'] = [i for i in cur['items'] if i['id'] not in ids]; ap.write_text(json.dumps(cur, indent=1))
