"""READY-TO-LEAVE check (runs daily on GitHub): writes publish/preflight.json for the Health page. Advice only, changes nothing."""
import json, os, subprocess, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
RETIRED = {'music-ace', 'music-test', 'phone-test', 'short-test', 'test-build', 'llmtest', 'sm-sources', 'analytics-old'}
NOW = datetime.datetime.now(datetime.timezone.utc)


def gh(*a):
    r = subprocess.run(['gh', *a], capture_output=True, text=True, timeout=90)
    try:
        return json.loads(r.stdout or 'null')
    except ValueError:
        return None


def jl(p, d):
    try:
        return json.loads((B / p).read_text())
    except (OSError, ValueError):
        return d


def main():
    ch = []
    add = lambda n, lvl, t: ch.append({'name': n, 'level': lvl, 'text': t})
    ap = jl('publish/autopilot.json', {})
    add('Autopilot', 'ok' if ap.get('on') else 'warn', 'ON' if ap.get('on') else 'OFF - turn it ON on the Review page before you leave')
    wf = gh('workflow', 'list', '--repo', REPO, '--json', 'name,id,state', '--limit', '100') or []
    failed = []
    for w in wf:
        if w['name'] in RETIRED or w['state'] != 'active':
            continue
        runs = gh('run', 'list', '--repo', REPO, '--workflow', str(w['id']), '--limit', '1', '--json', 'conclusion,status') or []
        if runs and runs[0].get('conclusion') == 'failure':
            failed.append(w['name'])
    add('Jobs', 'ok' if not failed else 'warn', 'every job last ran fine' if not failed else 'last run failed: ' + ', '.join(failed[:6]))
    al = gh('issue', 'list', '--repo', REPO, '--state', 'open', '--search', 'ALERT in:title', '--json', 'number,title') or []
    al = [a for a in al if a['title'].startswith('ALERT:')]
    add('Alerts', 'ok' if not al else 'bad', 'no open alerts' if not al else '%d open: %s' % (len(al), '; '.join(a['title'][:40] for a in al[:3])))
    tc = gh('run', 'list', '--repo', REPO, '--workflow', 'tokencheck.yml', '--limit', '1', '--json', 'conclusion,createdAt') or []
    if tc:
        age = (NOW - datetime.datetime.fromisoformat(tc[0]['createdAt'].replace('Z', '+00:00'))).days
        add('Keys', 'ok' if tc[0].get('conclusion') == 'success' and age <= 8 else 'warn', 'weekly key test %s, %d days ago' % (tc[0].get('conclusion'), age))
    else:
        add('Keys', 'warn', 'no key test found')
    pool = jl('data/doodles/story_pool.json', []); used = set(jl('data/doodles/used.json', []))
    left = sum(1 for s in pool if s['id'] not in used)
    add('Doodles stories', 'ok', '%d unused saved (more are written automatically)' % left)
    q = len(jl('publish/queue.json', {}).get('items', []))
    add('ShelfMade posts waiting', 'ok' if q >= 6 else 'warn', '%d in the queue' % q)
    rv = gh('issue', 'list', '--repo', REPO, '--state', 'open', '--label', 'review', '--json', 'number') or []
    add('Waiting for review', 'ok' if len(rv) <= 6 else 'warn', '%d videos open (autopilot clears them when ON)' % len(rv))
    lv = 'bad' if any(c['level'] == 'bad' for c in ch) else 'warn' if any(c['level'] == 'warn' for c in ch) else 'ok'
    (B / 'publish').mkdir(exist_ok=True)
    (B / 'publish' / 'preflight.json').write_text(json.dumps({'at': NOW.isoformat(timespec='seconds'), 'ready': lv, 'checks': ch}, indent=1))
    print(lv, [c['name'] + ':' + c['level'] for c in ch])


if __name__ == '__main__':
    main()
