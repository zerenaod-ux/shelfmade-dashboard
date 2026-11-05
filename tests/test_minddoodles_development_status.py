import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('bridge',Path(__file__).resolve().parents[1]/'minddoodles_bridge.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DevelopmentStatus(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
 def save(self,name,data):
  p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data))
 def result(self):return m.development_snapshot(self.root,now=1000)
 def test_no_files_means_unavailable_not_ready(self):
  value=self.result();self.assertEqual(value['character_test']['state'],'unavailable');self.assertEqual(value['local_build']['state'],'not_started')
 def test_status_is_read_only_and_never_exposes_authorization(self):
  self.save('leo-texture-v4/provider-state.json',{'provider_status':'queued','checked_at':990,'authorization':'private text','token':'secret'})
  with patch.object(m.urllib.request,'urlopen') as request:value=self.result();request.assert_not_called()
  self.assertEqual(value['character_test']['state'],'queued');self.assertNotIn('secret',json.dumps(value));self.assertNotIn('private text',json.dumps(value))
 def test_old_character_observation_is_explicitly_stale(self):
  self.save('leo-texture-v4/provider-state.json',{'provider_status':'queued','checked_at':800});self.assertTrue(self.result()['character_test']['stale'])
 def test_provider_complete_is_not_model_success(self):
  self.save('leo-texture-v4/provider-state.json',{'provider_status':'complete','checked_at':990});self.save('leo-texture-v4/Collection-report.json',{'state':'trial_failed'})
  self.assertEqual(self.result()['character_test']['state'],'failed')
 def test_bad_build_pointer_cannot_read_outside_state(self):
  self.save('production-control/latest.json',{'run_id':'../../outside'});self.assertEqual(self.result()['local_build']['state'],'not_started')
 def test_stale_running_observation_is_not_live_progress(self):
  ident='a'*32;self.save('production-control/latest.json',{'run_id':ident});self.save('production-control/runs/'+ident+'/status.json',{'brand':'minddoodles','run_id':ident,'state':'running','started_at':100,'elapsed_seconds':10})
  self.assertEqual(self.result()['local_build']['state'],'observation_stale')
 def test_other_brand_build_cannot_be_minddoodles_progress(self):
  ident='a'*32;self.save('production-control/latest.json',{'run_id':ident});self.save('production-control/runs/'+ident+'/status.json',{'brand':'shelfmade','run_id':ident,'state':'running'})
  self.assertEqual(self.result()['local_build']['state'],'not_started')

if __name__=='__main__':unittest.main()
