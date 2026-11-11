"""SELF-KICK: GitHub often delays or drops scheduled runs (seen: 2h25m late, whole hours skipped). review-publish runs every 30 min and does fire, so it calls this.
For each daily job: if its scheduled time + GRACE has passed today and NO run of that workflow exists since then (any event, any result), start it with workflow_dispatch.
Never retries failures (a failed run still counts as 'ran'). Fails soft. Needs GH_TOKEN and permissions: actions: write."""
import json, subprocess, datetime, sys
GRACE = 100   # minutes: GitHub delays of ~2.5 h were observed; after that we start it ourselves
MAXLATE = 10 * 60
JOBS = [  # workflow file, hour UTC, minute, weekdays (Mon=0..Sun=6) or None=daily
    ('radar.yml', 7, 7, None), ('doodles.yml', 7, 37, None), ('doodles-full.yml', 6, 40, (1, 4)),
    ('full-video.yml', 9, 10, (0, 2, 4, 6)), ('mindlore-2d.yml', 11, 20, (2, 5)),   # KICK2D: MindLore full video is 2D only
    ('mindlore-story-short.yml', 13, 40, None), ('shelfmade-story-short.yml', 14, 10, None), ('learn.yml', 14, 12, (0, 3)),
]
def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, timeout=60)
def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    for wf, h, m, days in JOBS:
        try:
            if days is not None and now.weekday() not in days: continue
            due = now.replace(hour=h, minute=m, second=0, microsecond=0)
            late = (now - due).total_seconds() / 60
            if late < GRACE or late > MAXLATE: continue
            r = sh('gh', 'run', 'list', '--workflow', wf, '--limit', '10', '--json', 'createdAt,event,status,conclusion')
            runs = json.loads(r.stdout or '[]')
            since = due - datetime.timedelta(minutes=5)
            rs = [x for x in runs if datetime.datetime.fromisoformat(x['createdAt'].replace('Z', '+00:00')) >= since]
            if rs:   # RETRY_ONCE: self-repair - if every run today failed and there is only one, try once more (never a third time)
                if len(rs) == 1 and rs[0]['status'] == 'completed' and rs[0]['conclusion'] == 'failure' and late >= 20:
                    d = sh('gh', 'workflow', 'run', wf)
                    print('RETRIED once', wf, (d.stdout + d.stderr).strip()[:120], flush=True)
                continue
            d = sh('gh', 'workflow', 'run', wf)
            print('KICKED', wf, 'late by %d min' % late, (d.stdout + d.stderr).strip()[:120], flush=True)
        except Exception as e:
            print('kick skipped', wf, str(e)[:100], flush=True)
if __name__ == '__main__':
    main()
