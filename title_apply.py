"""Applies OWNER-APPROVED title proposals (G1). Usage: python title_apply.py <issue number> <apply|revert>.
Only proposals whose issue number matches are touched. Only the TITLE is changed (all other fields are sent back exactly as YouTube returned them). Old title is logged for revert."""
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path
B = Path(__file__).resolve().parent
PROP, LOG = B / 'data/growth/title_proposals.json', B / 'data/growth/title_log.json'
CID, SEC = os.environ.get('YT_CLIENT_ID', ''), os.environ.get('YT_CLIENT_SECRET', '')


def jl(p, d):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return d


def access(rt):
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']


def call(tok, url, body=None, method='GET'):
    req = urllib.request.Request(url, json.dumps(body).encode() if body else None, {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}, method=method)
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        raise RuntimeError('HTTP %s %s' % (e.code, e.read()[:300].decode('utf8', 'ignore')))


def set_title(tok, vid, title):
    v = call(tok, 'https://www.googleapis.com/youtube/v3/videos?part=snippet&id=' + vid)['items'][0]['snippet']
    old = v['title']
    v['title'] = title[:100]
    call(tok, 'https://www.googleapis.com/youtube/v3/videos?part=snippet', {'id': vid, 'snippet': {k: v[k] for k in ('title', 'description', 'categoryId') if k in v} | ({'tags': v['tags']} if v.get('tags') else {})}, 'PUT')
    return old


def main():
    num, mode = sys.argv[1], sys.argv[2]
    props, log = jl(PROP, []), jl(LOG, [])
    todo = [p for p in props if str(p.get('issue')) == str(num)]
    toks = {}
    for p in todo:
        if mode == 'apply' and p['status'] != 'proposed':
            continue
        if mode == 'revert' and p['status'] != 'applied':
            continue
        b = p['brand']
        try:
            toks[b] = toks.get(b) or access(os.environ['YT_REFRESH_TOKEN_' + b.upper()])
            if mode == 'apply':
                old = set_title(toks[b], p['id'], p['options'][0]); p['status'] = 'applied'; p['applied'] = datetime.date.today().isoformat()
                log.append({'id': p['id'], 'brand': b, 'old': old, 'new': p['options'][0], 'date': p['applied'], 'vpd_before': p.get('vpd')})
            else:
                set_title(toks[b], p['id'], p['old']); p['status'] = 'reverted'
            print(mode, p['id'], 'ok')
        except Exception as e:
            print(mode, p['id'], 'FAILED', str(e)[:150]); p['status'] = p['status'] if mode == 'revert' else 'failed'
    PROP.write_text(json.dumps(props, indent=1)); LOG.write_text(json.dumps(log, indent=1))


if __name__ == '__main__':
    main()
