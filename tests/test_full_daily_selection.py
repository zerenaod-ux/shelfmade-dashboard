"""A fresh daily draft replaces untouched backlog, never owner/publishing work."""
import datetime,hashlib,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
import daily_plan

NOW=datetime.datetime(2026,10,21,15,tzinfo=ZoneInfo('America/Chicago'))

def item(id,status='review'):
 return dict(id=id,title=id,content_type='full',ready=True,status=status,quality=dict(duration=390,can_approve=True))

class Selection(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.p=patch.object(daily_plan,'DB',Path(self.tmp.name)/'state.sqlite');self.p.start();self.addCleanup(self.p.stop)
  self.fresh='long-'+hashlib.sha256(b'fresh-job-attempt-2').hexdigest()[:24]
  with daily_plan.connection() as db:
   db.execute('CREATE TABLE full_jobs(id TEXT,book TEXT,state TEXT,attempts INTEGER,updated TEXT)')
   db.execute("INSERT INTO full_jobs VALUES('fresh-job','book','ready',2,'2026-10-21 20:00:00')")
   db.execute('CREATE TABLE full_daily_generation(day TEXT,book TEXT)')
   db.execute("INSERT INTO full_daily_generation VALUES('2026-10-21','book')")
  self.assertEqual(daily_plan.full_pick([item('backlog')],[],NOW)['id'],'backlog')
 def pick(self,posts=None,status='review'):
  return daily_plan.full_pick([item('backlog',status),item(self.fresh)],posts or [],NOW)['id']
 def test_fresh_replaces_untouched_backlog(self):self.assertEqual(self.pick(),self.fresh)
 def test_approved_stays_pinned(self):self.assertEqual(self.pick(status='approved'),'backlog')
 def test_each_publishing_preparation_stays_pinned(self):
  for state in ['awaiting_publisher','uploading','needs_reconciliation','published','failed']:
   with self.subTest(state=state):self.assertEqual(self.pick([dict(item='backlog',state=state,url='receipt' if state=='published' else None)]),'backlog')
 def test_yesterday_reservation_does_not_replace(self):
  with daily_plan.connection() as db:db.execute("UPDATE full_daily_generation SET day='2026-10-20'")
  self.assertEqual(self.pick(),'backlog')
 def test_unfinished_job_does_not_replace(self):
  with daily_plan.connection() as db:db.execute("UPDATE full_jobs SET state='running'")
  self.assertEqual(self.pick(),'backlog')
 def test_missing_backlog_can_be_repaired(self):
  self.assertEqual(daily_plan.full_pick([item(self.fresh)],[],NOW)['id'],self.fresh)
 def test_daily_draft_visible_even_when_older_selection_is_published(self):
  result=daily_plan.full_pick([item('backlog','approved'),item(self.fresh)], [dict(item='backlog',state='published',url='receipt')],NOW)
  self.assertEqual(result['id'],'backlog');self.assertEqual(result['daily_draft_id'],self.fresh)
 def test_daily_draft_remains_visible_after_its_own_publication(self):
  result=daily_plan.full_pick([item('backlog','approved'),item(self.fresh,'approved')], [dict(item=self.fresh,state='published',url='receipt')],NOW)
  self.assertEqual(result['daily_draft_id'],self.fresh)
 def test_selection_never_changes_decisions_or_receipts(self):
  self.pick()
  with daily_plan.connection() as db:
   tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  self.assertNotIn('decisions',tables);self.assertNotIn('publications',tables)
