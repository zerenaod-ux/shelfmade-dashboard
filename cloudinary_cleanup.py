"""Free up Cloudinary room by deleting OLD review videos that nothing needs any more (owner approved 2026-11-25).
Safe rules: only videos older than MIN_DAYS (default 7); never one whose public_id appears in any publish/*.json (queued, approved or parked posts)
or in an open Issue; never the newest KEEP_NEWEST. Dry run unless APPLY=1. Prints counts and sizes only, never secrets."""
import base64, datetime, json, os, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path
MIN_DAYS = float(os.environ.get('MIN_DAYS', '7')); KEEP_NEWEST = 30; APPLY = os.environ.get('APPLY') == '1'

def call(c, method, path, data=None):
    auth = base64.b64encode((c['api_key'] + ':' + c['api_secret']).encode()).decode()
    url = 'https://api.cloudinary.com/v1_1/%s/%s' % (c['cloud_name'], path)
    body = urllib.parse.urlencode(data, doseq=True).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={'Authorization': 'Basic ' + auth})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())

def referenced_text():
    t = ''
    for p in Path('publish').glob('*.json'):
        try: t += p.read_text()
        except OSError: pass
    for d in ('data', 'gh-state'):
        for p in Path(d).rglob('*.json'):
            try: t += p.read_text()
            except OSError: pass
    try:
        t += subprocess.run(['gh', 'issue', 'list', '--state', 'open', '--limit', '200', '--json', 'body'], capture_output=True, text=True).stdout
    except Exception: pass
    return t

def run(who, env):
    try: c = json.loads(os.environ.get(env, '') or '{}')
    except ValueError: c = {}
    if not c.get('cloud_name'): print(who, 'no credentials, skipped'); return
    refs = referenced_text(); items = []; cursor = None
    while True:
        q = 'resources/video?max_results=500' + ('&next_cursor=' + cursor if cursor else '')
        d = call(c, 'GET', q); items += d.get('resources', []); cursor = d.get('next_cursor')
        if not cursor: break
    items.sort(key=lambda r: r['created_at'], reverse=True)
    now = datetime.datetime.now(datetime.timezone.utc); gone = []; keep = 0; total = sum(r.get('bytes', 0) for r in items)
    for i, r in enumerate(items):
        age = (now - datetime.datetime.fromisoformat(r['created_at'].replace('Z', '+00:00'))).total_seconds() / 86400
        pid = r['public_id'].split('/')[-1]
        if i < KEEP_NEWEST or age < MIN_DAYS or pid in refs: keep += 1; continue
        gone.append(r)
    freed = sum(r.get('bytes', 0) for r in gone)
    print('%s: %d videos (%.0f MB); delete %d (%.0f MB); keep %d; apply=%s' % (who, len(items), total / 1e6, len(gone), freed / 1e6, keep, APPLY), flush=True)
    if APPLY:
        for k in range(0, len(gone), 100):
            ids = [r['public_id'] for r in gone[k:k + 100]]
            res = call(c, 'DELETE', 'resources/video/upload', {'public_ids[]': ids})
            print('  deleted batch', len(res.get('deleted', {})), flush=True)
    return {'who': who, 'videos': len(items), 'deleted' if APPLY else 'would_delete': len(gone), 'mb_freed' if APPLY else 'mb_would_free': round(freed / 1e6)}

if __name__ == '__main__':
    out = [x for x in (run('ShelfMade/MindLore', 'CLOUDINARY_JSON'), run('Doodles', 'CLOUDINARY_JSON_DOODLES')) if x]
    Path('cloudinary-cleanup-result.json').write_text(json.dumps({'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'results': out}))
