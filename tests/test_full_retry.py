import sys,tempfile,unittest,sqlite3,concurrent.futures
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_jobs as f
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.patches=[patch.object(f,'DB',self.root/'state.db'),patch.object(f,'ROOT',self.root/'media'),patch.object(f,'script_for',return_value={'sections':[{'narration':'A meaningful supported idea. '*40}]}),patch('local_voice.available',return_value=True)]
  for p in self.patches:p.start()
  with f.connect() as c:
   c.execute("INSERT INTO full_jobs(id,book,state,version,attempts) VALUES('job','1497','failed','cinematic-default-v1',1)")
   c.execute("INSERT INTO full_generation_attempts(job) VALUES('job')")
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_failed_job_can_use_second_attempt_without_reset(self):
  row=f.retry('job');self.assertEqual(row['state'],'queued');self.assertEqual(row['attempts'],1)
  with f.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM full_generation_attempts').fetchone()[0],1)
 def test_two_attempts_stop_further_recovery(self):
  with f.connect() as c:c.execute("INSERT INTO full_generation_attempts(job) VALUES('job')")
  with self.assertRaisesRegex(ValueError,'Both'):f.retry('job')
 def test_success_cannot_be_retried_or_replaced(self):
  with f.connect() as c:c.execute("UPDATE full_jobs SET state='ready' WHERE id='job'")
  with self.assertRaises(ValueError):f.retry('job')
  with self.assertRaises(ValueError):f.enqueue('132')
 def test_no_second_book_during_failed_book_day(self):
  with self.assertRaisesRegex(ValueError,'Chicago'):f.enqueue('132')
 def test_active_or_unverifiable_worker_blocks_retry(self):
  with f.connect() as c:c.execute("UPDATE full_jobs SET worker_pid=123 WHERE id='job'")
  with patch.object(f.os,'kill'):
   with self.assertRaisesRegex(ValueError,'running'):f.retry('job')
  with patch.object(f.os,'kill',side_effect=PermissionError):
   with self.assertRaisesRegex(ValueError,'verified'):f.retry('job')
 def test_different_daily_reservation_cannot_be_overwritten(self):
  import datetime
  from zoneinfo import ZoneInfo
  day=datetime.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
  with f.connect() as c:
   c.execute('CREATE TABLE full_daily_generation(day TEXT PRIMARY KEY,book TEXT)');c.execute('INSERT INTO full_daily_generation VALUES (?,?)',(day,'205'))
  with self.assertRaisesRegex(ValueError,'reservation'):f.retry('job')
  with f.connect() as c:self.assertEqual(c.execute('SELECT book FROM full_daily_generation').fetchone()[0],'205')
 def test_another_full_job_prevents_retry(self):
  with f.connect() as c:c.execute("INSERT INTO full_jobs(id,book,state) VALUES('other','205','running')")
  with self.assertRaises(ValueError):f.retry('job')
 def test_double_click_queues_only_once(self):
  def enqueue():
   try:f.retry('job');return True
   except ValueError:return False
  with concurrent.futures.ThreadPoolExecutor(2) as pool:result=list(pool.map(lambda _:enqueue(),range(2)))
  self.assertEqual(sum(result),1)
 def test_worker_hard_limit_applies_even_to_a_queued_row(self):
  with f.connect() as c:
   c.execute("UPDATE full_jobs SET state='queued' WHERE id='job'");c.execute("INSERT INTO full_generation_attempts(job) VALUES('job')")
  with patch.object(f.subprocess,'Popen') as process:self.assertFalse(f.work_once());process.assert_not_called()
 def test_invalid_script_does_not_queue(self):
  with patch.object(f,'script_for',side_effect=ValueError('Review source')):
   with self.assertRaises(ValueError):f.retry('job')
  with f.connect() as c:self.assertEqual(c.execute("SELECT state FROM full_jobs WHERE id='job'").fetchone()[0],'failed')
 def test_free_search_requests_more_candidates_per_call(self):
  import footage_director as footage,io,urllib.parse,json
  with patch.object(footage,'DB',self.root/'footage.db'),patch.object(footage,'CACHE',self.root/'cache'),patch.object(footage,'key',return_value='private'),patch.object(footage.urllib.request,'urlopen',return_value=io.StringIO(json.dumps({'videos':[]}))) as request:
   footage.search('learning detail',1)
   self.assertEqual(urllib.parse.urlparse(request.call_args.args[0].full_url).path,'/videos/search')
   self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(request.call_args.args[0].full_url).query)['per_page'],['80'])
   with footage.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM requests').fetchone()[0],1)
 def test_missing_voice_blocks_recovery(self):
  with patch('local_voice.available',return_value=False):
   with self.assertRaises(ValueError):f.retry('job')
if __name__=='__main__':unittest.main()
