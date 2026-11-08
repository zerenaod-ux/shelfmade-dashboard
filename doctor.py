"""Self-healing doctor. Runs every 3h in GitHub Actions (free, no laptop).
Finds a workflow whose latest run failed, reads the log, then:
  1. playbook  - known harmless causes (quota, network) -> just wait, say so
  2. rollback  - a code commit made since the last good run AND named in the error log is reverted
  3. ai patch  - free LLM proposes a tiny exact-string fix (root .py only, <=25 lines, must compile)
Every change is verified: the workflow is re-run; if it still fails the change is undone and an
ALERT issue explains what was tried. Max 2 attempts per failure. Kill switch: publish/doctor.json {"on":false}.
Never edits .github/, never touches data/ or secrets."""
import json, os, re, subprocess, sys, time, py_compile
from pathlib import Path
from datetime import datetime, timezone

REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
STATE = Path('publish/doctor.json')
SKIP = {'watchdog', 'doctor', 'selfcheck', 'pages build and deployment'}
MAX_ATTEMPTS = 2
PLAYBOOK = [  # (regex, why) -> nothing to change in code; it heals itself
    (r'quotaExceeded|exceeded your (daily )?quota|rate.?limit|429', 'API quota/rate limit: resets by itself'),
    (r'Temporary failure in name resolution|Connection (reset|timed out)|502 Bad Gateway|503 Service', 'Network blip: next run retries'),
]

def sh(*a, check=False):
    r = subprocess.run(a, capture_output=True, text=True)
    if check and r.returncode: raise RuntimeError(' '.join(a) + ': ' + (r.stderr or r.stdout)[-400:])
    return r.stdout.strip() if r.returncode == 0 else ''

def api(path, *extra):
    out = sh('gh', 'api', '-H', 'Accept: application/vnd.github+json', *extra, 'repos/%s/%s' % (REPO, path))
    try: return json.loads(out) if out else {}
    except ValueError: return {}

def load():
    try: s = json.loads(STATE.read_text())
    except (OSError, ValueError): s = {}
    s.setdefault('on', True); s.setdefault('attempts', {}); s.setdefault('pending', []); s.setdefault('log', [])
    return s

def save(s):
    s['log'] = s['log'][-60:]; s['at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    STATE.write_text(json.dumps(s, indent=1))

def note(s, msg):
    print('DOCTOR:', msg, flush=True); s['log'].append({'t': datetime.now(timezone.utc).strftime('%m-%d %H:%MZ'), 'msg': msg})

def issue(title, body, close=False):
    n = sh('gh', 'issue', 'list', '--state', 'open', '--search', title + ' in:title', '--json', 'number', '-q', '.[0].number')
    if close:
        if n: sh('gh', 'issue', 'close', n, '--comment', body)
    elif n: sh('gh', 'issue', 'comment', n, '--body', body)
    else: sh('gh', 'issue', 'create', '--title', title, '--body', body)

def latest_runs():
    runs = api('actions/runs?per_page=100&branch=master').get('workflow_runs', [])
    by = {}
    for r in runs:
        if r['status'] != 'completed' or r['name'] in SKIP: continue
        by.setdefault(r['name'], []).append(r)
    return by

def failed_log(run_id):
    return sh('gh', 'run', 'view', str(run_id), '-R', REPO, '--log-failed')[-9000:]

def suspects(last_ok_sha, bad_sha, log):
    """Code commits between last good run and the failed run whose files are named in the log."""
    if not last_ok_sha or last_ok_sha == bad_sha: return []
    cmp = api('compare/%s...%s' % (last_ok_sha, bad_sha)).get('commits', [])
    out = []
    for c in reversed(cmp):  # newest first
        files = [f['filename'] for f in api('commits/' + c['sha']).get('files', [])]
        code = [f for f in files if f.endswith('.py') and '/' not in f]
        if not code or any(f.startswith('.github/') for f in files): continue
        if any(f in log or f[:-3] in log for f in code): out.append((c['sha'], c['commit']['message'].splitlines()[0], code))
    return out

def compiles():
    return all(not _bad(p) for p in Path('.').glob('*.py'))
def _bad(p):
    try: py_compile.compile(str(p), doraise=True); return False
    except Exception: return True

def push(msg):
    sh('git', 'config', 'user.name', 'doctor-bot'); sh('git', 'config', 'user.email', 'bot@users.noreply.github.com')
    sh('git', 'add', '-A', '--', '*.py', 'publish/doctor.json')
    if not sh('git', 'status', '--porcelain'): return None
    sh('git', 'commit', '-qm', msg)
    for _ in range(3):
        if subprocess.run(['git', 'push', '-q'], capture_output=True).returncode == 0: break
        sh('git', 'pull', '-q', '--rebase')
    return sh('git', 'rev-parse', 'HEAD')

def rerun(wf_id):
    subprocess.run(['gh', 'workflow', 'run', str(wf_id), '-R', REPO, '--ref', 'master'], capture_output=True)

def ai_patch(log):
    """Ask the free LLM for one exact replacement. Returns (file, old, new, why) or None."""
    try:
        import llm
        if not llm.available(): return None
        files = []
        for f in dict.fromkeys(re.findall(r'File "(?:/[^"]*/)?([A-Za-z0-9_]+\.py)", line (\d+)', log)):
            if Path(f[0]).is_file(): files.append(f)
        if not files: return None
        name, ln = files[-1]; ln = int(ln); src = Path(name).read_text().splitlines()
        ctx = '\n'.join('%d: %s' % (i + 1, src[i]) for i in range(max(0, ln - 25), min(len(src), ln + 25)))
        r = llm.json_call('You are a careful Python maintainer. Reply JSON only.',
            'A CI job failed. Error log tail:\n%s\n\nCode of %s around line %d:\n%s\n\nPropose the smallest safe fix as JSON '
            '{"old":"exact text copied from the code, must appear once","new":"replacement","why":"one sentence"}. '
            'If it is not a code bug (network, quota, data) reply {"old":""}.' % (log[-3500:], name, ln, ctx), temperature=0.1)
        if not r or not r.get('old') or r['old'] == r.get('new'): return None
        return name, r['old'], r.get('new', ''), r.get('why', '')
    except Exception as e:
        print('ai_patch error', e); return None

def main():
    s = load()
    if not s['on']: print('doctor off'); return
    by = latest_runs(); wfs = {w['name']: w['id'] for w in api('actions/workflows?per_page=100').get('workflows', [])}
    now = time.time(); changed = False
    # 1) verify earlier fixes
    keep = []
    for p in s['pending']:
        runs = [r for r in by.get(p['wf'], []) if r['created_at'] > p['at']]
        if not runs and now - p['ts'] < 7200: keep.append(p); continue
        if runs and runs[0]['conclusion'] == 'success':
            note(s, 'VERIFIED fix for %s (%s)' % (p['wf'], p['what'])); s['attempts'].pop(p['wf'], None)
            issue('Doctor: ' + p['wf'], 'Fixed and verified: %s.' % p['what'], close=True); changed = True
        else:
            note(s, 'FIX FAILED for %s, undoing (%s)' % (p['wf'], p['what']))
            sh('git', 'pull', '-q', '--rebase'); sh('git', 'revert', '--no-edit', p['commit'])
            push('doctor: undo unhelpful fix %s' % p['commit'][:7])
            issue('Doctor: ' + p['wf'], 'I tried: %s. It did not fix the failure, so I undid it. Needs a human (or the next attempt). Log tail:\n```\n%s\n```' % (p['what'], p.get('log', '')[-1500:])); changed = True
    s['pending'] = keep
    # 2) diagnose failing workflows
    for name, runs in by.items():
        last = runs[0]
        if last['conclusion'] == 'success':
            if name in s['attempts']: s['attempts'].pop(name); issue('Doctor: ' + name, 'Healthy again.', close=True); changed = True
            continue
        if last['conclusion'] not in ('failure', 'timed_out') or any(p['wf'] == name for p in s['pending']): continue
        if now - datetime.fromisoformat(last['updated_at'].replace('Z', '+00:00')).timestamp() > 86400: continue
        if s['attempts'].get(name, 0) >= MAX_ATTEMPTS: continue
        log = failed_log(last['id'])
        why = next((w for rx, w in PLAYBOOK if re.search(rx, log, re.I)), None)
        if why: note(s, '%s: %s (no change needed)' % (name, why)); changed = True; continue
        s['attempts'][name] = s['attempts'].get(name, 0) + 1
        ok_sha = next((r['head_sha'] for r in runs if r['conclusion'] == 'success'), None)
        what = None; sha = None
        sus = suspects(ok_sha, last['head_sha'], log)
        if sus and not any(c['sha'] == sus[0][0] for c in s.get('undone', [])):
            c, msg, files = sus[0]
            if subprocess.run(['git', 'revert', '--no-edit', c], capture_output=True).returncode == 0 and compiles():
                what = 'rolled back %s "%s" (%s)' % (c[:7], msg, ', '.join(files)); s.setdefault('undone', []).append({'sha': c})
            else: sh('git', 'revert', '--abort')
        if not what:
            p = ai_patch(log)
            if p:
                f, old, new, w = p; t = Path(f).read_text()
                if t.count(old) == 1 and abs(len(new.splitlines()) - len(old.splitlines())) <= 25 and len(old.splitlines()) <= 25:
                    Path(f).write_text(t.replace(old, new, 1))
                    if _bad(Path(f)): Path(f).write_text(t)
                    else: what = 'AI patch in %s: %s' % (f, w)
        if what:
            sha = push('doctor: ' + what[:100])
            if sha:
                rerun(wfs.get(name, last['workflow_id']))
                s['pending'].append({'wf': name, 'commit': sha, 'what': what, 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'ts': now, 'log': log[-1500:]})
                note(s, '%s: %s -> re-run started' % (name, what)); issue('Doctor: ' + name, 'Failure found. I did: %s. Re-run started; I will verify it.' % what); changed = True; continue
        note(s, '%s: no safe automatic fix found' % name)
        issue('Doctor: ' + name, 'Failed run %s. No safe automatic fix found (attempt %d/%d). Log tail:\n```\n%s\n```' % (last['html_url'], s['attempts'][name], MAX_ATTEMPTS, log[-2000:])); changed = True
    save(s)
    sh('git', 'add', 'publish/doctor.json'); push('doctor: state') if sh('git', 'status', '--porcelain') else None

if __name__ == '__main__':
    main()
