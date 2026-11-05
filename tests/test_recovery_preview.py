import copy
import datetime
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import recovery_preview as preview


class RecoveryPreviewTests(unittest.TestCase):
    def test_one_temporary_provider_failure_is_only_a_proposal(self):
        result = self.assess()
        self.assertTrue(result['eligible_under_proposal'])
        self.assertFalse(result['will_run'])

    def assess(self, **overrides):
        args = dict(job={'state': 'failed', 'attempts': 1, 'worker_pid': None},
                    same_day=True, attempt_count=1,
                    failure={'temporary': True, 'code': 'provider_unavailable'})
        args.update(overrides)
        before = copy.deepcopy(args)
        result = preview.assess(**args)
        self.assertEqual(args, before)
        return result

    def test_all_protected_conditions_block(self):
        cases = [dict(same_day=False), dict(attempt_count=2), dict(has_media=True),
                 dict(has_publication=True), dict(slot_valid=False),
                 dict(job={'state': 'running', 'attempts': 1}),
                 dict(job={'state': 'failed', 'attempts': 1, 'worker_pid': 123}),
                 dict(job={'state': 'failed', 'attempts': 2})]
        for case in cases:
            with self.subTest(case=case):
                self.assertFalse(self.assess(**case)['eligible_under_proposal'])

    def test_quality_meaning_quota_and_unknown_failures_block(self):
        for code in ('footage_shortage', 'quality', 'auth', '429', None):
            self.assertFalse(self.assess(failure={'temporary': True, 'code': code})['eligible_under_proposal'])
        self.assertFalse(self.assess(failure={})['eligible_under_proposal'])

    def test_snapshot_is_read_only_and_a_fourth_slot_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            db = base/'decisions.sqlite3'
            with sqlite3.connect(db) as c:
                c.executescript('''CREATE TABLE short_daily_slots(day,slot,book,job);
                CREATE TABLE jobs(id,state,attempts,worker_pid);
                CREATE TABLE attempts(job,started);
                CREATE TABLE publications(item);
                CREATE TABLE platform_posts(item);''')
                for slot in range(1, 4):
                    job = f'{slot:032x}'
                    c.execute('INSERT INTO short_daily_slots VALUES (?,?,?,?)', ('2026-10-19', slot, str(slot), job))
                    c.execute('INSERT INTO jobs VALUES (?,?,?,?)', (job, 'failed', 1, None))
                    c.execute('INSERT INTO attempts VALUES (?,?)', (job, '2026-10-19 15:00:00'))
                    folder = base/'generated'/job/'1'
                    folder.mkdir(parents=True)
                    (folder/'failure.json').write_text(json.dumps({'temporary': True, 'code': 'provider_unavailable'}))
            now = datetime.datetime(2026, 10, 19, 18, tzinfo=datetime.timezone.utc)
            original = db.read_bytes()
            report = preview.snapshot(base, now)
            self.assertEqual(report['eligible_count'], 3)
            self.assertEqual(db.read_bytes(), original)
            self.assertFalse(report['automatic_recovery_enabled'])
            with sqlite3.connect(db) as c:
                c.execute('INSERT INTO platform_posts VALUES (?)', ('job-'+f'{1:032x}',))
            self.assertEqual(preview.snapshot(base, now)['eligible_count'], 2)
            with sqlite3.connect(db) as c:
                c.execute('INSERT INTO short_daily_slots VALUES (?,?,?,?)', ('2026-10-19', 4, '4', f'{4:032x}'))
            self.assertEqual(preview.snapshot(base, now)['eligible_count'], 0)


if __name__ == '__main__':
    unittest.main()
