import sys,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_audience_learning as fixtures
T=fixtures.T
import audience_learning as a
class Tests(unittest.TestCase):
 setUp=fixtures.Audience.setUp
 tearDown=fixtures.Audience.tearDown
 add=fixtures.Audience.add
 def bind(self,key='abcdefghijk',version='style-one',question=True):
  a.bind_items([{'id':key,'content_type':'short','quality':{'fingerprint':'f','creative':{'version':version,'hook':'What do you notice?' if question else 'Notice your everyday habits.'}}}],[{'item':key,'fingerprint':'f','platform':'youtube','url':'https://www.youtube.com/watch?v='+key}])
 def fill(self,versions):
  for index,version in enumerate(versions):
   key='hook'+str(index).zfill(7);self.add(25,key=key,views=10+index);self.bind(key,version,index%2==0)
 def test_production_versions_do_not_pool_into_a_large_sample(self):
  self.fill(['old']*4+['new']*4);groups=a.snapshot(T+27*3600)['cohorts'];self.assertEqual(len(groups),2);self.assertEqual({g['creative_version'] for g in groups},{'old','new'});self.assertTrue(all(g['sample_size']==4 and g['kind']=='waiting' for g in groups))
 def test_same_recorded_version_can_support_cautious_hook_comparison(self):
  self.fill(['one']*8);group=a.snapshot(T+27*3600)['cohorts'][0];self.assertEqual(group['hook_comparison']['question']['n'],4);self.assertEqual(group['hook_comparison']['statement']['n'],4);self.assertIn('Small observational sample',group['caution'])
 def test_unrecorded_version_never_supports_hook_style_comparison(self):
  self.fill([None]*8);group=a.snapshot(T+27*3600)['cohorts'][0];self.assertEqual(group['creative_version'],'unrecorded');self.assertNotIn('hook_comparison',group)
 def test_alternate_provider_checkpoint_is_visible_without_replacing_direct_total(self):
  self.add(25,provider='buffer',views=45);self.add(100,views=300);self.bind();result=a.snapshot(T+101*3600);self.assertEqual(result['post_count'],1);post=result['posts'][0];self.assertEqual(post['provider'],'youtube_direct');self.assertEqual(post['latest']['views'],300);self.assertIsNone(post['at_24h']['sample']);sources={s['provider']:s for s in post['source_measurements']};self.assertEqual(sources['buffer']['at_24h']['sample']['views'],45);self.assertEqual(len(result['cohorts']),2)
 def test_coverage_separates_measured_waiting_and_missed(self):
  self.add(25);self.bind();self.add(40,key='abcdefghij2',published=T+39*3600);self.bind('abcdefghij2');self.add(40,key='abcdefghij3');self.bind('abcdefghij3');group=a.snapshot(T+40*3600)['cohorts'][0];self.assertEqual(group['coverage_24h']['measured'],1);self.assertEqual(group['coverage_24h']['waiting'],1);self.assertEqual(group['coverage_24h']['missed'],1);self.assertEqual(group['coverage_72h']['waiting'],3)
 def test_changed_caption_exclusion_remains_visible(self):
  self.add(25,content='old');self.add(26,content='new');self.bind();group=a.snapshot(T+27*3600)['cohorts'][0];self.assertEqual(group['sample_size'],0);self.assertEqual(group['changed_posts_excluded'],1);self.assertEqual(group['coverage_24h']['measured'],1)
 def test_readiness_deduplicates_provider_records_for_same_post(self):
  self.add(25);self.add(25,provider='buffer');self.bind();row=a.snapshot(T+27*3600)['data_readiness'][0];self.assertEqual(row['posts'],1);self.assertEqual(row['measured_24h_posts'],1);self.assertEqual(row['measured_72h_posts'],0);self.assertFalse(row['retention_available'])
 def test_watch_time_presence_is_not_called_a_retention_curve(self):
  a.record('youtube','buffer','https://www.youtube.com/watch?v=abcdefghijk','Title',T,T+25*3600,{'views':10,'average_watch_seconds':7},T+25*3600);self.bind();result=a.snapshot(T+27*3600);self.assertEqual(result['data_readiness'][0]['watch_time_posts'],1);self.assertFalse(result['retention_curve']['available'])
 def test_unclassified_first_day_points_are_not_called_comparable(self):
  self.add(25);result=a.snapshot(T+27*3600);self.assertEqual(result['data_readiness'][0]['unclassified_24h_posts'],1);self.assertEqual(result['cohorts'],[])
 def test_snapshot_is_read_only_and_never_contacts_provider(self):
  self.add(25);self.bind();before=a.DB.read_bytes()
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):result=a.snapshot(T+27*3600)
  self.assertEqual(a.DB.read_bytes(),before);self.assertEqual(result['version'],'audience-learning-v2')
if __name__=='__main__':unittest.main()
