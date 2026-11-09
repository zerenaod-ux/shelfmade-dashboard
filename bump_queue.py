"""One-off (owner request 2026-11-09): free the next N Buffer slots per MindLore channel so newly approved posts that sit first in publish/approved-mindlore.json go out sooner.
Deletes the N soonest SCHEDULED posts (not ones due within 45 min) and removes them from publish/state-mindlore.json 'done', so the publisher re-queues them later. Nothing is lost."""
import json, os, sys, datetime
import publisher as P
N = int(os.environ.get('BUMP_N', '3'))
if not P.TOKEN: sys.exit('no BUFFER_TOKEN')
now = datetime.datetime.now(datetime.timezone.utc)
orgs = ((P.api('{account{organizations{id}}}').get('data') or {}).get('account') or {}).get('organizations') or []
org = orgs[0]['id']
res = P.api('query($i:PostsInput!){posts(first:100,input:$i){edges{node{id channelService dueAt status}}}}', {'i': {'organizationId': org, 'filter': {'channelIds': list(P.CHANNELS.values()), 'status': ['scheduled']}}})
edges = ((res.get('data') or {}).get('posts') or {}).get('edges', [])
if not edges: sys.exit('could not read Buffer posts: ' + json.dumps(res)[:300])
state = P.load(P.STATE, {'done': {}}); bymeta = {v.get('remote'): k for k, v in state['done'].items()}
log = []
for svc in P.CHANNELS:
    posts = sorted([e['node'] for e in edges if e['node']['channelService'] == svc and e['node'].get('dueAt')], key=lambda n: n['dueAt'])
    posts = [n for n in posts if datetime.datetime.fromisoformat(n['dueAt'].replace('Z', '+00:00')) > now + datetime.timedelta(minutes=45)]
    for n in posts[:N]:
        key = bymeta.get(n['id'])
        if not key: print('skip (not in state, not ours):', n['id']); continue
        r = P.api('mutation($i:DeletePostInput!){deletePost(input:$i){__typename ... on MutationError{message}}}', {'i': {'id': n['id']}})
        out = json.dumps(r)[:200]
        if 'MutationError' in out or r.get('errors'): print('delete FAILED', n['id'], out); continue
        state['done'].pop(key); P.STATE.write_text(json.dumps(state, indent=1)); log.append({'svc': svc, 'id': key, 'was_due': n['dueAt']}); print('freed', svc, key, n['dueAt'])
print('freed', len(log), 'slots')
