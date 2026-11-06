"""AUTOPILOT: owner-away mode. publish/autopilot.json is the single switch (phone page, Health page and laptop Studio all read it).
python autopilot.py on|off  -> flip the switch;  python autopilot.py run  -> (every 3h) decide open review Issues when ON.
Rules when ON: checks-ok -> approve (after hold_hours, max cap per channel per day); duplicate title -> skip now; checks-warn -> skip after 24h;
anything unreviewed > skip_after_hours -> skip. Decisions go through review_decide.py (same path as a manual label)."""
import json, os, subprocess, sys, tempfile, datetime, re
from pathlib import Path

B = Path(__file__).resolve().parent
CFG = B / 'publish' / 'autopilot.json'
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
DEF = {'on': False, 'cap': 3, 'hold_hours': 3, 'skip_after_hours': 48, 'day': '', 'counts': {}, 'changed': '', 'last_run': '', 'log': []}


def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)


def load():
    try:
        c = json.loads(CFG.read_text())
    except (OSError, ValueError):
        c = {}
    d = dict(DEF); d.update(c); return d


def save(c):
    CFG.parent.mkdir(exist_ok=True); CFG.write_text(json.dumps(c, indent=1))


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def decide(i, label):
    ev = {'label': {'name': label}, 'issue': {'number': i['number'], 'body': i.get('body') or '', 'labels': [{'name': l['name']} for l in i['labels']]}}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(ev, f); p = f.name
    env = dict(os.environ, GITHUB_EVENT_PATH=p)
    r = subprocess.run([sys.executable, str(B / 'review_decide.py')], env=env, capture_output=True, text=True, cwd=str(B))
    os.unlink(p)
    return r.returncode == 0, (r.stdout + r.stderr)[-200:]


PUB = {'shelfmade': 'yt-publish-shelfmade.yml', 'mindlore': 'yt-publish-mindlore.yml', 'doodles': 'yt-publish-doodles.yml'}


def paused(brand):   # PAUSE_GUARD: 3+ failures in the channel's last 5 publisher runs -> approve nothing new for it
    try:
        r = sh('gh', 'run', 'list', '--repo', REPO, '--workflow', PUB.get(brand, ''), '--limit', '5', '--json', 'conclusion')
        return sum(1 for x in json.loads(r.stdout or '[]') if x.get('conclusion') == 'failure') >= 3
    except Exception:
        return False


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'run'
    c = load()
    if mode in ('on', 'off'):
        c['on'] = mode == 'on'; c['changed'] = now().isoformat(timespec='seconds'); save(c); print('autopilot', mode); return
    c['last_run'] = now().isoformat(timespec='seconds')
    if not c['on']:
        save(c); print('autopilot off'); return
    today = now().astimezone(datetime.timezone(datetime.timedelta(hours=-6))).date().isoformat()
    if c['day'] != today:
        c['day'] = today; c['counts'] = {}
    r = sh('gh', 'issue', 'list', '--repo', REPO, '--label', 'review', '--state', 'open', '--limit', '100', '--json', 'number,title,body,labels,createdAt')
    try:
        issues = json.loads(r.stdout or '[]')
    except ValueError:
        issues = []
    issues.sort(key=lambda x: x['createdAt'])
    seen_titles = set()
    for i in issues:
        names = [l['name'] for l in i['labels']]
        if 'approve' in names or 'skip' in names:
            continue
        age = (now() - datetime.datetime.fromisoformat(i['createdAt'].replace('Z', '+00:00'))).total_seconds() / 3600
        body = i.get('body') or ''
        m = re.search(r'<!--DATA (.*?) DATA-->', body, re.S)
        try:
            d = json.loads(m.group(1)) if m else {}
        except ValueError:
            d = {}
        brand = d.get('brand') or 'shelfmade'
        title = (d.get('title') or i['title']).strip().lower()
        dup = 'same title already' in body or title in seen_titles
        act, why = None, ''
        if dup and age >= 1:
            act, why = 'skip', 'duplicate title'
        elif age < c['hold_hours']:
            continue
        elif 'checks-ok' in names and paused(brand):
            c['log'] = ([{'t': c['last_run'], 'issue': i['number'], 'act': 'hold', 'why': 'channel paused: publisher failing', 'ok': True}] + c['log'])[:40]
            continue
        elif 'checks-ok' in names:
            if c['counts'].get(brand, 0) < c['cap']:
                act, why = 'approve', 'checks ok'
            elif age >= c['skip_after_hours']:
                act, why = 'skip', 'waited too long (daily cap)'
        elif age >= 24:
            act, why = 'skip', 'checks warn/failed'
        if not act and age >= c['skip_after_hours']:
            act, why = 'skip', 'unreviewed too long'
        if not act:
            continue
        ok, out = decide(i, act)
        if act == 'approve' and ok:
            c['counts'][brand] = c['counts'].get(brand, 0) + 1; seen_titles.add(title)
        c['log'] = ([{'t': c['last_run'], 'issue': i['number'], 'act': act, 'why': why, 'ok': ok}] + c['log'])[:40]
        sh('gh', 'issue', 'comment', str(i['number']), '--repo', REPO, '--body', 'Autopilot: %s (%s).' % (act, why))
        print('autopilot', act, i['number'], why, 'ok' if ok else 'FAILED ' + out)
    save(c)


if __name__ == '__main__':
    main()
