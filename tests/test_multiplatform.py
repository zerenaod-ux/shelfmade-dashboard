import sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import multiplatform as m, publishing
class PublishingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
  self.db=patch.object(m,'DB',self.base/'test.sqlite');self.db.start()
  self.old=patch.object(publishing,'DB',self.base/'old.sqlite');self.old.start()
  self.mocks=[patch.object(m.buffer_api,'reserve_publish',return_value='test-reservation'),patch.object(m.buffer_api,'release_publish'),patch.object(m,'validate_channels')]
  for mock in self.mocks:mock.start()
  (self.base/'video.mp4').write_bytes(b'reviewed-video')
  self.item={'id':'one','title':'Fresh test','quality':{'fingerprint':'a'*64,'can_approve':True}}
  self.prep={'fingerprint':'a'*64,'title':'Fresh test','description':'Reviewed caption'}
 def tearDown(self):
  for mock in self.mocks:mock.stop()
  self.db.stop();self.old.stop();self.temp.cleanup()
 def start(self):
  with patch.object(m,'status',return_value={'ready':True}),patch.object(m,'remote_history',return_value={'posts':[]}),patch.object(m,'check_duplicates',return_value=None),patch.object(m.threading,'Thread'):
   return m.start(self.item,self.prep,self.base/'video.mp4',['youtube','instagram','tiktok'],True)
 def test_second_click_is_idempotent(self):
  self.assertEqual(self.start()['started'],3);self.assertEqual(self.start()['started'],0)
 def test_unreviewed_and_changed_media_are_blocked(self):
  with self.assertRaises(ValueError):m.start(self.item,self.prep,'x',['youtube'],False)
  self.prep['fingerprint']='b'*64
  with self.assertRaises(ValueError):m.start(self.item,self.prep,'x',['youtube'],True)
 def test_partial_failure_retains_success_and_blocks_uncertain_retry(self):
  self.start();ids=[r['id'] for r in m.rows()]
  def send(network,*args):
   if network=='instagram':raise TimeoutError('Response lost')
   return {'id':network+'-remote','channelId':m.EXPECTED[network],'channelService':network,'status':'sending','externalLink':None}
  with patch.object(m.quality,'inspect',return_value={'fingerprint':'a'*64}),patch.object(m,'validate_channels'),patch.object(m.delivery_video,'prepare',return_value=(self.base/'video.mp4','b'*64)),patch.object(m.cloudinary_host,'upload_video',return_value={'url':'https://example.test/video.mp4'}),patch.object(m,'create_remote',side_effect=send):m.run(ids,self.base/'video.mp4','a'*64)
  states={r['platform']:r['state'] for r in m.rows()}
  self.assertEqual(states,{'youtube':'sending','instagram':'needs_reconciliation','tiktok':'sending'})
  self.assertEqual(self.start()['started'],0)
 def test_buffer_acceptance_is_not_publication(self):
  self.start();row=m.rows()[0];id=row['id'];evidence={'id':'remote','channelId':m.EXPECTED[row['platform']],'channelService':row['platform']};m.apply_remote(id,{**evidence,'status':'sending'})
  self.assertEqual(m.rows()[0]['state'],'sending')
  m.apply_remote(id,{**evidence,'status':'sent','externalLink':{'youtube':'https://www.youtube.com/watch?v=abcdefghijk','instagram':'https://www.instagram.com/reel/abc123/','tiktok':'https://www.tiktok.com/@shelfmade.daily/video/123456'}[row['platform']]})
  self.assertEqual(m.rows()[0]['state'],'published')
 def test_fresh_rendition_is_not_duplicate_of_same_book(self):
  item={**self.item,'generated':True}
  remote={'posts':[{'channelService':'youtube','status':'sent','text':'Fresh test','externalLink':'https://example.test/old'}]}
  self.assertIsNone(m.check_duplicates(item,'youtube',remote))
 def test_failed_attempt_can_be_retried_after_remote_confirmation(self):
  self.start();row=m.rows()[0];m.update(row['id'],state='failed',remote_id='failed-remote')
  with patch.object(m,'status',return_value={'ready':True}),patch.object(m,'remote_history',return_value={'posts':[]}),patch.object(m,'check_duplicates',return_value=None),patch.object(m.threading,'Thread'),patch.object(m.buffer_api,'query',return_value={'post':{'id':'failed-remote','channelId':m.EXPECTED[row['platform']],'channelService':row['platform'],'status':'error'}}):
   result=m.start(self.item,self.prep,self.base/'video.mp4',[row['platform']],True)
  self.assertEqual(result['started'],1)
 def test_metadata_is_public_general_audience(self):
  p=m.payload('youtube','Title','Caption','https://example.test/video.mp4')
  self.assertEqual(p['metadata']['youtube']['privacy'],'public');self.assertFalse(p['metadata']['youtube']['madeForKids']);self.assertFalse(p['saveToDraft']);self.assertEqual(p['mode'],'shareNow')
  self.assertTrue(m.payload('tiktok','Title','Caption','https://example.test/video.mp4',True)['saveToDraft'])
if __name__=='__main__':unittest.main()
