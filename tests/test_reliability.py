import sys,tempfile,unittest,sqlite3,datetime,json
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import reliability as r
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.now=datetime.datetime(2026,10,16,18,tzinfo=ZoneInfo('America/Chicago'))
  self.patches=[patch.object(r,'BASE',self.root),patch.object(r,'DB',self.root/'db.sqlite'),patch.object(r,'HISTORY',self.root/'history.json'),patch.object(r.quality,'inspect',return_value={'can_approve':True,'fingerprint':'f','duration':28})]
  for p in self.patches:p.start()
  with sqlite3.connect(r.DB) as c:
   c.execute('CREATE TABLE jobs(id,book,state,attempts,updated,error)');c.execute("INSERT INTO jobs VALUES('one','book','ready',1,'2026-10-16 14:00:00',NULL)")
  folder=self.root/'generated/one/1';folder.mkdir(parents=True);(folder/'final.mp4').write_bytes(b'media');(folder/'POST_THIS.txt').write_text('Supported lesson')
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def test_old_or_future_completion_is_not_todays_fresh_output(self):
  for updated in ['2026-10-15 14:00:00','2026-10-17 14:00:00','unknown']:
   with sqlite3.connect(r.DB) as c:c.execute('UPDATE jobs SET updated=?',(updated,))
   self.assertEqual(r.snapshot(self.now)['completed']['shorts'],0)
 def test_missing_media_and_failed_quality_are_not_counted(self):
  with patch.object(r.quality,'inspect',return_value={'can_approve':False}):self.assertEqual(r.snapshot(self.now)['completed']['shorts'],0)
  (self.root/'generated/one/1/final.mp4').unlink();self.assertEqual(r.snapshot(self.now)['completed']['shorts'],0)
 def test_published_uses_current_fingerprint_and_separate_destinations(self):
  with sqlite3.connect(r.DB) as c:
   c.execute('CREATE TABLE platform_posts(item,fingerprint,platform,state,url)');c.execute("INSERT INTO platform_posts VALUES('job-one','old','instagram','published','https://www.instagram.com/reel/old/')");c.execute("INSERT INTO platform_posts VALUES('job-one','f','youtube','published','https://www.youtube.com/watch?v=abcdefghijk')")
  result=r.snapshot(self.now);dest=result['items'][0]['destinations'];self.assertEqual(dest['youtube']['state'],'published');self.assertEqual(dest['instagram']['state'],'not_submitted');self.assertFalse(result['all_completed_items_published'])
 def test_chicago_date_boundary(self):
  with sqlite3.connect(r.DB) as c:c.execute("UPDATE jobs SET updated='2026-10-16 02:00:00'")
  self.assertEqual(r.snapshot(self.now)['completed']['shorts'],0)
 def test_tracker_keeps_unknown_days_and_closes_window(self):
  history=r.record(self.now);self.assertEqual(history['window_end'],'2026-10-22');self.assertEqual(r.summary(history)['unobserved_days'],6)
  later=self.now+datetime.timedelta(days=8);r.record(later);self.assertEqual(len(json.loads(r.HISTORY.read_text())['observations']),1)
 def test_repeat_observation_does_not_invent_another_day(self):
  r.record(self.now);history=r.record(self.now);self.assertEqual(len(history['observations']),1)
  history=r.record(self.now+datetime.timedelta(minutes=1));self.assertEqual(len(history['observations']),2);self.assertEqual(r.summary(history)['observed_days'],1)
 def test_tracker_is_private_and_never_changes_source_state_or_calls_provider(self):
  before=r.DB.read_bytes()
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):r.record(self.now)
  self.assertEqual(before,r.DB.read_bytes());self.assertEqual(r.HISTORY.stat().st_mode&0o777,0o600)
 def test_dashboard_missing_history_is_unavailable_without_creating_it(self):
  self.assertFalse(r.dashboard(self.now)['available']);self.assertFalse(r.HISTORY.exists())
 def test_dashboard_read_preserves_history_and_never_rechecks_media(self):
  r.record(self.now);before=r.HISTORY.read_bytes()
  with patch.object(r,'snapshot',side_effect=AssertionError('No probing')),patch('urllib.request.urlopen',side_effect=AssertionError('No network')):data=r.dashboard(self.now)
  self.assertTrue(data['available']);self.assertEqual(len(data['days']),7);self.assertEqual(data['days'][0]['state'],'incomplete');self.assertEqual(data['days'][1]['state'],'upcoming');self.assertEqual(before,r.HISTORY.read_bytes())
 def test_dashboard_uses_latest_timestamp_not_file_order(self):
  history=r.record(self.now);new=dict(history['observations'][0]);new['observed_at']=(self.now+datetime.timedelta(minutes=1)).isoformat();new['completed']={'shorts':3,'full':1};history['observations'].insert(0,new);r.HISTORY.write_text(json.dumps(history))
  data=r.dashboard(self.now+datetime.timedelta(minutes=2));self.assertEqual(data['days'][0]['state'],'target_met');self.assertEqual(data['observed_days'],1)
 def test_dashboard_unknown_past_day_does_not_become_zero(self):
  r.record(self.now);data=r.dashboard(self.now+datetime.timedelta(days=2));self.assertEqual(data['days'][1]['state'],'unknown');self.assertIsNone(data['days'][1]['completed'])
 def test_dashboard_future_observation_is_not_evidence(self):
  r.record(self.now);data=r.dashboard(self.now-datetime.timedelta(hours=1));self.assertEqual(data['observed_days'],0)
 def test_dashboard_requires_each_destination_receipt(self):
  history=r.record(self.now);history['observations'][0]['all_completed_items_published']=True;r.HISTORY.write_text(json.dumps(history));day=r.dashboard(self.now)['days'][0];self.assertEqual(day['expected_destinations'],3);self.assertEqual(day['confirmed_destinations'],0)
 def test_dashboard_corrupt_history_fails_closed(self):
  for value in ['{','{}','{"window_start":"2026-10-16","window_end":"2026-11-16"}']:
   r.HISTORY.write_text(value);self.assertFalse(r.dashboard(self.now)['available'])
 def test_dashboard_route_requires_owner_authentication(self):
  import server
  from unittest.mock import Mock
  handler=object.__new__(server.Handler);handler.path='/api/reliability';handler.headers={};handler.local_host=lambda:True;handler.send=Mock()
  with patch.object(server.access,'valid',return_value=False),patch.object(server.reliability,'dashboard',side_effect=AssertionError('Must authenticate')):handler.do_GET()
  self.assertEqual(handler.send.call_args.kwargs['status'],401)
  with patch.object(server.access,'valid',return_value=True),patch.object(server.reliability,'dashboard',return_value={'available':True}) as dashboard:handler.do_GET();dashboard.assert_called_once()
  handler.send.assert_called_with({'available':True})
if __name__=='__main__':unittest.main()
