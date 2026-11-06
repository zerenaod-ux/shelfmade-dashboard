"""Instagram / TikTok / YouTube view counts from Buffer, collected on GitHub (the laptop is no longer needed).
Writes data/analytics/social-<brand>.json. Read-only: never posts. Uses 2 Buffer requests per brand per run."""
import json, os, sys, time, urllib.request, urllib.error
from pathlib import Path
B = Path(__file__).resolve().parent
OUT = B / 'data' / 'analytics'
CH = {
    'shelfmade': {'youtube': '6acef48c778b240e2f0201d8', 'instagram': '6acef38d778b240e2f01f97b', 'tiktok': '6acef41b778b240e2f01fe44'},
    'mindlore': {'youtube': '6ad2d9d4778b240e2f33343d', 'instagram': '6ad2d979778b240e2f3330c9', 'tiktok': '6ad2da89778b240e2f333abd'},
    'doodles': {'youtube': '6adecc262f1f5ed648d31a5c', 'instagram': '6adecbdb2f1f5ed648d318e9', 'tiktok': '6adecb442f1f5ed648d31611'},
}
Q = ('query($input:PostsInput!){posts(input:$input,first:100){edges{node{id channelId channelService text status externalLink sentAt '
     'metrics{type value unit} metricsUpdatedAt}} pageInfo{hasNextPage}}}')


def api(token, doc, variables=None):
    req = urllib.request.Request('https://api.buffer.com', json.dumps({'query': doc, 'variables': variables or {}}).encode(),
                                 {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    if d.get('errors'):
        raise RuntimeError('; '.join(e.get('message', 'error') for e in d['errors'])[:300])
    return d.get('data', {})


def one(brand, token):
    org = api(token, '{account{organizations{id}}}')['account']['organizations'][0]['id']
    res = api(token, Q, {'input': {'organizationId': org, 'filter': {'channelIds': list(CH[brand].values())}}})['posts']
    posts = []
    for e in res.get('edges') or []:
        p = e['node']
        m = {x['type']: x['value'] for x in p.get('metrics') or []}
        if 'likes' not in m and 'reactions' in m:
            m['likes'] = m['reactions']
        posts.append({'platform': p['channelService'], 'status': p['status'], 'url': p.get('externalLink'), 'sent': p.get('sentAt'),
                      'text': (p.get('text') or '')[:110], 'views': m.get('views'), 'likes': m.get('likes'), 'comments': m.get('comments'),
                      'metrics': sorted(m), 'updated': p.get('metricsUpdatedAt')})
    return {'brand': brand, 'collected': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'more': bool(res.get('pageInfo', {}).get('hasNextPage')), 'posts': posts}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bad = []
    for brand in CH:
        tok = os.environ.get('BUFFER_TOKEN_' + brand.upper(), '').strip()
        if not tok:
            print(brand, 'no token'); bad.append(brand); continue
        try:
            d = one(brand, tok)
            (OUT / ('social-%s.json' % brand)).write_text(json.dumps(d, indent=1))
            sent = [p for p in d['posts'] if p['status'] == 'sent']
            print(brand, 'posts', len(d['posts']), 'sent', len(sent), 'with views', sum(1 for p in sent if p['views'] is not None), 'metric types', sorted({m for p in d['posts'] for m in p['metrics']}))
        except Exception as e:
            print(brand, 'FAILED', str(e)[:200]); bad.append(brand)
    if len(bad) == len(CH):
        sys.exit(1)


if __name__ == '__main__':
    main()
