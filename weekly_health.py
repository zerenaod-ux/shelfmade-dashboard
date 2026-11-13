"""WEEKLY HEALTH REPORT (owner 2026-11-13): one phone message every Monday, so slow problems are seen before they break things.
Numbers for the week, posts booked per channel, approved videos stuck waiting to post, Content Engine videos, failed jobs, and keys that expire soon
(publish/key-dates.json). Sent with ntfy (topic from the NTFY_TOPIC secret). Free, no laptop."""
import datetime, json, os, urllib.request
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
APP = 'https://zerenaod-ux.github.io/shelfmade-dashboard/app/'
CH = {'ShelfMade': (['state.json', 'state-shfull.json'], ['approved.json', 'approved-shfull.json'], 'shelfmade'),
      'MindLore': (['state-mindlore.json', 'state-mlfull.json'], ['approved-mindlore.json', 'approved-mlfull.json'], 'mindlore'),
      'AnimationDoodles': (['state-doodles.json', 'state-ddfull.json'], ['approved-doodles.json', 'approved-ddfull.json'], 'doodles')}

def load(p, d):
    try: return json.loads((B / p).read_text())
    except Exception: return d

def T(s):
    try: return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except Exception: return None

def report(now, runs=None):
    L, warn = [], []
    wk = now - datetime.timedelta(days=7)
    h = load('data/daily/history.json', {}); days = sorted(h)
    old = next((d for d in days if d >= (now - datetime.timedelta(days=7)).date().isoformat()), days[0] if days else None)
    for name, (states, appr, key) in CH.items():
        done = {}
        for s in states: done.update(load('publish/' + s, {}).get('done', {}))
        booked = sum(1 for v in done.values() if (T(v.get('due')) or now) >= wk and (T(v.get('due')) or now) <= now)
        v_now = sum((h[days[-1]].get('%s/%s' % (key, p)) or {}).get('views') or 0 for p in ('youtube', 'tiktok', 'instagram')) if days else 0
        v_old = sum((h[old].get('%s/%s' % (key, p)) or {}).get('views') or 0 for p in ('youtube', 'tiktok', 'instagram')) if old else 0
        gain = v_now - v_old
        L.append('%s: %d posts went out, %s views this week%s' % (name, booked, ('+%d' % gain) if gain >= 0 else 'n/a', ''))
        if booked == 0: warn.append('%s posted nothing this week' % name)
    ce = [v for v in load('data/scenes/videos.json', []) if (T(v.get('date')) or wk).date() >= wk.date()]
    L.append('Content Engine: %d new videos this week (not posted)' % len(ce))
    if runs is not None:
        bad = sorted({r['name'] for r in runs if r.get('conclusion') == 'failure' and (T(r['created_at']) or now) >= wk})
        L.append('Jobs that failed at least once: ' + (', '.join(bad[:8]) if bad else 'none'))
    for k in load('publish/key-dates.json', {}).get('items', []):
        e = T(k.get('expires') + 'T00:00:00+00:00') if k.get('expires') else None
        if e and (e - now).days <= 45: warn.append('%s expires %s. %s' % (k['name'], k['expires'], k.get('how', '')))
    return ('NEEDS A LOOK: ' + ' | '.join(warn) + '\n\n' if warn else 'All good this week.\n\n') + '\n'.join(L), bool(warn)

def main():
    now = datetime.datetime.now(datetime.timezone.utc); runs = None
    try:
        req = urllib.request.Request('https://api.github.com/repos/%s/actions/runs?per_page=100&created=>%s' % (REPO, (now - datetime.timedelta(days=7)).date().isoformat()),
                                     headers={'Authorization': 'Bearer ' + os.environ.get('GITHUB_TOKEN', ''), 'Accept': 'application/vnd.github+json'})
        runs = json.load(urllib.request.urlopen(req, timeout=30)).get('workflow_runs', [])
    except Exception as e: print('runs skipped:', e)
    body, warn = report(now, runs); print(body)
    topic = os.environ.get('NTFY_TOPIC', '')
    if topic:
        urllib.request.urlopen(urllib.request.Request('https://ntfy.sh/' + topic, data=body.encode(),
            headers={'Title': 'Weekly health' + (' - needs a look' if warn else ''), 'Tags': 'clipboard', 'Click': APP, 'Priority': 'high' if warn else 'default'}), timeout=30).read()

if __name__ == '__main__':
    main()
