"""Stopgap for GitHub's throttled schedules: once an hour the Mac checks the light workflows (senders, review, watchdog) and
starts any that has not run for a while. Safe to repeat: senders keep their own state and never double-post.
Needs the gh command on the Mac (already logged in). Never touches the heavy video builders and never approves anything."""
import json, os, shutil, subprocess, time
from datetime import datetime, timezone

REPO = 'zerenaod-ux/shelfmade-dashboard'
# workflow -> hours without a run before the Mac starts it
LIGHT = {'publisher.yml': 3, 'publisher-mindlore.yml': 3, 'publisher-doodles.yml': 6,
         'yt-publish-mindlore.yml': 6, 'yt-publish-shelfmade.yml': 6, 'yt-publish-doodles.yml': 6, 'review-publish.yml': 2, 'watchdog.yml': 12}


def _gh():
    for p in (shutil.which('gh'), '/opt/homebrew/bin/gh', '/usr/local/bin/gh'):
        if p and os.path.exists(p):
            return p
    return None


def kick():
    gh = _gh()
    if not gh:
        print('gh_kick: gh not found', flush=True)
        return 0
    n = 0
    for wf, hrs in LIGHT.items():
        try:
            r = subprocess.run([gh, 'run', 'list', '--workflow', wf, '--repo', REPO, '--limit', '1', '--json', 'createdAt,status'],
                               capture_output=True, text=True, timeout=60)
            runs = json.loads(r.stdout or '[]')
            if runs and runs[0].get('status') in ('queued', 'in_progress'):
                continue
            last = datetime.fromisoformat(runs[0]['createdAt'].replace('Z', '+00:00')) if runs else None
            age = (datetime.now(timezone.utc) - last).total_seconds() / 3600 if last else 999
            if age >= hrs:
                subprocess.run([gh, 'workflow', 'run', wf, '--repo', REPO], capture_output=True, timeout=60)
                print('gh_kick: started %s (last run %.1f h ago)' % (wf, age), flush=True)
                n += 1
        except Exception as e:
            print('gh_kick: %s skipped: %s' % (wf, str(e)[:80]), flush=True)
    return n
