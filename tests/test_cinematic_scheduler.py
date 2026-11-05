import unittest,tempfile,sys,datetime,json
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_jobs,cinematic_pipeline as cp,cinematic_content as cc,daily_plan,quality
class Tests(unittest.TestCase):
 def test_daily_only_once_and_never_before_nine(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   with patch.object(full_jobs,'DB',root/'state.sqlite'),patch.object(full_jobs,'ROOT',root/'outputs'),patch.dict('os.environ',{'SHELFMADE_STUDIO':str(root/'studio')}),patch.object(full_jobs,'script_for',return_value={}),patch.object(full_jobs,'enqueue',return_value={'id':'test'}) as queue:
    full_jobs.queue_daily(datetime.datetime(2026,10,20,8,tzinfo=ZoneInfo('America/Chicago')));queue.assert_not_called()
    full_jobs.queue_daily(datetime.datetime(2026,10,20,9,tzinfo=ZoneInfo('America/Chicago')))
    full_jobs.queue_daily(datetime.datetime(2026,10,20,10,tzinfo=ZoneInfo('America/Chicago')));self.assertEqual(queue.call_count,1)
 def test_failed_midnight_reservation_uses_remaining_bounded_recovery(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);now=datetime.datetime(2026,10,20,10,tzinfo=ZoneInfo('America/Chicago'))
   window=('2026-10-20 05:00:00','2026-10-21 05:00:00')
   with patch.object(full_jobs,'DB',root/'state.sqlite'),patch.object(full_jobs,'ROOT',root/'outputs'),patch.object(full_jobs,'attempt_window',return_value=window),patch('cinematic_pipeline.settings',return_value={'daily_generation':True,'daily_hour_chicago':9}),patch.object(full_jobs,'retry',return_value={'id':'old','state':'queued'}) as retry,patch.object(full_jobs,'enqueue') as enqueue:
    with full_jobs.connect() as c:
     c.execute("INSERT INTO full_jobs(id,book,state,created,version) VALUES('old','14988','failed','2026-10-19 23:00:00','cinematic-default-v1')")
     c.execute('INSERT INTO full_generation_attempts(job,started) VALUES (?,?)',('old','2026-10-20 05:15:00'))
     c.execute('CREATE TABLE full_daily_generation(day TEXT PRIMARY KEY,book TEXT NOT NULL)')
     c.execute('INSERT INTO full_daily_generation(day,book) VALUES (?,?)',('2026-10-20','14988'))
    full_jobs.queue_daily(now)
    retry.assert_called_once_with('old');enqueue.assert_not_called()
 def test_daily_pick_can_fill_after_generation(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(daily_plan,'DB',Path(folder)/'state.sqlite'):
   self.assertIsNone(daily_plan.full_pick([],[])['id'])
   item={'id':'new','title':'New','content_type':'full','ready':True,'status':'review','quality':{'duration':400,'can_approve':True}}
   self.assertEqual(daily_plan.full_pick([item],[])['id'],'new')
 def test_word_timing_drives_shot_anchor(self):
  assets=json.loads((cp.BASE/'cinematic-assets.json').read_text());chapter={'index':0,'title':'An idea','narration':'A completely different sentence.','start':0,'duration':8}
  shots=cp.plan_shots([chapter],assets,[{'text':'forest','start':0,'end':1},{'text':'nature','start':1,'end':2}]);self.assertEqual(shots[0]['narration_anchor'],'forest nature')
 def test_cover_change_requires_new_review(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'v.mp4').write_bytes(b'video');(p/'POST_THIS.txt').write_text('Caption');(p/'THUMBNAIL.jpg').write_bytes(b'cover');(p/'package.json').write_text('{"style":"cinematic-default-v1"}')
   media={'format':{'duration':'400'},'streams':[{'codec_type':'video','width':1280,'height':720},{'codec_type':'audio'}]}
   class Result:stdout=json.dumps(media)
   with patch.object(quality,'CACHE',p/'cache'),patch.object(quality.subprocess,'run',return_value=Result()):
    first=quality.inspect(p,'v.mp4',True);(p/'THUMBNAIL.jpg').write_bytes(b'new cover');second=quality.inspect(p,'v.mp4',True)
   self.assertNotEqual(first['fingerprint'],second['fingerprint']);self.assertTrue(first['can_approve'])
if __name__=='__main__':unittest.main()
