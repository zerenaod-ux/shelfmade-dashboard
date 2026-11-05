import sys,unittest,tempfile,json,sqlite3,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audience_learning as a
T=1760000000
class Audience(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(a,'DB',Path(self.tmp.name)/'state.sqlite');self.patch.start()
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def add(self,hours,views=20,likes=2,comments=1,key='abcdefghijk',provider='youtube_direct',measured=True,published=T,content='Title'):
  return a.record('youtube',provider,'https://www.youtube.com/watch?v='+key,'Title',published,T+hours*3600,{'views':views,'likes':likes,'comments':comments},T+hours*3600 if measured else None,content)
 def test_zero_is_real_missing_and_invalid_are_not_zero(self):
  self.add(1,views=0,likes=None,comments='invalid');post=a.snapshot(T+3600)['posts'][0]
  self.assertEqual(post['latest']['views'],0);self.assertIsNone(post['latest']['likes']);self.assertIsNone(post['latest']['comments']);self.assertIsNone(post['like_comment_rate'])
  for value in (-1,True,'NaN','inf','2.5'):self.assertIsNone(a.number(value))
 def test_no_backfill_from_current_total(self):
  self.add(100,views=900);p=a.snapshot(T+101*3600)['posts'][0]
  self.assertEqual(p['at_24h']['state'],'missed');self.assertEqual(p['at_72h']['state'],'missed');self.assertIsNone(p['views_gained_24_to_72'])
 def test_windows_use_actual_measured_age(self):
  self.add(23,10);self.add(25,20);self.add(76,70);p=a.snapshot(T+80*3600)['posts'][0]
  self.assertEqual(p['at_24h']['age_hours'],25);self.assertEqual(p['at_72h']['age_hours'],76);self.assertEqual(p['views_gained_24_to_72'],50)
 def test_unknown_metric_time_never_qualifies(self):
  self.add(25,provider='buffer',measured=False);p=a.snapshot(T+25*3600)['posts'][0]
  self.assertEqual(p['at_24h']['state'],'collecting');self.assertFalse(p['timing_verified'])
 def test_cached_buffer_observations_deduplicate(self):
  data={'checked_at':T+25*3600,'posts':[{'channelService':'instagram','channelId':'ig','status':'sent','externalLink':'https://www.instagram.com/reel/abc/','text':'Title','sentAt':T,'metricsUpdatedAt':T+24*3600,'metrics':[{'type':'views','value':0},{'type':'averageTimeWatched','value':7000,'unit':'milliseconds'}]}]}
  a.ingest_buffer(data,{'instagram':'ig'});data['checked_at']+=3600;a.ingest_buffer(data,{'instagram':'ig'})
  result=a.snapshot(T+26*3600);self.assertEqual(result['saved_observations'],1);self.assertEqual(result['posts'][0]['latest']['average_watch_seconds'],7)
  data['posts'][0]['metrics'][1].pop('unit');data['posts'][0]['metricsUpdatedAt']+=3600;a.ingest_buffer(data,{'instagram':'ig'});self.assertIsNone(a.snapshot(T+26*3600)['posts'][0]['latest']['average_watch_seconds'])
 def test_provider_and_format_cohorts_do_not_mix(self):
  self.add(25,20);self.add(25,80,provider='buffer')
  items=[{'id':'item','content_type':'full','quality':{'fingerprint':'f'}}];pub=[{'item':'item','fingerprint':'f','platform':'youtube','url':'https://youtu.be/abcdefghijk'}]
  a.bind_items(items,pub);result=a.snapshot(T+26*3600)
  self.assertEqual(result['post_count'],1);self.assertEqual(result['posts'][0]['provider'],'youtube_direct');self.assertEqual(len(result['cohorts']),2);self.assertTrue(all(c['format']=='full' for c in result['cohorts']))
 def test_local_fingerprint_must_match_and_binding_is_pinned(self):
  self.add(25)
  item={'id':'item','content_type':'short','quality':{'fingerprint':'new','creative':{'hook':'A question?','version':'v1'}}};post={'item':'item','fingerprint':'old','platform':'youtube','url':'https://youtu.be/abcdefghijk'}
  self.assertEqual(a.bind_items([item],[post]),0);post['fingerprint']='new';self.assertEqual(a.bind_items([item],[post]),1)
  item['content_type']='full';self.assertEqual(a.bind_items([item],[post]),0);self.assertEqual(a.snapshot(T+26*3600)['posts'][0]['format'],'short')
 def test_small_sample_suppresses_experiment(self):
  self.add(25)
  a.bind_items([{'id':'item','content_type':'short','quality':{'fingerprint':'f'}}],[{'item':'item','fingerprint':'f','platform':'youtube','url':'https://youtu.be/abcdefghijk'}])
  cohort=a.snapshot(T+26*3600)['cohorts'][0];self.assertEqual(cohort['sample_size'],1);self.assertEqual(cohort['kind'],'waiting');self.assertNotIn('leading_post',cohort)
 def test_enough_comparable_samples_support_only_an_experiment(self):
  items=[];pub=[]
  for i in range(5):
   key=f'abcdefghij{i}';self.add(25,10+i*10,key=key);items.append({'id':str(i),'content_type':'short','quality':{'fingerprint':'f'}});pub.append({'item':str(i),'fingerprint':'f','platform':'youtube','url':'https://youtu.be/'+key})
  a.bind_items(items,pub);cohort=a.snapshot(T+26*3600)['cohorts'][0]
  self.assertEqual(cohort['median_24h_views'],30);self.assertEqual(cohort['sample_size'],5);self.assertEqual(cohort['kind'],'observation');self.assertIn('No automatic',cohort['caution'])
 def test_counter_revision_is_not_hidden(self):
  self.add(25,100);self.add(73,80);p=a.snapshot(T+74*3600)['posts'][0]
  self.assertEqual(p['views_gained_24_to_72'],-20);self.assertTrue(p['counter_adjusted'])
 def test_edited_posts_are_flagged(self):
  self.add(25,content='First');self.add(26,content='Changed');self.assertTrue(a.snapshot(T+27*3600)['posts'][0]['content_changed'])
 def test_snapshot_does_not_write_or_contact_a_provider(self):
  self.assertEqual(a.snapshot(T)['posts'],[]);self.assertFalse(a.DB.exists());self.add(1)
  before=hashlib.sha256(a.DB.read_bytes()).hexdigest()
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network reads')):a.snapshot(T+3600)
  self.assertEqual(before,hashlib.sha256(a.DB.read_bytes()).hexdigest())
 def test_collector_claim_and_failure_backoff_survive_connections(self):
  self.assertTrue(a.claim('buffer',T));self.assertFalse(a.claim('buffer',T+1));a.collector_result('buffer','refresh_failed',T)
  self.assertFalse(a.claim('buffer',T+3599));self.assertTrue(a.claim('buffer',T+3601))
 def test_wrong_channel_and_unknown_publication_times_remain_safe(self):
  video={'id':'abcdefghijk','snippet':{'channelId':'other'},'status':{'privacyStatus':'public','uploadStatus':'processed'}}
  self.assertFalse(a.ingest_youtube(video,T,'owner'));self.assertIsNone(a.timestamp('2026-01-01'))
  self.add(25,published=None);self.assertEqual(a.snapshot(T+26*3600)['posts'][0]['at_24h']['state'],'publication_time_unknown')
class CollectorSafety(unittest.TestCase):
 setUp=Audience.setUp
 tearDown=Audience.tearDown
 add=Audience.add
 def test_budget_pause_does_not_call_remote_history(self):
  import buffer_api,multiplatform
  private=Path(self.tmp.name)/'private';private.mkdir();(private/'credentials.json').write_text('{}')
  with patch.object(buffer_api,'PRIVATE',private),patch.object(buffer_api,'budget_status',return_value={'analytics_paused':True}),patch.object(multiplatform,'remote_history') as remote:
   self.assertFalse(a.refresh_due());remote.assert_not_called()
  self.assertEqual(a.snapshot()['collectors'][0]['state'],'budget_paused')
 def test_short_url_proof_propagates_without_guessing_from_titles(self):
  a.record('youtube','buffer','https://www.youtube.com/shorts/abcdefghijk','A long full video',T,T+25*3600,{'views':20},T+25*3600)
  self.add(25,views=20)
  result=a.snapshot(T+26*3600);self.assertEqual(result['posts'][0]['format'],'short')
  a.record('youtube','buffer','https://www.youtube.com/watch?v=abcdefghij2','A Short under 60 seconds',T,T+25*3600,{'views':20},T+25*3600)
  self.assertEqual(next(p for p in a.snapshot(T+26*3600)['posts'] if p['post_key']=='abcdefghij2')['format'],'unknown')
class Revisions(unittest.TestCase):
 setUp=Audience.setUp
 tearDown=Audience.tearDown
 def test_provider_revision_keeps_history_without_fake_fresh_age(self):
  url='https://www.instagram.com/reel/abc/'
  a.record('instagram','buffer',url,'Title',T,T+25*3600,{'views':20},T+24*3600)
  a.record('instagram','buffer',url,'Title',T,T+26*3600,{'views':18},T+24*3600)
  result=a.snapshot(T+50*3600);self.assertEqual(result['saved_observations'],2)
  self.assertEqual(result['posts'][0]['at_24h']['sample']['views'],18);self.assertEqual(result['posts'][0]['at_24h']['age_hours'],24)
  self.assertTrue(result['posts'][0]['stale'])
 def test_old_cached_collection_does_not_clear_a_new_failure(self):
  a.claim('buffer',T);a.collector_result('buffer','refresh_failed',T+100)
  a.note_collection('buffer',T-1000)
  state=a.snapshot(T+101)['collectors'][0];self.assertEqual(state['state'],'refresh_failed')
if __name__=='__main__':unittest.main()
