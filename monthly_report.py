"""MONTHLY HEALTH REPORT in plain words (GitHub). One Issue 'Monthly report YYYY-MM' on the 1st (GitHub timers run late, so it also fires after review-publish on days 1-5 if not yet made).
Growth vs ~30 days ago, what the doctor fixed, what broke, retitles, open alerts, what needs the owner. Never posts anything public."""
import datetime, json, os, subprocess
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
def jl(p, d):
    try: return json.loads((B / p).read_text())
    except (OSError, ValueError): return d
def gh(*a):
    return subprocess.run(['gh', *a], capture_output=True, text=True).stdout
def build(today):
    L = ['## Monthly report %s' % today.strftime('%Y-%m'), '', '### Growth (now vs about 30 days ago)']
    sb = jl('data/growth/scoreboard.json', {}).get('brands', {}); hist = jl('data/growth/history.json', [])
    old = None
    for h in hist:
        if (today - datetime.date.fromisoformat(h['date'])).days >= 25: old = h
    for b, v in sb.items():
        t = v.get('totals', {}); o = (old or {}).get(b) or {}
        d = lambda k: ('%+d' % (t.get(k, 0) - o.get(k, 0))) if o else 'n/a (first month)'
        L.append('- %s: %s views (%s), %s subscribers (%s), %s videos (%s)' % (b, t.get('views'), d('views'), t.get('subs'), d('subs'), t.get('videos'), d('videos')))
    L.append('\n### What the system fixed by itself (last 30 days)')
    dl = [x for x in jl('publish/doctor.json', {}).get('log', []) if 'DRILL' not in x.get('msg', '')]
    L.append('- Doctor actions: %d' % len(dl)); [L.append('  - %s %s' % (x['t'], x['msg'][:140])) for x in dl[-8:]]
    lg = jl('data/growth/title_log.json', []); L.append('- Titles improved so far: %d (undo: workflow `retitle`, mode revert-all)' % len([e for e in lg if e.get('source') == 'auto' and not e.get('reverted')]))
    ev = jl('data/growth/exp-s30.json', {}); L.append('- 30-second Shorts test: ' + '; '.join('%s %s' % (b, ev[b].get('verdict')) for b in ('shelfmade', 'mindlore') if b in ev))
    sc = jl('publish/selfcheck.json', {}); bad = [c for c in sc.get('checks', []) if not c.get('ok')]
    L.append('\n### Health now')
    L.append('- Self-check: ' + ('all verified.' if not bad else 'NEEDS A LOOK: ' + '; '.join('%s - %s' % (c['name'], c['text']) for c in bad)))
    try:
        iss = json.loads(gh('issue', 'list', '--repo', REPO, '--state', 'open', '--limit', '50', '--json', 'number,title') or '[]')
        al = [i for i in iss if 'ALERT' in i['title'] or i['title'].startswith('Doctor')]
        L.append('- Open alerts: ' + ('none.' if not al else '; '.join('#%d %s' % (i['number'], i['title'][:50]) for i in al)))
    except Exception: pass
    L.append('\n### Needs you')
    L.append('- Keep Autopilot ON while away; approve pending reviews if it is OFF.')
    L.append('- Check dates: GitLab backup token renew before 2027-11-05. Google login: if uploads stop, re-authorize YouTube (see README).')
    return '\n'.join(L)
def main():
    today = datetime.date.today(); title = 'Monthly report %s' % today.strftime('%Y-%m')
    if os.environ.get('GITHUB_EVENT_NAME') == 'workflow_run' and today.day > 5: print('not the start of the month'); return
    if json.loads(gh('issue', 'list', '--repo', REPO, '--state', 'all', '--search', title + ' in:title', '--json', 'number') or '[]'): print('already exists'); return
    body = build(today); print(body)
    gh('label', 'create', 'report', '--repo', REPO, '--color', '0e8a16')
    subprocess.run(['gh', 'issue', 'create', '--repo', REPO, '--title', title, '--body', body, '--label', 'report'], check=False)
if __name__ == '__main__': main()
