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
for name, env, url in (('Groq', 'GROQ_API_KEY', 'https://api.groq.com/openai/v1/models'), ('Cerebras', 'CEREBRAS_API_KEY', 'https://api.cerebras.ai/v1/models'),
                       ('OpenRouter', 'OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1/auth/key'), ('Mistral', 'MISTRAL_API_KEY', 'https://api.mistral.ai/v1/models')):
    k = os.environ.get(env, '').strip()
    if k:   # optional free fallbacks: only checked when configured
        s, b = call(url, headers={'Authorization': 'Bearer ' + k, 'User-Agent': 'studio/1.0'})
        check(name, s, b)

# CLOUD_GUARD: Cloudinary hosts every Short for review. The key must work and free credits must not run out (80% = alert).
import base64, re as _re
for _who, _env in (('ShelfMade/MindLore', 'CLOUDINARY_JSON'), ('Doodles', 'CLOUDINARY_JSON_DOODLES')):
    try:
        _c = json.loads(os.environ.get(_env, '') or '{}')
    except ValueError:
        _c = {}
    if not _c.get('cloud_name'):
        continue
    _auth = base64.b64encode((_c['api_key'] + ':' + _c['api_secret']).encode()).decode()
    _req = urllib.request.Request('https://api.cloudinary.com/v1_1/%s/usage' % _c['cloud_name'], headers={'Authorization': 'Basic ' + _auth})
    try:
        with urllib.request.urlopen(_req, timeout=40) as _r:
            _st, _txt = _r.status, _r.read().decode('utf8', 'ignore')
    except urllib.error.HTTPError as e:
        _st, _txt = e.code, e.read()[:200].decode('utf8', 'ignore')
    except Exception as e:
        _st, _txt = 0, str(e)
    check('Cloudinary ' + _who, _st, _txt.encode())
    if _st == 200:
        _m = _re.search(r'"used_percent":\s*([0-9.]+)', _txt)
        if _m and float(_m.group(1)) >= 80:
            bad.append('Cloudinary %s: %s%% of free credits used - clean old videos or the review pages stop working' % (_who, _m.group(1)))
print('OK: ' + ', '.join(ok))
open('alert.md', 'w').write('\n'.join('- ' + x for x in bad))
if bad:
    print('PROBLEMS:\n' + '\n'.join(bad)); sys.exit(1)
