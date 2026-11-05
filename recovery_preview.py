"""Read-only preview of the proposed same-day Short recovery policy.

Not imported by the scheduler. An eligible result grants no execution capacity.
No provider calls, database migrations, queue updates or publication operations.
"""
import datetime
import json
import re
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
ZONE = ZoneInfo('America/Chicago')


def assess(job, *, same_day, attempt_count, failure, has_media=False,
           has_publication=False, slot_valid=True):
    """Conservative, pure decision: uncertain evidence always requires attention."""
    reason = None
    if not slot_valid:
        reason = 'No unique daily Short slot (1–3)'
    elif not same_day:
        reason = 'Earlier-day work needs separate owner recovery'
    elif has_media or job.get('state') == 'ready':
        reason = 'Completed media is protected'
    elif has_publication:
        reason = 'Existing publishing preparation or receipt is protected'
    elif job.get('worker_pid') is not None:
        reason = 'Previous worker ownership requires inspection'
    elif job.get('state') not in ('failed', 'retry_wait'):
        reason = 'Job is not stopped with a classified failure'
    elif attempt_count != 1 or job.get('attempts') != 1:
        reason = 'Only a first failure could receive one proposed recovery'
    elif failure.get('temporary') is not True:
        reason = 'Failure is not confirmed temporary'
    elif failure.get('code') != 'provider_unavailable':
        reason = 'Footage meaning, quality, quota or unclassified failure needs attention'
    return {'eligible_under_proposal': reason is None,
            'reason': reason or 'One temporary provider recovery could be permitted',
            'will_run': False}


def snapshot(base=BASE, now=None):
    base = Path(base).resolve()
    now = (now or datetime.datetime.now(ZONE)).astimezone(ZONE)
    day = now.date().isoformat()
    report = {'day': day, 'timezone': str(ZONE), 'checked_at': now.isoformat(),
              'mode': 'read-only proposal preview', 'automatic_recovery_enabled': False,
              'policy': {'fresh_slots': 3, 'proposed_recoveries_per_slot': 1,
                         'proposed_maximum_executions': 6}, 'slots': []}
    # SQLite read-only connection and one consistent transaction, including receipts.
    with sqlite3.connect((base/'decisions.sqlite3').as_uri()+'?mode=ro', uri=True) as c:
        c.row_factory = sqlite3.Row
        c.execute('BEGIN')
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'short_daily_slots', 'jobs', 'attempts', 'publications', 'platform_posts'}
        if not required <= tables:
            return dict(report, available=False, message='Required local evidence is unavailable')
        slots = [dict(r) for r in c.execute(
            'SELECT * FROM short_daily_slots WHERE day=? ORDER BY slot', (day,))]
        jobs = {r['id']: dict(r) for r in c.execute('SELECT * FROM jobs')}
        for slot in slots:
            job = jobs.get(slot['job'])
            item = {'slot': slot['slot'], 'job': slot['job']}
            if job is None or not re.fullmatch(r'[a-f0-9]{32}', job['id']):
                item.update(eligible_under_proposal=False, reason='Job evidence is missing or invalid', will_run=False)
            else:
                folder = base/'generated'/job['id']/str(job['attempts'])
                failure = {}
                # Never follow an out-of-root folder to read package evidence.
                safe = folder.resolve().is_relative_to(base/'generated')
                if safe:
                    try:
                        value = json.loads((folder/'failure.json').read_text())
                        if isinstance(value, dict):
                            failure = value
                    except (OSError, ValueError):
                        pass
                count = c.execute('SELECT count(*) FROM attempts WHERE job=?', (job['id'],)).fetchone()[0]
                publication = any(c.execute('SELECT 1 FROM '+table+' WHERE item=? LIMIT 1',
                                  ('job-'+job['id'],)).fetchone() is not None
                                  for table in ('publications', 'platform_posts'))
                # All attempts must belong to this Chicago day, not merely the reservation.
                timestamps = [r[0] for r in c.execute('SELECT started FROM attempts WHERE job=?', (job['id'],))]
                try:
                    same_day = bool(timestamps) and all(datetime.datetime.fromisoformat(t)
                        .replace(tzinfo=datetime.timezone.utc).astimezone(ZONE).date().isoformat() == day
                        for t in timestamps)
                except (ValueError, TypeError):
                    same_day = False
                item.update(assess(job, same_day=same_day, attempt_count=count, failure=failure,
                    has_media=not safe or (folder/'final.mp4').exists(), has_publication=publication,
                    slot_valid=slot['slot'] in (1, 2, 3) and len(slots) <= 3
                    and sum(s['job'] == slot['job'] for s in slots) == 1))
            report['slots'].append(item)
    report['available'] = True
    report['eligible_count'] = sum(s['eligible_under_proposal'] for s in report['slots'])
    return report


if __name__ == '__main__':
    print(json.dumps(snapshot(), indent=2))
