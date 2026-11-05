"""Publishing confidence: simulated responses only; no credentials, workers or live posts."""
import sys,tempfile,unittest,json,io,datetime,concurrent.futures
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import multiplatform as m,publishing as p,youtube_api as y
class Immediate:
 def __init__(self,target,daemon=True,**kwargs):self.target=target
 def start(self):self.target()
class Response(io.StringIO):
 status=200
 headers={'Location':'https://www.googleapis.com/upload/session'}
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.file=self.base/'final.mp4';self.file.write_bytes(b'approved-film')
  self.patches=[patch.object(m,'DB',self.base/'state.db'),patch.object(p,'DB',self.base/'state.db'),patch.object(m,'BASE',self.base)]
  for v in self.patches:v.start()
  with m.connect() as c:c.execute("INSERT INTO platform_posts(id,item,fingerprint,platform,title,description,state,submitted_at) VALUES ('b','i','f','instagram','Title','Caption','submitting',?)",(m.now(),))
 def tearDown(self):
  for v in reversed(self.patches):v.stop()
  self.tmp.cleanup()
 def remote(self,**changes):return {'id':'remote','channelId':m.EXPECTED['instagram'],'channelService':'instagram','status':'sent','externalLink':'https://www.instagram.com/reel/real123/',**changes}
 def row(self):return next(r for r in m.rows() if r['id']=='b')
 def direct(self):
  with y.connect_db() as c:c.execute("INSERT INTO publications(id,item,fingerprint,platform,title,description,state) VALUES ('d','i','f','youtube','Title','Caption','awaiting_publisher')")
 def test_wrong_account_is_uncertain_without_public_link(self):
  self.assertFalse(m.apply_remote('b',self.remote(channelId='wrong')));self.assertEqual(self.row()['state'],'needs_reconciliation');self.assertIsNone(self.row()['url'])
 def test_wrong_service_is_uncertain(self):self.assertFalse(m.apply_remote('b',self.remote(channelService='youtube')))
 def test_missing_post_is_uncertain(self):self.assertFalse(m.apply_remote('b',None));self.assertEqual(self.row()['state'],'needs_reconciliation')
 def test_dashboard_or_arbitrary_link_is_not_publication(self):
  for link in ['https://publish.buffer.com/','https://example.test/','http://www.instagram.com/reel/real123/','https://www.instagram.com.evil.test/reel/real123/','https://www.instagram.com/']:
   m.apply_remote('b',self.remote(externalLink=link));self.assertNotEqual(self.row()['state'],'published');self.assertIsNone(self.row()['url'])
 def test_success_survives_stale_or_missing_responses(self):
  m.apply_remote('b',self.remote());m.apply_remote('b',self.remote(status='sending',externalLink=None));m.apply_remote('b',None)
  self.assertEqual(self.row()['state'],'published');self.assertEqual(self.row()['url'],self.remote()['externalLink'])
 def test_remote_id_cannot_be_replaced(self):
  m.apply_remote('b',self.remote(status='sending'));self.assertFalse(m.apply_remote('b',self.remote(id='other')));self.assertEqual(self.row()['remote_id'],'remote')
 def test_persisted_evidence_trail(self):
  m.apply_remote('b',self.remote(status='sending'));m.apply_remote('b',self.remote())
  with m.connect() as c:events=list(c.execute("SELECT state,observed_at FROM publishing_events WHERE post_id='b' ORDER BY sequence"))
  self.assertEqual([r[0] for r in events],['sending','published']);self.assertTrue(all(r[1] for r in events))
 def test_replayed_worker_does_not_call_provider(self):
  m.apply_remote('b',self.remote())
  with patch.object(m,'create_remote') as send,patch.object(m,'validate_channels') as validate:m._run(['b'],self.file,'f')
  send.assert_not_called();validate.assert_not_called();self.assertEqual(self.row()['state'],'published')
 def test_reconcile_requires_account_time_and_unique_evidence(self):
  m.update('b',state='needs_reconciliation')
  with m.connect() as c:c.execute("INSERT INTO delivery_hosts VALUES('f','https://host.test/video.mp4')")
  remote=self.remote(assets=[{'source':'https://host.test/video.mp4'}],text='Caption',createdAt=m.now())
  cache=self.base/'buffer-history.json'
  for posts in [[{**remote,'channelId':'wrong'}],[{**remote,'createdAt':'2000-01-01T00:00:00Z'}],[remote,{**remote,'id':'second'}]]:
   cache.write_text(json.dumps({'posts':posts}));m.reconcile_local();self.assertEqual(self.row()['state'],'needs_reconciliation')
  cache.write_text(json.dumps({'posts':[remote]}));m.reconcile_local();self.assertEqual(self.row()['state'],'published')
 def test_content_claim_is_atomic_between_routes(self):
  digest=p.media_digest(self.file)
  def reserve(owner):
   with m.connect() as c:
    c.execute('BEGIN IMMEDIATE');return p.claim(c,'youtube',digest,owner)
  with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(reserve,['direct','buffer']))
  self.assertEqual(sum(results),1)
 def test_caption_change_cannot_claim_same_bytes(self):
  with m.connect() as c:
   c.execute('BEGIN IMMEDIATE');self.assertTrue(p.claim(c,'instagram',p.media_digest(self.file),'old-fingerprint'));self.assertFalse(p.claim(c,'instagram',p.media_digest(self.file),'new-fingerprint'))
 def test_new_media_can_have_same_book_title(self):
  with m.connect() as c:
   c.execute('BEGIN IMMEDIATE');self.assertTrue(p.claim(c,'instagram',p.media_digest(self.file),'first'));self.file.write_bytes(b'new-film');self.assertTrue(p.claim(c,'instagram',p.media_digest(self.file),'second'))
 def test_direct_route_blocks_existing_buffer_attempt(self):
  self.direct()
  with m.connect() as c:c.execute("UPDATE platform_posts SET platform='youtube',state='sending' WHERE id='b'")
  with patch.object(y,'status',return_value={'connected':True}),patch.object(y.threading,'Thread') as worker:
   with self.assertRaises(ValueError):y.send_upload('d',self.file,'public',False)
  worker.assert_not_called()
 def test_direct_lost_initial_response_is_uncertain(self):
  self.direct()
  with patch.object(y,'status',return_value={'connected':True}),patch.object(y,'token',return_value='private'),patch.object(y,'verify_channel'),patch.object(y.threading,'Thread',Immediate),patch.object(y,'request',side_effect=TimeoutError('Lost reply')):
   y.send_upload('d',self.file,'public',False)
  with y.connect_db() as c:row=dict(c.execute("SELECT * FROM publications WHERE id='d'").fetchone())
  self.assertEqual(row['state'],'needs_reconciliation');self.assertIsNone(row['upload_session'])
  with self.assertRaises(ValueError):y.send_upload('d',self.file,'public',False)
 def test_known_http400_before_upload_can_be_retried(self):
  self.direct()
  with y.connect_db() as c:c.execute("UPDATE publications SET state='failed',error='Google request failed (HTTP 400). Reconnect or check YouTube API configuration.' WHERE id='d'")
  self.assertTrue(p.list_posts()[0]['retry_safe'])
  video={'id':'abcdefghijk','snippet':{'channelId':y.EXPECTED},'status':{'privacyStatus':'private','uploadStatus':'processed'}}
  with patch.object(y,'status',return_value={'connected':True}),patch.object(y,'token',return_value='private'),patch.object(y,'verify_channel'),patch.object(y.threading,'Thread',Immediate),patch.object(y,'request',side_effect=[Response(''),Response(json.dumps(video))]) as request:
   y.send_upload('d',self.file,'private',False)
  self.assertEqual(request.call_count,2)
  with y.connect_db() as c:row=dict(c.execute("SELECT * FROM publications WHERE id='d'").fetchone())
  self.assertEqual(row['state'],'processing_private');self.assertTrue(row['url'].endswith('abcdefghijk'))
 def test_failed_row_with_saved_session_is_not_retryable(self):
  self.direct()
  with y.connect_db() as c:c.execute("UPDATE publications SET state='failed',error='Google request failed (HTTP 400).',upload_session='https://www.googleapis.com/upload/session' WHERE id='d'")
  self.assertFalse(p.list_posts()[0]['retry_safe'])
  with patch.object(y,'status',return_value={'connected':True}),patch.object(y.threading,'Thread') as worker:
   with self.assertRaises(ValueError):y.send_upload('d',self.file,'public',False)
  worker.assert_not_called()
 def session(self):
  self.direct()
  with y.connect_db() as c:c.execute("UPDATE publications SET state='needs_reconciliation',upload_session='https://www.googleapis.com/upload/session',upload_size='13' WHERE id='d'")
 def test_session_status_recovers_completed_upload_without_sending_media(self):
  self.session();video={'id':'abcdefghijk','snippet':{'channelId':y.EXPECTED},'status':{'privacyStatus':'public','uploadStatus':'processed'}}
  with patch.object(y,'request',return_value=Response(json.dumps(video))) as request:y.recover_sessions('private')
  args=request.call_args.args;self.assertEqual(args[1],b'');self.assertEqual(args[2]['Content-Range'],'bytes */13');self.assertEqual(args[3],'PUT')
  self.assertEqual(p.list_posts()[0]['state'],'published')
 def test_incomplete_session_stays_uncertain(self):
  self.session();response=Response('');response.status=308
  with patch.object(y,'request',return_value=response):y.recover_sessions('private')
  self.assertEqual(p.list_posts()[0]['state'],'needs_reconciliation');self.assertIsNone(p.list_posts()[0]['url'])
 def test_expired_session_never_starts_fresh_upload(self):
  self.session()
  with patch.object(y,'request',side_effect=RuntimeError('HTTP 404')) as request:y.recover_sessions('private')
  self.assertEqual(request.call_count,1);self.assertEqual(p.list_posts()[0]['state'],'needs_reconciliation')
 def test_wrong_channel_session_result_is_not_public(self):
  self.session()
  with patch.object(y,'request',return_value=Response(json.dumps({'id':'abcdefghijk','snippet':{'channelId':'wrong'},'status':{'privacyStatus':'public','uploadStatus':'processed'}}))):y.recover_sessions('private')
  self.assertIsNone(p.list_posts()[0]['url'])
 def test_restart_and_prepare_hide_session_secret(self):
  self.session()
  with y.connect_db() as c:c.execute("UPDATE publications SET state='uploading' WHERE id='d'")
  y.recover_interrupted();self.assertEqual(p.list_posts()[0]['state'],'needs_reconciliation')
  row=p.prepare({'id':'i','quality':{'can_approve':True,'fingerprint':'f'}},'Title','A thoughtful lesson from this book.',True)
  self.assertNotIn('upload_session',row);self.assertNotIn('upload_session',p.list_posts()[0])
if __name__=='__main__':unittest.main()
