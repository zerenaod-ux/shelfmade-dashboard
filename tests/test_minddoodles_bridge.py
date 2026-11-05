import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('bridge',Path(__file__).resolve().parents[1]/'minddoodles_bridge.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MindDoodlesBridge(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.p=patch.object(m,'ROOT',self.root);self.p.start();self.addCleanup(self.p.stop)
  self.day=self.root/'data/days/2026-10-19';(self.day/'out').mkdir(parents=True);(self.day/'out/long.mp4').write_bytes(b'fake-video')
  self.pkg={'id':'2026-10-19','status':'ready','long':{'title':'Original','video':'out/long.mp4'},'shorts':[],'publish':{'long':{'youtube':{'status':'pending'}}}};self.save()
 def save(self):(self.day/'package.json').write_text(json.dumps(self.pkg))
 def test_snapshot_never_exposes_tokens_or_upload_sessions(self):
  (self.root/'data/secrets.json').write_text(json.dumps({'YOUTUBE_REFRESH_TOKEN':'secret-value'}));self.pkg['publish']['long']['youtube'].update(upload_session='private-session',url='https://evil.invalid/');self.save();d=m.snapshot();self.assertTrue(d['connections']['youtube']);self.assertNotIn('secret-value',json.dumps(d));self.assertNotIn('private-session',json.dumps(d));self.assertNotIn('evil.invalid',json.dumps(d))
 def test_cross_brand_request_rejected(self):
  with self.assertRaises(ValueError):m.action({'brand':'shelfmade','action':'generate'})
 def test_sample_removal_is_an_explicit_minddoodles_action(self):
  class Creator:
   def remove(self,job,confirmed=False):return {'id':job,'state':'removed_from_collection','confirmed':confirmed}
  with patch.object(m,'short_creator',return_value=Creator()):
   self.assertEqual(m.action({'brand':'minddoodles','action':'remove-short','id':'a'*32,'confirmed':True}),
                    {'id':'a'*32,'state':'removed_from_collection','confirmed':True})
 def test_unpublished_short_removal_is_recoverable_and_hidden(self):
  (self.day/'out/short1.mp4').write_bytes(b'sample-short')
  self.pkg['shorts']=[{'title':'Sample','video':'out/short1.mp4'}]
  self.pkg['publish']['short1']={'youtube':{'status':'pending'}};self.save()
  result=m.remove_review_short('2026-10-19','short1',True)
  self.assertEqual(result['state'],'removed_from_review')
  self.assertFalse((self.day/'out/short1.mp4').exists())
  self.assertEqual((self.day/'.removed-from-review/short1-short1.mp4').read_bytes(),b'sample-short')
  self.assertNotIn('short1',[i['key'] for i in m.snapshot()['packages'][0]['items']])
 def test_published_short_is_protected_from_removal(self):
  (self.day/'out/short1.mp4').write_bytes(b'sample-short')
  self.pkg['shorts']=[{'title':'Published','video':'out/short1.mp4'}]
  self.pkg['publish']['short1']={'youtube':{'status':'published','id':'receipt-1'}};self.save()
  with self.assertRaisesRegex(ValueError,'publishing record'):
   m.remove_review_short('2026-10-19','short1',True)
  self.assertTrue((self.day/'out/short1.mp4').exists())
 def test_traversal_rejected(self):
  with self.assertRaises(ValueError):m.video_path('../shelfmade','long')
  self.pkg['long']['video']='../../../../secret.mp4';self.save()
  with self.assertRaises(ValueError):m.video_path('2026-10-19','long')
 def test_changed_exact_video_invalidates_review(self):
  before=m.fingerprint('2026-10-19');(self.day/'out/long.mp4').write_bytes(b'new-version')
  with self.assertRaises(ValueError):m.action({'brand':'minddoodles','action':'approve','id':'2026-10-19','fingerprint':before,'reviewed':True,'selection':{'long':['youtube']}})
 def test_unknown_receipt_cannot_resubmit(self):
  (self.root/'data/secrets.json').write_text(json.dumps({'YOUTUBE_REFRESH_TOKEN':'test'}));self.pkg['publish']['long']['youtube']['status']='unknown';self.save()
  with patch.object(m.urllib.request,'urlopen') as request:
   with self.assertRaises(ValueError):m.action({'brand':'minddoodles','action':'approve','id':'2026-10-19','fingerprint':m.fingerprint('2026-10-19'),'reviewed':True,'selection':{'long':['youtube']}})
   request.assert_not_called()
 def test_old_native_service_cannot_receive_action(self):
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return b'{"build":"old"}'
  with patch.object(m.urllib.request,'urlopen',return_value=Reply()) as request:
   with self.assertRaises(ValueError):m.action({'brand':'minddoodles','action':'verify-accounts'})
   self.assertEqual(request.call_count,1);self.assertEqual(request.call_args.args[0],'http://127.0.0.1:8777/api/version')
 def test_account_setup_snapshot_never_returns_saved_secrets(self):
  class Reply:
   def __init__(self,data):self.data=data
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return json.dumps(self.data).encode()
  settings={'secrets':{'YOUTUBE_CLIENT_ID':'client-id','YOUTUBE_CLIENT_SECRET':'••••1234','INSTAGRAM_USER_ID':'ig-id','INSTAGRAM_ACCESS_TOKEN':'••••5678','TIKTOK_CLIENT_KEY':'tt-key','TIKTOK_CLIENT_SECRET':'••••9999'},'redirects':{'youtube':'http://localhost:8777/oauth/youtube/callback','tiktok':'http://localhost:8777/oauth/tiktok/callback'}}
  accounts={'youtube':{'connected':False,'verified':False},'instagram':{'connected':False,'verified':False},'tiktok':{'connected':False,'verified':False}}
  with patch.object(m.urllib.request,'urlopen',side_effect=[Reply(settings),Reply(accounts)]):
   result=m.account_setup_snapshot()
  self.assertEqual(result['youtube']['client_id'],'client-id')
  self.assertTrue(result['youtube']['client_secret_saved'])
  self.assertNotIn('1234',json.dumps(result));self.assertNotIn('5678',json.dumps(result));self.assertNotIn('9999',json.dumps(result))
 def test_account_setup_save_only_accepts_allowlisted_minddoodles_fields(self):
  class Reply:
   def __init__(self,data):self.data=data
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return json.dumps(self.data).encode()
  with patch.object(m.urllib.request,'urlopen',side_effect=[Reply({'build':'minddoodles-reference-v7'}),Reply({'ok':True})]) as request:
   result=m.action({'brand':'minddoodles','action':'save-account-settings','secrets':{'YOUTUBE_CLIENT_ID':' client-id '}})
  self.assertTrue(result['ok'])
  body=json.loads(request.call_args.args[0].data)
  self.assertEqual(body,{'secrets':{'YOUTUBE_CLIENT_ID':'client-id'}})
  with self.assertRaisesRegex(ValueError,'only MindDoodles'):
   m.action({'brand':'minddoodles','action':'save-account-settings','secrets':{'SHELFMADE_TOKEN':'borrowed'}})
if __name__=='__main__':unittest.main()

class MindDoodlesHTTPBoundary(unittest.TestCase):
 def test_new_routes_require_owner_session(self):
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  import server
  from unittest.mock import Mock
  for path in ['/api/minddoodles/quality','/api/minddoodles/account-setup','/api/minddoodles','/api/minddoodles/design-reference','/api/minddoodles/approved-sample','/api/minddoodles/approved-poster','/api/minddoodles/production','/api/minddoodles/voice-audition?character=leo','/api/minddoodles/sample','/api/minddoodles/media?day=2026-10-19&item=long','/api/minddoodles/action-package?recipe=silent-treatment']:
   h=Mock();h.path=path;h.headers={};h.local_host.return_value=True
   with patch.object(server.access,'valid',return_value=False),patch.object(server.minddoodles_bridge,'snapshot') as read:
    server.Handler.do_GET(h);self.assertEqual(h.send.call_args.kwargs['status'],401);read.assert_not_called()

 def test_story_action_package_is_story_specific_and_not_rendered(self):
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  import minddoodles_bridge
  package=minddoodles_bridge.action_package('silent-treatment')
  self.assertEqual(package['recipe'],'silent-treatment')
  self.assertEqual(len(package['scenes']),3)
  self.assertEqual('not_submitted',package['scenes'][0]['render']['state'])
  with self.assertRaises(ValueError):minddoodles_bridge.action_package('../unknown')

 def test_shared_minddoodles_setup_ui_does_not_link_to_legacy_settings_page(self):
  html=(Path(__file__).resolve().parents[2]/'content-empire-studio'/'minddoodles.html').read_text()
  self.assertIn('/api/minddoodles/account-setup',html)
  self.assertIn('save-account-settings',html)
  self.assertNotIn('http://localhost:8777/#settings',html)

 def test_authenticated_story_package_route_sets_download_name(self):
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  import server
  from unittest.mock import Mock
  h=Mock();h.path='/api/minddoodles/action-package?recipe=silent-treatment';h.headers={'Cookie':'session'};h.local_host.return_value=True
  with patch.object(server.access,'valid',return_value=True),patch.object(server.minddoodles_bridge,'action_package',return_value={'recipe':'silent-treatment','submitted':False}):
   server.Handler.do_GET(h)
  self.assertEqual(h.send.call_args.args[0]['recipe'],'silent-treatment')
  self.assertEqual(h.send.call_args.kwargs['extra']['Content-Disposition'],'attachment; filename="silent-treatment.action-package.json"')
 def test_action_requires_existing_csrf_header(self):
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  import server
  from unittest.mock import Mock
  h=Mock();h.path='/api/minddoodles/action';h.headers={};h.local_host.return_value=True
  server.Handler.do_POST(h);self.assertEqual(h.send.call_args.kwargs['status'],403)

class ProductionBridge(unittest.TestCase):
 def test_production_rejects_wrong_brand(self):
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return b'{"brand":"shelfmade","schema":1,"today":{"secret":"value"}}'
  with patch.object(m.urllib.request,'urlopen',return_value=Reply()):
   self.assertEqual(m.production_snapshot()['capability']['state'],'service_update_needed')
 def test_production_snapshot_filters_top_level_fields(self):
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return b'{"brand":"minddoodles","schema":1,"today":null,"private_token":"secret"}'
  with patch.object(m.urllib.request,'urlopen',return_value=Reply()):
   self.assertNotIn('secret',json.dumps(m.production_snapshot()))
 def test_prepare_cannot_dispatch_to_old_native_service(self):
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return b'{"build":"minddoodles-creative-v2"}'
  with patch.object(m.urllib.request,'urlopen',return_value=Reply()) as request:
   with self.assertRaises(ValueError):m.action({'brand':'minddoodles','action':'prepare-production'})
   self.assertEqual(request.call_count,1)

class CorrectedVersionDispatch(unittest.TestCase):
 def test_v7_accepts_planning(self):
  class Reply:
   def __init__(self,data):self.data=data
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return json.dumps(self.data).encode()
  with patch.object(m.urllib.request,'urlopen',side_effect=[Reply({'build':'minddoodles-reference-v7'}),Reply({'id':'fixture'})]) as request:
   self.assertTrue(m.action({'brand':'minddoodles','action':'prepare-production','topic':'Original gag'})['ok'])
   self.assertTrue(request.call_args.args[0].full_url.endswith('/api/production/prepare'))
 def test_v6_cannot_start_old_speech(self):
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return b'{"build":"minddoodles-reference-v6"}'
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
  import minddoodles_identity
  with patch.object(minddoodles_identity,'validate_speech_source'),patch.object(m.urllib.request,'urlopen',return_value=Reply()) as request:
   with self.assertRaises(ValueError):m.action({'brand':'minddoodles','action':'build-speech'})
   self.assertEqual(request.call_count,1)

class QualityReleaseBridge(unittest.TestCase):
 def test_coffee_break_review_stream_serves_only_the_saved_preview(self):
  with tempfile.TemporaryDirectory() as temp:
   ui=Path(temp)/'content-empire-studio';root=Path(temp)/'minddoodles-production'/'coffee-break-50'/'repair-v2'/'assembly-work'/'review';root.mkdir(parents=True)
   video=root/'Leo-Mia-The-Five-Second-Coffee-Break-50s.mp4';video.write_bytes(b'local-review-video')
   handler=object()
   with patch.object(m,'UI',ui),patch.object(m,'stream_path') as stream:
    m.coffee_break_review_stream(handler)
   stream.assert_called_once_with(handler,video)
 def test_coffee_break_review_stream_rejects_symlinked_preview(self):
  with tempfile.TemporaryDirectory() as temp:
   ui=Path(temp)/'content-empire-studio';root=Path(temp)/'minddoodles-production'/'coffee-break-50'/'repair-v2'/'assembly-work'/'review';root.mkdir(parents=True)
   outside=Path(temp)/'outside.mp4';outside.write_bytes(b'private')
   (root/'Leo-Mia-The-Five-Second-Coffee-Break-50s.mp4').symlink_to(outside)
   with patch.object(m,'UI',ui),patch.object(m,'stream_path') as stream:
    with self.assertRaisesRegex(ValueError,'unavailable or unsafe'):
     m.coffee_break_review_stream(object())
    stream.assert_not_called()
 def test_real_unaccepted_cast_never_admits_full_build(self):
  data=m.quality_snapshot();self.assertEqual(data['brand'],'minddoodles');self.assertFalse(data['new_full_build_allowed']);self.assertFalse(data['automatic_daily_production_verified']);self.assertNotIn('token',json.dumps(data))
 def test_missing_quality_module_fails_closed(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(m,'UI',Path(temp)/'missing'):
   data=m.quality_snapshot();self.assertFalse(data['new_full_build_allowed']);self.assertEqual(data['state'],'quality_status_unavailable')
