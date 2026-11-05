"""Weekly token check (GitHub, no Mac). Tests each stored key with one cheap request and writes alert.md + exits 1 when any is dead."""
import json, os, sys, urllib.request, urllib.parse, urllib.error

bad, ok = [], []

def call(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data, headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:
        return 0, str(e).encode()

def check(name, status, body, good=(200,)):
    if status in good:
        ok.append(name)
    elif status == 0 or status >= 500 or status == 429:
        ok.append('%s (service busy, retry next week)' % name)
    else:
        bad.append('%s: HTTP %s %s' % (name, status, body.decode('utf8', 'ignore')[:100].replace('\n', ' ')))

cid, sec = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
for who in ('MINDLORE', 'SHELFMADE', 'DOODLES'):
    rt = os.environ.get('YT_REFRESH_TOKEN_' + who, '')
    if not rt:
        bad.append('YouTube %s: secret missing' % who); continue
    d = urllib.parse.urlencode({'client_id': cid, 'client_secret': sec, 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    s, b = call('https://oauth2.googleapis.com/token', d)
    check('YouTube ' + who, s, b)
for who in ('MINDLORE', 'SHELFMADE', 'DOODLES'):
    t = os.environ.get('BUFFER_TOKEN_' + who, '').strip()
    if not t:
        bad.append('Buffer %s: secret missing' % who); continue
    s, b = call('https://api.buffer.com', json.dumps({'query': '{ __typename }'}).encode(), {'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json'})
    check('Buffer ' + who, s, b)
g = os.environ.get('GEMINI_API_KEY', '')
s, b = call('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1', headers={'x-goog-api-key': g})
check('Gemini', s, b)
p = os.environ.get('PEXELS_API_KEY', '')
s, b = call('https://api.pexels.com/v1/search?query=sky&per_page=1', headers={'Authorization': p, 'User-Agent': 'studio'})
check('Pexels', s, b)
print('OK: ' + ', '.join(ok))
open('alert.md', 'w').write('\n'.join('- ' + x for x in bad))
if bad:
    print('PROBLEMS:\n' + '\n'.join(bad)); sys.exit(1)
