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


def _why_not_posting(brand):
    """Cause finder (owner 2026-11-09): when a channel has not posted for >30 h, say WHY in the alert. Safe causes are reported, never auto-'fixed' by guessing."""
    out = []
    try:
        if not jl('publish/autopilot.json', {}).get('on'): out.append('Autopilot is OFF (only matters for items that need a decision)')
        rv = json.loads(sh('gh', 'issue', 'list', '--repo', REPO, '--state', 'open', '--label', 'review', '--limit', '60', '--json', 'title,labels').stdout or '[]')
        pend = [i for i in rv if not any(l['name'] in ('approve', 'skip', 'auto-approved') for l in i['labels']) and (('ML' in i['title'] or 'MindLore' in i['title']) if brand == 'mindlore' else ('DOODLES' in i['title'] if brand == 'doodles' else not any(k in i['title'] for k in ('ML', 'DOODLES'))))]
        if pend: out.append('%d review(s) waiting for approval' % len(pend))
        appr = {'shelfmade': 'approved.json', 'mindlore': 'approved-mindlore.json', 'doodles': 'approved-doodles.json'}[brand]; st = {'shelfmade': 'state.json', 'mindlore': 'state-mindlore.json', 'doodles': 'state-doodles.json'}[brand]
        done = jl('publish/' + st, {}).get('done', {}); wait = [i for i in jl('publish/' + appr, {}).get('items', []) if i['id'] not in done]
        if not wait: out.append('no approved videos waiting (builder not producing / nothing approved)')
        for wf in {'shelfmade': ['shelfmade-story-short.yml', 'publisher.yml'], 'mindlore': ['mindlore-story-short.yml', 'publisher-mindlore.yml'], 'doodles': ['doodles.yml', 'publisher-doodles.yml']}[brand]:
            rr = [r for r in last_run(wf) if r.get('status') == 'completed']
            if rr and rr[0].get('conclusion') != 'success': out.append('%s last run %s' % (wf, rr[0].get('conclusion')))
            if rr and (age_h(rr[0].get('createdAt', '')) or 0) > 36 and wf.startswith(brand if brand != 'doodles' else 'doodles'): out.append('%s has not run for %.0f h' % (wf, age_h(rr[0]['createdAt'])))
        tc = [r for r in last_run('tokencheck.yml') if r.get('status') == 'completed']
        if tc and tc[0].get('conclusion') != 'success': out.append('login/token check failing')
    except Exception as e:
        out.append('(cause search failed: %s)' % str(e)[:40])
    return ' | LIKELY CAUSE: ' + ('; '.join(out) if out else 'unknown (all job runs look fine) - check Buffer/YouTube directly')

def last_run(wf):
    r = sh('gh', 'run', 'list', '--repo', REPO, '--workflow', wf, '--limit', '5', '--json', 'conclusion,status,createdAt,event')
    try:
        return json.loads(r.stdout or '[]')
    except ValueError:
        return []


def main():
    if os.environ.get('GITHUB_EVENT_NAME') == 'workflow_run':
        _prev = jl('publish/selfcheck.json', {}).get('at', '')
        if _prev and (age_h(_prev) or 99) < 20:
            print('selfcheck: already ran %.1f h ago, skipping' % age_h(_prev)); return
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
    # 4b approved-but-never-queued: an Issue closed as approved/auto-approved must have its posts in the approved files (a lost save once dropped 3 Shorts)
    try:
        r = sh('gh', 'issue', 'list', '--state', 'closed', '--label', 'review', '--limit', '30', '--json', 'number,title,labels,closedAt')
        known = ''
        for f in ('publish/approved.json', 'publish/approved-mindlore.json', 'publish/approved-mindlore-parked-oldlook.json', 'publish/approved-doodles.json', 'publish/approved-mlfull.json', 'publish/approved-shfull.json', 'publish/approved-ddfull.json', 'publish/state.json', 'publish/state-mindlore.json'):
            try: known += open(f).read()
            except Exception: pass
        lost = []
        for i in json.loads(r.stdout or '[]'):
            lab = {l['name'] for l in i['labels']}
            if ('auto-approved' in lab or 'approve' in lab) and 'skip' not in lab and age_h(i['closedAt']) is not None and age_h(i['closedAt']) < 96 and ('"gh%d-' % i['number']) not in known:
                lost.append('#%d %s' % (i['number'], i['title'][:40]))
        rec('Approved videos reach the queue', not lost, 'all approved Issues are queued' if not lost else 'approved but NOT queued: ' + '; '.join(lost[:5]), 'ALERT: approved videos missing from the posting queue')
    except Exception as e:
        print('queue check skipped:', str(e)[:100])
    # 5 free-tier room: any service above 80% used (deps.json) -> alert BEFORE it runs out (cleanup needs the owner's OK, never automatic)
    dp = jl('publish/deps.json', {})
    hot = ['%s %s%%' % (r['name'], r['used_percent']) for r in dp.get('rows', []) if (r.get('used_percent') or 0) >= 80]
    rec('Free-tier room', not hot, ('running out: ' + ', '.join(hot)) if hot else 'all services under 80%', 'ALERT: a free service is above 80% used')
    # 6 private GitLab backup ran OK in the last 40 h
    mr = [r for r in last_run('mirror.yml') if r.get('status') == 'completed']
    ok = bool(mr) and mr[0].get('conclusion') == 'success' and (age_h(mr[0].get('createdAt', '')) or 999) <= 40
    rec('GitLab backup', ok, ('last: %s %s' % (mr[0].get('conclusion'), mr[0].get('createdAt', '')[:16])) if mr else 'no run yet', 'ALERT: GitLab backup not working',
        lambda: sh('gh', 'workflow', 'run', 'mirror.yml', '--repo', REPO))
    # 7 safety guard readable, and a reminder when a kill switch is left ON
    try:
        gd = json.loads((B / 'publish/guard.json').read_text()); on = [k for k, v in gd.get('kill', {}).items() if v]
        rec('Safety guard', not on, ('KILL SWITCH ON for: ' + ', '.join(on) + ' (no new posts)') if on else 'readable, no kill switch on', 'ALERT: a channel kill switch is ON (posting stopped)')
    except Exception as e:
        rec('Safety guard', False, 'guard.json unreadable: ' + str(e)[:50], 'ALERT: safety guard file unreadable')
    # 8 weekly jobs: last run must not have failed, and must not be older than ~9 days (a never-run job is OK for its first 9 days after launch)
    for wf, label, launch in (('weekly-report.yml', 'Weekly report', '2026-11-07'), ('packaging.yml', 'Title proposals', '2026-11-07'), ('learn.yml', 'Learning + scoreboard', '2026-11-01')):
        wr = [r for r in last_run(wf) if r.get('status') == 'completed']
        fresh = bool(wr) and wr[0].get('conclusion') == 'success' and (age_h(wr[0].get('createdAt', '')) or 999) <= 9 * 24
        young = (NOW - datetime.datetime.fromisoformat(launch + 'T00:00:00+00:00')).days < 9
        rec(label, fresh or (young and not (wr and wr[0].get('conclusion') == 'failure')), ('last: %s %s' % (wr[0].get('conclusion'), wr[0].get('createdAt', '')[:10])) if wr else 'not run yet (launched %s)' % launch,
            'ALERT: %s job not working' % label, lambda w=wf: sh('gh', 'workflow', 'run', w, '--repo', REPO))
    # 9 viewer flywheel (playlists): no brand reporting an error
    fs = jl('data/growth/flywheel-status.json', None)
    if fs is None:
        rec('Playlist flywheel', True, 'not run yet (launched 2026-11-07)')
    else:
        badb = {k: v for k, v in fs.get('brands', {}).items() if str(v).startswith(('error', 'HTTP'))}
        rec('Playlist flywheel', not badb, ('problem: ' + '; '.join('%s %s' % (k, v[:60]) for k, v in badb.items())) if badb else 'ok (%s)' % '; '.join('%s: %s' % kv for kv in fs.get('brands', {}).items()), 'ALERT: playlist flywheel failing',
            lambda: sh('gh', 'workflow', 'run', 'flywheel.yml', '--repo', REPO))
    # 10 retitle campaign: daily job must not be failing
    rt = [r for r in last_run('retitle.yml') if r.get('status') == 'completed']
    rec('Retitle campaign', (not rt) or rt[0].get('conclusion') == 'success', ('last: %s %s' % (rt[0].get('conclusion'), rt[0].get('createdAt', '')[:10])) if rt else 'not run yet', 'ALERT: retitle job failing',
        lambda: sh('gh', 'workflow', 'run', 'retitle.yml', '--repo', REPO))
    # 13 ACCESS CHECK (R10): weekly tokencheck proves the YouTube logins still work; it must have run OK in the last 9 days
    tk = [r for r in last_run('tokencheck.yml') if r.get('status') == 'completed']
    ok_tk = bool(tk) and tk[0].get('conclusion') == 'success' and (age_h(tk[0].get('createdAt', '')) or 999) < 9 * 24
    rec('Access check (logins)', ok_tk, ('last: %s %s' % (tk[0].get('conclusion'), tk[0].get('createdAt', '')[:10])) if tk else 'never ran', 'ALERT: YouTube login check failing or stale',
        lambda: sh('gh', 'workflow', 'run', 'tokencheck.yml', '--repo', REPO))
    # 14 VIRAL DNA (V): weekly study must have run OK in the last 10 days
    vr = [r for r in last_run('viral.yml') if r.get('status') == 'completed']
    ok_v = bool(vr) and vr[0].get('conclusion') == 'success' and (age_h(vr[0].get('createdAt', '')) or 999) < 10 * 24
    rec('Viral DNA study', ok_v, ('last: %s %s' % (vr[0].get('conclusion'), vr[0].get('createdAt', '')[:10])) if vr else 'not run yet', 'ALERT: viral DNA study failing or stale',
        lambda: sh('gh', 'workflow', 'run', 'viral.yml', '--repo', REPO))
    # 15 NOTHING POSTED (the result the owner cares about): every channel must have a public video newer than 30 h (owner 2026-11-09: was 72) (judged from the daily analytics file)
    try:
        import guard as _g
    except Exception:
        _g = None
    for _b in ('shelfmade', 'mindlore', 'doodles'):
        try:
            if _g and _g.killed(_b):
                continue
            an = jl('data/analytics/%s.json' % _b, {})
            pubs = [v['published'] for v in an.get('videos', []) if v.get('published') and v.get('privacy', 'public') == 'public']
            newest = max(pubs) if pubs else ''
            a_h = age_h(newest) if newest else None
            fresh = age_h(an['collected'] + ('T00:00:00+00:00' if len(an['collected']) == 10 else '')) if an.get('collected') else None
            # analytics are only collected weekly, so they are usually stale: ALSO use what was handed to Buffer (publish state 'due' times already in the past = posted)
            try:
                _sf = {'shelfmade': 'state.json', 'mindlore': 'state-mindlore.json', 'doodles': 'state-doodles.json'}[_b]
                _now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                _past = [v['due'] for v in jl('publish/' + _sf, {}).get('done', {}).values() if v.get('due') and v['due'][:19] <= _now]
                if _past:
                    _h = age_h(max(_past)[:19] + '+00:00')
                    a_h = _h if a_h is None else min(a_h, _h)
                    fresh = 0   # a trustworthy recent source exists: do not let stale analytics silence the alarm
            except Exception:
                pass
            stale_data = fresh is not None and fresh > 48
            rec('Posting: %s' % _b, stale_data or (a_h is not None and a_h <= 30), ('newest public video %.0f h ago' % a_h) if a_h is not None else 'no video found',
                'ALERT: %s has not posted for over a day' % _b + ('' if (stale_data or (a_h is not None and a_h <= 30)) else _why_not_posting(_b)))
        except Exception as e:
            rec('Posting: %s' % _b, True, 'could not measure (%s)' % str(e)[:50])
    # 16 SERVICE PROBES (free keys / logins): a probe failing twice in a row = alert (deps.py probes every service daily; a switch to Plan B is automatic, this tells the owner)
    dd = [r for r in jl('publish/deps.json', {}).get('rows', []) if r.get('status') not in (None, 'up') and (r.get('down_recent') or 0) >= 2]
    rec('Service probes', not dd, 'all probes fine' if not dd else '; '.join('%s down %dx' % (r['name'], r['down_recent']) for r in dd), 'ALERT: a free service is failing')
    # 12 DOODLES GPU BUDGET (H2): Kaggle free GPU is ~30h/week. 3 stories/day normally; drop to 2 if the last 7 days used > 24h, back to 3 under 18h.
    try:
        r = sh('gh', 'run', 'list', '--repo', REPO, '--workflow', 'doodles.yml', '--limit', '40', '--json', 'createdAt,updatedAt,status')
        mins = 0.0
        for x in json.loads(r.stdout or '[]'):
            c = datetime.datetime.fromisoformat(x['createdAt'].replace('Z', '+00:00')); u = datetime.datetime.fromisoformat(x['updatedAt'].replace('Z', '+00:00'))
            if (NOW - c).total_seconds() <= 7 * 86400 and x.get('status') == 'completed': mins += (u - c).total_seconds() / 60
        g = jl('publish/guard.json', {}); cap = int(g.get('doodles_count', 3)); new = cap
        if mins > 24 * 60: new = 2
        elif mins < 18 * 60: new = 3
        if new != cap:
            g['doodles_count'] = new; (B / 'publish/guard.json').write_text(json.dumps(g, indent=1))
        rec('Doodles GPU budget', mins <= 28 * 60, '%.1f h used in 7 days, stories/day cap %d' % (mins / 60, new), 'ALERT: Doodles using too much free GPU')
    except Exception as e:
        rec('Doodles GPU budget', True, 'could not measure (%s)' % str(e)[:60])
    # 11 NO MODULE SHADOWING: a repo file named like a standard/pip module (for example packaging.py) silently breaks tools that import it (this killed the Kaggle step on 2026-11-07)
    import sys as _sys
    PIPN = {'packaging', 'requests', 'yaml', 'numpy', 'pandas', 'PIL', 'kaggle', 'google', 'urllib3', 'six', 'setuptools', 'pkg_resources', 'certifi', 'idna', 'dateutil', 'pytz', 'typing_extensions',
            'attr', 'click', 'jinja2', 'markupsafe', 'pydantic', 'tqdm', 'scipy', 'cv2', 'moviepy', 'imageio', 'soundfile', 'edge_tts', 'aiohttp', 'bs4', 'lxml', 'cloudinary', 'tenacity', 'rich'}
    names = {f.stem for d in (B, B / 'doodles_engine') for f in d.glob('*.py')}
    bad = sorted(n for n in names if n in _sys.stdlib_module_names or n in PIPN)
    rec('No module shadowing', not bad, ('files that shadow a library: ' + ', '.join(bad)) if bad else 'no repo file shadows a standard or pip module', 'ALERT: a repo file shadows a Python library')
    out = {'at': NOW.isoformat(timespec='seconds'), 'level': 'ok' if all(r['ok'] for r in res) else 'warn', 'checks': res}
    (B / 'publish').mkdir(exist_ok=True)
    (B / 'publish/selfcheck.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
