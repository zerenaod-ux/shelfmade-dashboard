import sys,unittest,tempfile,sqlite3,copy,json,io
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import evidence_journal as j
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.db=Path(self.temp.name)/'state.sqlite';self.p=patch.object(j,'DB',self.db);self.p.start();self.addCleanup(self.p.stop)
  self.data={'available':True,'saved_observations':10,'post_count':4,'cohorts':[{'platform':'youtube','format':'short','provider':'buffer','creative_version':'v1','sample_size':2,'message':'Keep collecting','kind':'waiting','coverage_24h':{'measured':2}},{'platform':'instagram','format':'short','provider':'buffer','creative_version':'v1','sample_size':1,'kind':'waiting'},{'platform':'youtube','format':'full','provider':'youtube_direct','creative_version':'v2','sample_size':1,'kind':'waiting'}]}
 def save(self,note='Still too little evidence.',platform='youtube',fmt='short'):return j.save(self.data,platform,fmt,note)
 def test_saved_evidence_is_frozen_and_duplicate_retry_is_idempotent(self):
  first=self.save();self.assertEqual(first,self.save());self.assertEqual(j.snapshot()['total'],1);self.data['cohorts'][0]['sample_size']=99;entry=j.snapshot()['entries'][0];self.assertEqual(entry['evidence']['cohorts'][0]['sample_size'],2)
 def test_filters_do_not_mix_formats_or_platforms(self):
  self.save();entry=j.snapshot()['entries'][0]['evidence'];self.assertEqual(len(entry['cohorts']),1);self.assertEqual(entry['global_distinct_posts'],4)
 def test_providers_and_production_versions_remain_separate(self):
  self.data['cohorts'].append({**self.data['cohorts'][0],'provider':'youtube_direct','creative_version':'v2'})
  self.save();rows=j.snapshot()['entries'][0]['evidence']['cohorts'];self.assertEqual(len(rows),2);self.assertEqual({c['provider'] for c in rows},{'buffer','youtube_direct'})
 def test_missing_metrics_stay_missing_and_no_winner_added(self):
  self.save();e=j.snapshot()['entries'][0]['evidence'];self.assertNotIn('median_24h_views',e['cohorts'][0]);self.assertNotIn('winner',e);self.assertIn('not a controlled experiment',e['policy'])
 def test_read_does_not_create_or_change_database(self):
  self.assertEqual(j.snapshot()['total'],0);self.assertFalse(self.db.exists());self.save();before=self.db.read_bytes();j.snapshot();self.assertEqual(before,self.db.read_bytes())
 def test_invalid_requests_rejected(self):
  for note in ('',' ',None,'x'*1001,'bad\x00note'):
   with self.assertRaises(ValueError):self.save(note)
  with self.assertRaises(ValueError):self.save(platform='publish')
  with self.assertRaises(ValueError):j.save({'available':False},'all','all','A note')
 def test_empty_scope_is_honest_and_literal_text_is_preserved(self):
  text='<script>Publish now</script>';self.save(text,platform='tiktok');e=j.snapshot()['entries'][0];self.assertEqual(e['note'],text);self.assertEqual(e['evidence']['cohorts'],[])
 def test_no_provider_or_approval_changes(self):
  with sqlite3.connect(self.db) as c:c.execute('CREATE TABLE publications(state)');c.execute("INSERT INTO publications VALUES('published')")
  before=copy.deepcopy(self.data)
  with patch('urllib.request.urlopen',side_effect=AssertionError('No provider')):self.save()
  self.assertEqual(self.data,before)
  with sqlite3.connect(self.db) as c:self.assertEqual(c.execute('SELECT state FROM publications').fetchone()[0],'published')
 def test_latest_limit_preserves_all_rows(self):
  for i in range(105):self.save('Assessment '+str(i))
  snapshot=j.snapshot();self.assertEqual(snapshot['total'],105);self.assertEqual(len(snapshot['entries']),100)
 def test_auth_guards_run_before_evidence_read(self):
  import server
  h=object.__new__(server.Handler);h.path='/api/evidence-journal';h.headers={'Host':'127.0.0.1:8765'};h.send=Mock();h.client_address=('127.0.0.1',1234)
  with patch.object(server.Handler,'local_host',return_value=True),patch.object(server.access,'valid',return_value=False),patch.object(j,'snapshot') as read:
   h.do_GET();self.assertEqual(h.send.call_args.kwargs['status'],401);read.assert_not_called()
  h.headers={'Host':'127.0.0.1:8765','Origin':'https://wrong.example','X-ShelfMade':'local'}
  with patch.object(server.Handler,'local_host',return_value=True),patch.object(server,'remote_origin',return_value='https://owner.example'),patch.object(j,'save') as save:
   h.do_POST();self.assertEqual(h.send.call_args.kwargs['status'],403);save.assert_not_called()
 def test_post_captures_server_evidence_ignoring_client_measurements(self):
  import server
  body=json.dumps({'platform':'youtube','format':'short','note':'Check the small sample.','evidence':{'sample_size':999999}}).encode()
  h=object.__new__(server.Handler);h.path='/api/evidence-journal';h.headers={'Host':'127.0.0.1:8765','X-ShelfMade':'local','Content-Length':str(len(body))};h.rfile=io.BytesIO(body);h.send=Mock();h.client_address=('127.0.0.1',1234)
  with patch.object(server.Handler,'local_host',return_value=True),patch.object(server.access,'valid',return_value=True),patch.object(server.audience_learning,'snapshot',return_value=self.data):h.do_POST()
  self.assertTrue(h.send.call_args.args[0]['saved']);self.assertEqual(j.snapshot()['entries'][0]['evidence']['cohorts'][0]['sample_size'],2)
if __name__=='__main__':unittest.main()
