import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import full_jobs as f
class FullProgress(unittest.TestCase):
 def test_active_owner_recovery_shows_its_folder_not_previous_failed_attempt(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(f,'DB',Path(temp)/'db.sqlite3'),patch.object(f,'ROOT',Path(temp)/'media'):
   folder=f.ROOT/'job-attempt-4';folder.mkdir(parents=True);(folder/'production-progress.json').write_text(json.dumps({'stage':'subtitles','message':'Adding animated subtitles'}))
   with f.connect() as c:
    c.execute("insert into full_jobs(id,book,state,attempts) values('job','2274','recovering',2)")
    c.execute('create table owner_generation_recoveries(kind,job,folder,state)');c.execute("insert into owner_generation_recoveries values('full','job',?,'running')",(str(folder),))
   self.assertEqual(f.list_jobs()[0]['progress']['stage'],'subtitles')
 def test_progress_cannot_read_outside_full_media_root(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(f,'DB',Path(temp)/'db.sqlite3'),patch.object(f,'ROOT',Path(temp)/'media'):
   folder=Path(temp)/'outside/job-attempt-4';folder.mkdir(parents=True);(folder/'production-progress.json').write_text('{"private":"do not read"}')
   with f.connect() as c:
    c.execute("insert into full_jobs(id,book,state,attempts) values('job','2274','recovering',2)")
    c.execute('create table owner_generation_recoveries(kind,job,folder,state)');c.execute("insert into owner_generation_recoveries values('full','job',?,'running')",(str(folder),))
   self.assertIsNone(f.list_jobs()[0]['progress'])
