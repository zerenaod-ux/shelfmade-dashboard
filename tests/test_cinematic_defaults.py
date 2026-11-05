import unittest,sys,json,tempfile,sqlite3,io
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cinematic_pipeline as cp,cinematic_content as cc,cinematic_subtitles as cs,full_jobs,youtube_api,publishing
class Tests(unittest.TestCase):
 def test_range(self):
  for t in (300,375,480):cp.validate_duration(t)
  for t in (299.9,480.1,641):
   with self.assertRaises(ValueError):cp.validate_duration(t)
 def test_curated_hook(self):
  s=cc.build('205');self.assertIn('living',s['hook']);self.assertEqual(s['thumbnail_headline'],'BUSY ISN’T LIVING');self.assertLess(len(s['sections']),9)
 def test_catalog_moving_and_matching(self):
  assets=json.loads((cp.BASE/'cinematic-assets.json').read_text());chosen,review=cp.choose_assets('The forest and nature invite closer attention.','Nature',assets)
  self.assertTrue(chosen);self.assertTrue(all('nature' in a['tags'] or 'attention' in a['tags'] for a in chosen));self.assertFalse(review)
  self.assertTrue(all(Path(a['path']).is_file() and a['path'].endswith('.mp4') for a in assets))
 def test_shots_not_repeat_adjacent(self):
  assets=json.loads((cp.BASE/'cinematic-assets.json').read_text());shots=cp.plan_shots([{'index':0,'title':'Nature','narration':'The forest invites attention. Observe nature carefully.','duration':40,'start':0}],assets)
  self.assertTrue(all(a['asset_id']!=b['asset_id'] for a,b in zip(shots,shots[1:])));self.assertTrue(all(s['kind']=='footage' for s in shots))
 def test_punctuation(self):
  g=cs.phrases([{'text':'living','start':0,'end':1},{'text':'?','start':1,'end':1.1}]);self.assertEqual(g[0][0]['text'],'living?')
 def test_ready_books(self):
  self.assertGreater(len(cc.available_books()),10)
  for b in cc.available_books():
   s=cc.build(b['id']);self.assertTrue(s['hook']);self.assertTrue(s['thumbnail_headline']);self.assertLessEqual(len(s['thumbnail_headline'].split()),6)
 def test_thumbnail_api(self):
  with tempfile.TemporaryDirectory() as folder:
   f=Path(folder)/'cover.jpg';f.write_bytes(b'jpeg')
   with patch.object(youtube_api,'request',return_value=io.StringIO('{"items":[{"default":{"url":"https://i.ytimg.com/x"}}]}')) as req:
    self.assertTrue(youtube_api.set_thumbnail('abcdefghijk',f,'secret-not-logged'));self.assertIn('thumbnails/set',req.call_args.args[0]);self.assertEqual(req.call_args.args[2]['Content-Type'],'image/jpeg')
 def test_thumbnail_failure_does_not_retry_video(self):
  class Immediate:
   def __init__(self,target,daemon):self.target=target
   def start(self):self.target()
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'state.sqlite';video=Path(folder)/'video.mp4';video.write_bytes(b'video')
   with patch.object(publishing,'DB',db):
    with youtube_api.connect_db() as c:c.execute("INSERT INTO publications(id,item,fingerprint,platform,title,description,state) VALUES ('p','i','f','youtube','Title','Caption','awaiting_publisher')")
    result={'id':'abcdefghijk','snippet':{'channelId':youtube_api.EXPECTED},'status':{'privacyStatus':'public','uploadStatus':'processed'}}
    class Response(io.StringIO):
     status=200;headers={'Location':'https://www.googleapis.com/upload/session'}
    with patch.object(youtube_api,'status',return_value={'connected':True}),patch.object(youtube_api,'token',return_value='private'),patch.object(youtube_api,'verify_channel'),patch.object(youtube_api.threading,'Thread',Immediate),patch.object(youtube_api,'request',side_effect=[Response('{}'),Response(json.dumps(result))]),patch.object(youtube_api,'set_thumbnail',side_effect=ValueError('rejected')):
     youtube_api.send_upload('p',video,'public',False,Path(folder)/'cover.jpg')
    with youtube_api.connect_db() as c:row=dict(c.execute("SELECT * FROM publications WHERE id='p'").fetchone())
    self.assertEqual(row['state'],'published');self.assertTrue(row['url']);self.assertEqual(row['thumbnail_state'],'needs_attention')
    with self.assertRaises(ValueError):youtube_api.send_upload('p',video,'public',False)
if __name__=='__main__':unittest.main()
