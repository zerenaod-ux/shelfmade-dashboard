import unittest,sqlite3,tempfile,json,urllib.error
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import generation_recovery as r
class Recovery(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT,error TEXT,updated TEXT)');r.migrate(self.c,'jobs')
  self.c.execute("INSERT INTO jobs(id,state) VALUES ('one','running')")
 def tearDown(self):self.c.close();self.tmp.cleanup()
 def row(self):return self.c.execute('SELECT * FROM jobs').fetchone()
 def test_backoff_survives_repeated_schema_setup(self):
  (self.folder/'failure.json').write_text(json.dumps({'temporary':True}))
  r.failure(self.c,'jobs',self.row(),self.folder,'failed',100)
  r.migrate(self.c,'jobs');self.assertEqual(self.row()['retry_at'],160)
  r.promote(self.c,'jobs',1,159);self.assertEqual(self.row()['state'],'retry_wait')
  r.promote(self.c,'jobs',0,200);self.assertEqual(self.row()['state'],'retry_wait')
  r.promote(self.c,'jobs',1,200);self.assertEqual(self.row()['state'],'queued')
  r.failure(self.c,'jobs',self.row(),self.folder,'failed',200);self.assertEqual(self.row()['retry_at'],500)
  r.failure(self.c,'jobs',self.row(),self.folder,'failed',501);self.assertEqual(self.row()['state'],'failed')
 def test_unclassified_quality_and_quota_never_retry(self):
  for text in ('quality failed','quota reached','voice unavailable'):
   r.failure(self.c,'jobs',self.row(),self.folder,text,100);self.assertEqual(self.row()['state'],'failed')
  for status in (401,403,404,429):self.assertFalse(r.transient(urllib.error.HTTPError('https://example.invalid',status,'',{},None)))
  self.assertTrue(r.transient(urllib.error.HTTPError('https://example.invalid',503,'',{},None)))
 def test_restart_does_not_duplicate_or_resume_unknown_process(self):
  self.c.execute('UPDATE jobs SET worker_pid=123')
  r.interrupted(self.c,'jobs');r.promote(self.c,'jobs',3,999)
  self.assertEqual(self.row()['state'],'failed');self.assertEqual(self.row()['worker_pid'],123)
  self.assertEqual(self.c.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
class WorkerIntegration(unittest.TestCase):
 def test_full_retry_preserves_previous_folder_and_consumes_capacity(self):
  import full_jobs
  from unittest.mock import patch
  class Process:
   pid=987654
   def wait(self,timeout):return 0
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   with patch.object(full_jobs,'DB',root/'state.sqlite'),patch.object(full_jobs,'ROOT',root/'media'),patch.object(full_jobs.subprocess,'Popen',return_value=Process()) as launch:
    with full_jobs.connect() as c:
     c.execute("INSERT INTO full_jobs(id,book,state,created,updated,attempts,retry_count,retry_at) VALUES ('job','book','retry_wait','2000-01-01','2000-01-01',1,1,0)")
    old=root/'media/job';old.mkdir(parents=True);(old/'original.txt').write_text('preserve')
    self.assertTrue(full_jobs.work_once())
    self.assertEqual((old/'original.txt').read_text(),'preserve')
    self.assertTrue(str(launch.call_args.args[0][-1]).endswith('job-attempt-2'))
    with full_jobs.connect() as c:
     self.assertEqual(c.execute('SELECT count(*) FROM full_generation_attempts').fetchone()[0],1)
    self.assertFalse(full_jobs.work_once());self.assertEqual(launch.call_count,1)
 def test_short_recovery_does_not_bypass_daily_cap(self):
  import jobs
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as temp,patch.object(jobs,'DB',Path(temp)/'state.sqlite'),patch.object(jobs.subprocess,'Popen') as launch:
   with jobs.connect() as c:
    c.execute("INSERT INTO jobs(id,book,state,retry_at) VALUES ('job','book','retry_wait',0)")
    for i in range(3):c.execute("INSERT INTO attempts(job) VALUES ('other')")
   self.assertFalse(jobs.work_once());launch.assert_not_called()
   with jobs.connect() as c:self.assertEqual(c.execute("SELECT state FROM jobs").fetchone()[0],'retry_wait')
if __name__=='__main__':unittest.main()
