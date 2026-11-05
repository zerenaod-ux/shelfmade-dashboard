import json,sqlite3,tempfile,unittest,sys,datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import jobs,source_cache,daily_plan

class SourceRecovery(unittest.TestCase):
 def test_reuses_only_a_ready_package_for_the_same_gutenberg_book(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);db=root/'state.sqlite';media=root/'generated';folder=media/'completed'/'1';folder.mkdir(parents=True)
   (folder/'source.txt').write_text('A verified original public-domain book. '*100)
   (folder/'content-review.json').write_text(json.dumps({'source_url':'https://www.gutenberg.org/ebooks/205'}))
   with sqlite3.connect(db) as c:
    c.execute('CREATE TABLE jobs(id TEXT,book TEXT,state TEXT,edition INTEGER,attempts INTEGER,created TEXT)')
    c.execute("INSERT INTO jobs VALUES ('completed','205','ready',1,1,'2026-01-01')")
   self.assertIsNotNone(source_cache.read('205',db,media))
   self.assertIsNone(source_cache.read('132',db,media))

 def test_pre_source_failures_do_not_consume_render_capacity(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(jobs,'DB',Path(temp)/'state.sqlite'):
   with jobs.connect() as c:
    for index in range(3):
     c.execute("INSERT INTO jobs(id,book,state,attempts) VALUES (?,?,'failed',1)",(f'job-{index}',str(index)))
     c.execute('INSERT INTO attempts(job,source_ready) VALUES (?,0)',(f'job-{index}',))
    c.execute("INSERT INTO attempts(job,source_ready) VALUES ('rendered',1)")
    self.assertEqual(jobs.attempts_used(c,'2000-01-01','2100-01-01'),1)
   self.assertTrue(jobs.pre_source_retryable({'id':'job-0','attempts':1}))
   self.assertFalse(jobs.pre_source_retryable({'id':'job-0','attempts':2}))

 def test_legacy_attempts_without_saved_source_are_reclassified_without_deleting_history(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);db=root/'state.sqlite';media=root/'generated'
   with sqlite3.connect(db) as c:
    c.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,book TEXT,state TEXT,attempts INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE attempts(job TEXT,started TEXT DEFAULT CURRENT_TIMESTAMP)')
    for index in range(3):
     c.execute("INSERT INTO jobs(id,book,state,attempts) VALUES (?,?,'failed',1)",(f'job-{index}',str(index)))
     c.execute('INSERT INTO attempts(job) VALUES (?)',(f'job-{index}',))
   with patch.object(jobs,'DB',db),patch.object(jobs,'ROOT',media),patch.object(jobs,'BOOKS',[]):
    with jobs.connect() as c:
     self.assertEqual(c.execute('SELECT count(*) FROM attempts').fetchone()[0],3)
     self.assertEqual(jobs.attempts_used(c,'2000-01-01','2100-01-01'),0)

 def test_reserved_failed_slot_retries_once_after_a_pre_source_failure(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);self_rows=[{'id':'failed','book':'0','state':'failed','attempts':1,'edition':2}]
   with patch.object(daily_plan,'DB',root/'state.sqlite'),patch.object(daily_plan,'history',return_value={}),patch.object(daily_plan.jobs,'BOOKS',[{'id':'0','title':'Book 0'}]),patch.object(daily_plan.jobs,'list_jobs',side_effect=lambda:self_rows),patch.object(daily_plan.jobs,'pre_source_retryable',return_value=True):
    with daily_plan.connection() as c:
     daily_plan.short_slots(c);c.execute("INSERT INTO short_daily_slots(day,slot,book,job) VALUES ('2026-10-26',1,'0','failed')")
    def retry(book,retry=False):
     self.assertEqual(book,'0');self.assertTrue(retry)
     self_rows[0]['state']='queued'
     return self_rows[0]
    with patch.object(daily_plan.jobs,'enqueue',side_effect=retry) as enqueue:
     daily_plan.queue_fresh([],[],datetime.datetime(2026,10,26,10,tzinfo=ZoneInfo('America/Chicago')))
    self.assertEqual(enqueue.call_count,1)

if __name__=='__main__':unittest.main()
