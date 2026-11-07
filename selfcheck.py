"""SELF-CHECK + DECISIONS (GitHub, daily, no human). Verifies that the newest features really work and fixes what it can by itself:
  growth scoreboard fresh (<=5 days)      -> else re-runs learn.yml itself; still stale next day -> ALERT issue
  Doodles last run succeeded (<=40 h)     -> else ALERT (autopilot/preflight already retry; this is the final witness)
  Doodles stories carry the best-of-3 judge note (when new ones were written after the feature went live)
  Kaggle status ok and not older than 4 days
Writes publish/selfcheck.json (Health page can show it). An ALERT is opened ONCE per problem and CLOSED by itself when the problem is gone. Never posts, approves or deletes anything."""
import datetime, json, os, subprocess
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
NOW = datetime.datetime.now(datetime.timezone.utc)
LIVE = datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc)   # best-of-3 + spice scripts went live before this day's Doodles run


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True, timeout=90)


def jl(p, d):
    try:
        return json.loads((B / p).read_text())
    except (OSError, ValueError):
        return d


def age_h(iso):
    try:
        return (NOW - datetime.datetime.fromisoformat(iso.replace('Z', '+00:00'))).total_seconds() / 3600
    except Exception:
        return None


def alert(title, body, open_it):
    try:
        r = sh('gh', 'issue', 'list', '--repo', REPO, '--state', 'open', '--search', title + ' in:title', '--json', 'number,title')
        found = [i for i in json.loads(r.stdout or '[]') if i['title'] == title]
        if open_it and not found:
            sh('gh', 'issue', 'create', '--repo', REPO, '--title', title, '--body', body)
        if not open_it:
            for i in found:
                sh('gh', 'issue', 'close', str(i['number']), '--repo', REPO, '--comment', 'Fixed by itself: the check passes again.')
    except Exception:
        pass


def last_run(wf):
    r = sh('gh', 'run', 'list', '--repo', REPO, '--workflow', wf, '--limit', '5', '--json', 'conclusion,status,createdAt,event')
    try:
        return json.loads(r.stdout or '[]')
    except ValueError:
        return []


def main():
    res = []
    def rec(name, ok, text, title=None, fix=None):
        acted = ''
        if not ok and fix:
            try:
                fix(); acted = ' | auto-fix started'
            except Exception as e:
                acted = ' | auto-fix failed: ' + str(e)[:60]
        res.append({'name': name, 'ok': ok, 'text': text + acted})
        if title:
            alert(title, 'Self-check: ' + name + ' - ' + text + acted + '\n\nThis Issue closes itself when the check passes again.', not ok)
    # 1 growth scoreboard fresh
    sb = jl('data/growth/scoreboard.json', {})
    h = age_h(sb.get('updated', ''))
    rec('Growth scoreboard', h is not None and h <= 120, 'updated %s h ago' % (round(h) if h is not None else '?'),
        'ALERT: growth scoreboard is stale', lambda: sh('gh', 'workflow', 'run', 'analytics.yml', '--repo', REPO))
    # 2 Doodles last run
    runs = [r for r in last_run('doodles.yml') if r.get('status') == 'completed']
    ok = bool(runs) and runs[0].get('conclusion') == 'success' and (age_h(runs[0].get('createdAt', '')) or 999) <= 40
    rec('Doodles daily run', ok, 'last: %s %s' % (runs[0].get('conclusion'), runs[0].get('createdAt', '')[:16]) if runs else 'no run found', 'ALERT: Doodles daily run not succeeding')
    # 3 best-of-3 judge visible in new stories
    pool = jl('data/doodles/story_pool.json', [])
    used = jl('data/doodles/used.json', [])
    newer = [s for s in pool if s.get('judge')]
    ran_after = bool(runs) and (datetime.datetime.fromisoformat(runs[0]['createdAt'].replace('Z', '+00:00')) > LIVE + datetime.timedelta(hours=12)) and runs[0].get('conclusion') == 'success'
    rec('Best-of-3 judge', (not ran_after) or bool(newer), ('%d stories carry a judge note' % len(newer)) if newer else 'no judged story yet' + (' AFTER a successful run' if ran_after else ' (no run since it went live)'),
        'ALERT: best-of-3 judge not showing in Doodles stories' if ran_after else None)
    # 4 Kaggle status
    ks = jl('data/doodles/kaggle-status.json', {})
    ka = age_h(ks.get('at', '') or ks.get('updated', ''))
    rec('Kaggle GPU', ks.get('ok', True) and (ka is None or ka <= 96), 'ok=%s, checked %s h ago' % (ks.get('ok'), round(ka) if ka is not None else '?'), 'ALERT: Kaggle GPU failing or silent')
    # 5 free-tier room: any service above 80% used (deps.json) -> alert BEFORE it runs out (cleanup needs the owner's OK, never automatic)
    dp = jl('publish/deps.json', {})
    hot = ['%s %s%%' % (r['name'], r['used_percent']) for r in dp.get('rows', []) if (r.get('used_percent') or 0) >= 80]
    rec('Free-tier room', not hot, ('running out: ' + ', '.join(hot)) if hot else 'all services under 80%', 'ALERT: a free service is above 80% used')
    # 6 private GitLab backup ran OK in the last 40 h
    mr = [r for r in last_run('mirror.yml') if r.get('status') == 'completed']
    ok = bool(mr) and mr[0].get('conclusion') == 'success' and (age_h(mr[0].get('createdAt', '')) or 999) <= 40
    rec('GitLab backup', ok, ('last: %s %s' % (mr[0].get('conclusion'), mr[0].get('createdAt', '')[:16])) if mr else 'no run yet', 'ALERT: GitLab backup not working',
        lambda: sh('gh', 'workflow', 'run', 'mirror.yml', '--repo', REPO))
    out = {'at': NOW.isoformat(timespec='seconds'), 'level': 'ok' if all(r['ok'] for r in res) else 'warn', 'checks': res}
    (B / 'publish').mkdir(exist_ok=True)
    (B / 'publish/selfcheck.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
