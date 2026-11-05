import unittest,tempfile,sqlite3,json
from pathlib import Path
from unittest.mock import patch
import owner_recovery as r
class OwnerRecovery(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.patches=[patch.object(r,'DB',self.root/'db.sqlite3'),patch.object(r.jobs,'ROOT',self.root/'generated'),patch.object(r.full_jobs,'ROOT',self.root/'full'),patch.object(r.jobs,'attempt_window',return_value=('2026-10-19 05:00:00','2026-10-20 05:00:00')),patch.object(r,'day',return_value='2026-10-19')]
  for p in self.patches:p.start()
  with sqlite3.connect(r.DB) as c:
   for table in ['jobs','full_jobs']:
    c.execute('create table '+table+'(id TEXT,book TEXT,state TEXT,attempts INTEGER,worker_pid INTEGER,created TEXT,updated TEXT,retry_at REAL,error TEXT)')
    c.execute('insert into '+table+' values(?,?,?,?,?,?,?,?,?)',('abc','26716','failed',1,None,'2026-10-19 14:00:00','2026-10-19 14:01:00',None,'original failure'))
   c.execute('create table attempts(job,started)');c.execute("insert into attempts values('abc','2026-10-19 14:00:00')")
   c.execute('create table platform_posts(item,state,url)')
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_authorization_archives_failure_without_resetting_normal_attempts(self):
  out=r.authorize('short','abc','Owner requests one generation recovery today.')
  self.assertEqual(Path(out),r.jobs.ROOT/'abc/2')
  with r.connect() as c:
   rec=c.execute('select * from owner_generation_recoveries').fetchone();self.assertEqual(json.loads(rec['original_record'])['error'],'original failure')
   self.assertEqual(c.execute('select count(*) from attempts').fetchone()[0],1);self.assertEqual(c.execute('select state from jobs').fetchone()[0],'failed')
  self.assertFalse(Path(out).exists())
 def test_same_authorization_cannot_repeat(self):
  r.authorize('short','abc','Owner requests one generation recovery today.')
  with self.assertRaisesRegex(ValueError,'already'):r.authorize('short','abc','Owner requests another generation recovery today.')
 def test_old_day_and_completed_jobs_are_not_recovered(self):
  with sqlite3.connect(r.DB) as c:c.execute("update jobs set created='2026-10-18 14:00:00'")
  with self.assertRaisesRegex(ValueError,'today'):r.authorize('short','abc','Owner requests generation recovery.')
  with sqlite3.connect(r.DB) as c:c.execute("update jobs set state='ready',created='2026-10-19 14:00:00'")
  with self.assertRaises(ValueError):r.authorize('short','abc','Owner requests generation recovery.')
 def test_active_worker_is_blocked(self):
  with patch.object(r,'alive',return_value=True):
   with self.assertRaisesRegex(ValueError,'still running'):r.authorize('short','abc','Owner requests generation recovery.')
 def test_existing_complete_package_is_preserved(self):
  source=r.jobs.ROOT/'abc/1';source.mkdir(parents=True);(source/'POST_THIS.txt').write_text('completed')
  with self.assertRaisesRegex(ValueError,'completed'):r.authorize('short','abc','Owner requests generation recovery.')
 def test_successful_and_uncertain_posts_are_never_recovered(self):
  for state,url in [('published','https://example.com/post'),('submitting',None)]:
   with sqlite3.connect(r.DB) as c:c.execute('delete from platform_posts');c.execute('insert into platform_posts values(?,?,?)',('job-abc',state,url))
   with self.assertRaisesRegex(ValueError,'publication'):r.authorize('short','abc','Owner requests generation recovery.')
 def test_changed_job_blocks_execution_before_child(self):
  r.authorize('short','abc','Owner requests generation recovery today.')
  with sqlite3.connect(r.DB) as c:c.execute("update jobs set error='changed'")
  from contextlib import contextmanager
  @contextmanager
  def lock():yield True
  with patch.object(r.media_runtime,'require_ready'),patch.object(r.footage_budget,'available',return_value=True),patch.object(r.render_capacity,'claim',lock),patch.object(r.subprocess,'Popen') as child:
   with self.assertRaisesRegex(ValueError,'changed'):r.run_one('short','abc')
   child.assert_not_called()
 def test_explicit_request_and_valid_format_required(self):
  with self.assertRaises(ValueError):r.authorize('other','abc','Owner requests recovery today.')
  with self.assertRaises(ValueError):r.authorize('short','abc','')
if __name__=='__main__':unittest.main()

class RepairContinuation(unittest.TestCase):
 setUp=OwnerRecovery.setUp
 tearDown=OwnerRecovery.tearDown
 def test_stopped_recovery_is_archived_before_one_continuation(self):
  r.authorize('full','abc','Owner requests one generation recovery today.')
  old=self.root/'full/abc-attempt-2';old.mkdir(parents=True);(old/'worker.log').write_text('original stopped recovery')
  with r.connect() as c:c.execute("update owner_generation_recoveries set state='failed',error='pronunciation missing'")
  new=r.continue_after_repair('full','abc','Owner requests continuation after the proven defect is repaired.')
  self.assertEqual(Path(new).name,'abc-attempt-3');self.assertEqual((old/'worker.log').read_text(),'original stopped recovery')
  with r.connect() as c:
   saved=json.loads(c.execute('select previous_record from owner_recovery_continuations').fetchone()[0]);self.assertEqual(saved['error'],'pronunciation missing')
   self.assertEqual(c.execute('select count(*) from attempts').fetchone()[0],1)
   c.execute("update owner_generation_recoveries set state='failed'")
  with self.assertRaisesRegex(ValueError,'already exists'):r.continue_after_repair('full','abc','Owner requests yet another continuation.')
 def test_no_continuation_for_active_or_ready_recovery(self):
  r.authorize('full','abc','Owner requests one generation recovery today.')
  with self.assertRaisesRegex(ValueError,'No stopped'):r.continue_after_repair('full','abc','Owner requests continuation after repair.')
