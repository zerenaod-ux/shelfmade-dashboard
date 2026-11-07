"""DEPENDENCY MAP + CANARY (GitHub, daily). Probes every free service the system relies on, remembers the last 60 results, predicts running out
(Cloudinary credits), and says which Plan B takes over. Writes publish/deps.json for the Health page. Advice only - changes nothing."""
import json, os, base64, re, datetime, urllib.request, urllib.error, urllib.parse
from pathlib import Path
B = Path(__file__).resolve().parent
OUT = B / 'publish' / 'deps.json'
NOW = datetime.datetime.now(datetime.timezone.utc)


def get(url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data, headers or {'User-Agent': 'studio-canary'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode('utf8', 'ignore')
    except Exception as e:
        return 0, str(e)


def okc(s):   # 200 = up; 429/5xx/0 = busy (not a dead key); 401/403/404 = broken
    return 'up' if s == 200 else ('busy' if s in (0, 429) or s >= 500 else 'down')


def probes():
    P = []
    s, _ = get('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1', {'x-goog-api-key': os.environ.get('GEMINI_API_KEY', '')})
    P.append(('Writer A: Gemini', okc(s), '', 'Writer B-E (Groq > Cerebras > OpenRouter > Mistral) take over per call, Gemini is retried next call'))
    for name, env, url in (('Writer B: Groq', 'GROQ_API_KEY', 'https://api.groq.com/openai/v1/models'), ('Writer C: Cerebras', 'CEREBRAS_API_KEY', 'https://api.cerebras.ai/v1/models'),
                           ('Writer D: OpenRouter', 'OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1/auth/key'), ('Writer E: Mistral', 'MISTRAL_API_KEY', 'https://api.mistral.ai/v1/models')):
        k = os.environ.get(env, '').strip()
        if k:
            s, _ = get(url, {'Authorization': 'Bearer ' + k, 'User-Agent': 'studio-canary'})
            P.append((name, okc(s), '', 'next writer in the chain'))
    s, _ = get('https://api.pexels.com/v1/search?query=sky&per_page=1', {'Authorization': os.environ.get('PEXELS_API_KEY', ''), 'User-Agent': 'studio-canary'})
    P.append(('Stock footage: Pexels', okc(s), '', 'Plan B: Pixabay takes over automatically'))
    _pk = os.environ.get('PIXABAY_API_KEY', '')
    if _pk:
        s, _ = get('https://pixabay.com/api/videos/?key=%s&q=sky&per_page=3' % _pk)
        P.append(('Plan B footage: Pixabay', okc(s), '', 'second footage source (used only when Pexels fails)'))
    for who, env in (('Cloudinary (ShelfMade+MindLore)', 'CLOUDINARY_JSON'), ('Cloudinary (Doodles)', 'CLOUDINARY_JSON_DOODLES')):
        try:
            c = json.loads(os.environ.get(env, '') or '{}')
        except ValueError:
            c = {}
        if not c.get('cloud_name'):
            continue
        a = base64.b64encode((c['api_key'] + ':' + c['api_secret']).encode()).decode()
        s, t = get('https://api.cloudinary.com/v1_1/%s/usage' % c['cloud_name'], {'Authorization': 'Basic ' + a})
        m = re.search(r'"used_percent":\s*([0-9.]+)', t)
        P.append((who, okc(s), m.group(1) if m else '', 'Plan B: GitHub release file link (review still works, no inline player)'))
    for who in ('MINDLORE', 'SHELFMADE', 'DOODLES'):
        t = os.environ.get('BUFFER_TOKEN_' + who, '').strip()
        if t:
            s, _ = get('https://api.buffer.com', {'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json', 'User-Agent': 'studio-canary'}, json.dumps({'query': '{ __typename }'}).encode())
            P.append(('Buffer ' + who.title(), okc(s), '', 'GAP: Instagram/TikTok have only Buffer; posts wait in the queue and retry'))
    cid, sec = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')
    for who in ('MINDLORE', 'SHELFMADE', 'DOODLES'):
        rt = os.environ.get('YT_REFRESH_TOKEN_' + who, '')
        if rt:
            d = urllib.parse.urlencode({'client_id': cid, 'client_secret': sec, 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
            s, _ = get('https://oauth2.googleapis.com/token', {'User-Agent': 'studio-canary'}, d)
            P.append(('YouTube ' + who.title(), okc(s), '', 'Shorts also go through Buffer; full videos wait until the key is reconnected'))
    try:   # Kaggle GPU (Doodles voices/pictures): read the result the Doodles run saved, no extra quota used
        k = json.loads((B / 'data' / 'doodles' / 'kaggle-status.json').read_text())
        st = 'down' if k.get('fails_in_row', 0) >= 2 else 'busy' if k.get('fails_in_row', 0) == 1 else 'up'
        P.append(('Kaggle GPU (Doodles)', st, '', 'OUTAGE MODE: Doodles stops building, gives the story back, retries next run; already-approved Doodles posts keep going out'))
        if st == 'down':
            import subprocess
            r = subprocess.run(['gh', 'issue', 'list', '--state', 'open', '--search', 'ALERT: Kaggle in:title', '--json', 'number'], capture_output=True, text=True)
            if not json.loads(r.stdout or '[]'):
                subprocess.run(['gh', 'issue', 'create', '--title', 'ALERT: Kaggle GPU failing (Doodles paused)', '--body', 'The Kaggle GPU stage failed twice in a row. Doodles stops and retries by itself. Check the Kaggle token/quota if it lasts more than a day.'])
    except Exception:
        pass
    s, _ = get('https://zerenaod-ux.github.io/shelfmade-dashboard/')
    P.append(('GitHub Pages (phone pages)', okc(s), '', 'Issues on GitHub still work for approve/skip'))
    return P


def predict(hist):
    """days until Cloudinary reaches 80% from the last readings (needs >=3 readings over >=2 days)"""
    pts = [(datetime.datetime.fromisoformat(t), float(v)) for t, v in hist if v not in ('', None)]
    if len(pts) < 3:
        return None
    (t0, v0), (t1, v1) = pts[0], pts[-1]
    days = (t1 - t0).total_seconds() / 86400
    if days < 2 or v1 <= v0:
        return None
    rate = (v1 - v0) / days
    return round(max(0.0, (80 - v1) / rate), 1) if v1 < 80 else 0.0


def main():
    old = {}
    try:
        old = json.loads(OUT.read_text())
    except (OSError, ValueError):
        pass
    hist = old.get('history', {})
    rows = []
    for name, st, metric, planb in probes():
        h = hist.get(name, [])
        h.append([NOW.isoformat(timespec='seconds'), st, metric]); hist[name] = h[-60:]
        fails = sum(1 for x in hist[name][-14:] if x[1] == 'down')
        row = {'name': name, 'status': st, 'planb': planb, 'down_recent': fails}
        if metric:
            row['used_percent'] = float(metric)
            eta = predict([(x[0], x[2]) for x in hist[name]])
            if eta is not None:
                row['days_to_80'] = eta
        rows.append(row)
    lvl = 'bad' if any(r['status'] == 'down' for r in rows) else 'warn' if any(r['status'] == 'busy' or r.get('days_to_80', 99) < 14 for r in rows) else 'ok'
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({'at': NOW.isoformat(timespec='seconds'), 'level': lvl, 'rows': rows, 'history': hist}, indent=1))
    print(lvl, [(r['name'], r['status']) for r in rows])


if __name__ == '__main__':
    main()
