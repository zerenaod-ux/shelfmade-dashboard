import unittest,tempfile,json,sqlite3,datetime,sys
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maintenance as m,full_jobs,quality,jobs
class MaintenanceTests(unittest.TestCase):
 def test_backup_and_tamper_detection(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'BASE',Path(d)):
   root=Path(d)
   with sqlite3.connect(root/'decisions.sqlite3') as c:c.execute('create table example(value)');c.execute("insert into example values ('preserved')")
   snapshot=Path(m.backup()['snapshot']);self.assertTrue(m.verify_snapshot(snapshot)['verified']);self.assertEqual(snapshot.stat().st_mode&0o777,0o700)
   with sqlite3.connect(snapshot/'decisions.sqlite3') as c:self.assertEqual(c.execute('select value from example').fetchone()[0],'preserved')
   (snapshot/'decisions.sqlite3').write_bytes(b'changed');self.assertFalse(m.verify_snapshot(snapshot)['verified'])
 def test_chicago_day_and_dst(self):
  zone=ZoneInfo('America/Chicago')
  self.assertEqual(jobs.attempt_window(datetime.datetime(2026,10,15,23,tzinfo=zone)),('2026-10-15 05:00:00','2026-10-16 05:00:00'))
  self.assertEqual(jobs.attempt_window(datetime.datetime(2026,3,8,12,tzinfo=zone)),('2026-03-08 06:00:00','2026-03-09 05:00:00'))
 def test_full_day_cap_across_utc_midnight(self):
  with tempfile.TemporaryDirectory() as d,patch.object(full_jobs,'DB',Path(d)/'db.sqlite'),patch.object(full_jobs,'script_for',return_value={'sections':[{'narration':'A meaningful idea. '*50}]}),patch('local_voice.available',return_value=True),patch.object(full_jobs,'attempt_window',return_value=('2026-10-15 05:00:00','2026-10-16 05:00:00')):
   with full_jobs.connect() as c:c.execute("insert into full_jobs(id,book,state,created,version) values ('old','205','ready','2026-10-15 23:00:00','cinematic-default-v1')")
   with self.assertRaisesRegex(ValueError,'Chicago'):full_jobs.enqueue('132')
 def test_corrupt_optional_quality_cache_regenerates(self):
  with tempfile.TemporaryDirectory() as d,patch.object(quality,'CACHE',Path(d)/'cache'):
   p=Path(d);(p/'v.mp4').write_bytes(b'video');(p/'POST_THIS.txt').write_text('Caption')
   class Reply:stdout=json.dumps({'format':{'duration':'20'},'streams':[{'codec_type':'video','width':1080,'height':1920},{'codec_type':'audio'}]})
   with patch.object(quality.subprocess,'run',return_value=Reply()):
    first=quality.inspect(p,'v.mp4');(quality.CACHE/(first['fingerprint']+'.json')).write_text('{broken')
    self.assertTrue(quality.inspect(p,'v.mp4')['can_approve'])
if __name__=='__main__':unittest.main()
