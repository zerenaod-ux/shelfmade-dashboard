"""SELF-KICK: GitHub often delays or drops scheduled runs (seen: 2h25m late, whole hours skipped). review-publish runs every 30 min and does fire, so it calls this.
For each daily job: if its scheduled time + GRACE has passed today and NO run of that workflow exists since then (any event, any result), start it with workflow_dispatch.
Never retries failures (a failed run still counts as 'ran'). Fails soft. Needs GH_TOKEN and permissions: actions: write."""
import json, subprocess, datetime, sys, time, random
GRACE = 100   # minutes: GitHub delays of ~2.5 h were observed; after that we start it ourselves
MAXLATE = 14 * 60
JOBS = [  # workflow file, hour UTC, minute, weekdays (Mon=0..Sun=6) or None=daily
    ('radar.yml', 7, 7, None), ('doodles.yml', 7, 37, None), ('doodles-full.yml', 6, 40, (1, 4)),
    ('full-video.yml', 9, 10, (0, 2, 4, 6)), ('mindlore-2d.yml', 11, 20, (2, 5)),   # KICK2D: MindLore full video is 2D only
    ('analytics.yml', 13, 30, None), ('ml-scripts.yml', 7, 30, None), ('ml-scripts.yml', 13, 30, None), ('ml-scripts.yml', 19, 30, None), ('sm-scripts.yml', 8, 50, None), ('sm-scripts.yml', 14, 50, None), ('sm-scripts.yml', 20, 50, None), ('first-comment.yml', 16, 17, None), ('daily-summary.yml', 14, 25, None), ('mindlore-story-short.yml', 13, 40, None), ('shelfmade-story-short.yml', 14, 10, None), ('learn.yml', 14, 12, (0, 3)),
]
def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, timeout=60)
def start(wf, since, why):
    """NO_DOUBLE_START: four jobs run this kick at the same moment, and twice they all started the same workflow (doodles 2026-11-13 10:10, one copy got cancelled).
    So wait a random moment, look again, and only start it if nobody else has in the meantime."""
    time.sleep(random.uniform(5, 50))
    r = sh('gh', 'run', 'list', '--workflow', wf, '--limit', '10', '--json', 'createdAt,status')
    new = [x for x in json.loads(r.stdout or '[]') if datetime.datetime.fromisoformat(x['createdAt'].replace('Z', '+00:00')) >= since and x['status'] in ('queued', 'in_progress', 'waiting', 'pending', 'requested')]
    if new and why != 'stuck': print('skip', wf, '- another kick already started it', flush=True); return
    if why == 'stuck' and [x for x in new if (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(x['createdAt'].replace('Z', '+00:00'))).total_seconds() < 600]:
        print('skip', wf, '- a fresh run was just started', flush=True); return
    d = sh('gh', 'workflow', 'run', wf); print(why.upper(), wf, (d.stdout + d.stderr).strip()[:120], flush=True)

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
            def age(x): return (now - datetime.datetime.fromisoformat(x['createdAt'].replace('Z', '+00:00'))).total_seconds() / 60
            stuck = [x for x in rs if x['status'] == 'queued' and age(x) > 75]   # STUCK_QUEUE: GitHub sometimes leaves a run 'queued' for hours (seen 2026-11-11); start a fresh one
            alive = [x for x in rs if x['status'] == 'in_progress' or (x['status'] == 'queued' and age(x) <= 75) or x.get('conclusion') == 'success']
            if stuck and not alive:
                start(wf, since, 'stuck'); continue
            if rs:   # RETRY_ONCE: self-repair - if every run today failed and there is only one, try once more (never a third time)
                if len(rs) == 1 and rs[0]['status'] == 'completed' and rs[0]['conclusion'] == 'failure' and late >= 20:
                    start(wf, since, 'retried once')
                continue
            start(wf, since, 'kicked (late by %d min)' % late)
        except Exception as e:
            print('kick skipped', wf, str(e)[:100], flush=True)
if __name__ == '__main__':
    main()
