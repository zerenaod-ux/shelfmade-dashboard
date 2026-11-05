import sys,unittest,copy
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import book_series as b
class Tests(unittest.TestCase):
 def items(self):return [{'id':'short-one','book_id':'1497','title':'Republic Short','ready':True,'content_type':'short','status':'approved','quality':{'fingerprint':'f','can_approve':True}},{'id':'full-one','book_id':'1497','title':'Republic full','ready':True,'content_type':'full','status':'approved','quality':{'fingerprint':'g','can_approve':True}}]
 def books(self):return [{'id':'1497','title':'The Republic'}]
 def post(self,item='short-one',fp='f',network='youtube',url='https://www.youtube.com/watch?v=abcdefghijk',state='published'):return {'item':item,'fingerprint':fp,'platform':network,'url':url,'state':state}
 def result(self,items=None,posts=None,summaries=None):return b.snapshot(items if items is not None else self.items(),posts or [],self.books(),summaries or {})
 def test_groups_by_explicit_book_and_separates_formats(self):
  data=self.result();group=data['series'][0];self.assertEqual(group['title'],'The Republic');self.assertEqual(len(group['full']),1);self.assertEqual(len(group['shorts']),1);self.assertFalse(group['connected'])
 def test_never_guesses_book_from_title(self):
  items=self.items();items[0].pop('book_id');data=self.result(items);self.assertEqual(data['unclassified_items'],1);self.assertEqual(data['series'][0]['shorts'],[])
 def test_pending_or_old_media_receipts_are_not_public(self):
  result=self.result(posts=[self.post(state='sending'),self.post(fp='old')]);self.assertFalse(result['series'][0]['has_public_short'])
 def test_public_series_requires_a_confirmed_full_and_short(self):
  group=self.result(posts=[self.post(),self.post('full-one','g',url='https://www.youtube.com/watch?v=lmnopqrstuv')])['series'][0];self.assertTrue(group['connected'])
 def test_duplicate_direct_and_buffer_urls_are_one_public_link(self):
  posts=[self.post(),self.post(url='https://www.youtube.com/shorts/abcdefghijk')];self.assertEqual(len(self.result(posts=posts)['series'][0]['shorts'][0]['published']),1)
 def test_full_video_only_accepts_youtube_receipt_and_rejects_bad_urls(self):
  posts=[self.post('full-one','g','instagram','https://www.instagram.com/reel/code/'),self.post(url='https://attacker.example/watch?v=abcdefghijk'),self.post(url='http://www.youtube.com/watch?v=abcdefghijk')];group=self.result(posts=posts)['series'][0];self.assertFalse(group['has_public_full']);self.assertFalse(group['has_public_short'])
 def test_angles_are_three_distinct_existing_summary_titles(self):
  summaries={'1497':{'ideas':[{'title':'Justice','explanation':'An existing editorial summary.'},{'title':'justice','explanation':'Duplicate.'},{'title':'Knowledge','explanation':'A second summary.'},{'title':'Education','explanation':'A third summary.'},{'title':'Government','explanation':'Not included.'}]}}
  angles=self.result(summaries=summaries)['series'][0]['angles'];self.assertEqual([a['angle'] for a in angles],['Justice','Knowledge','Education']);self.assertTrue(all(a['review_required'] for a in angles))
 def test_missing_summary_never_fabricates_three_video_ideas(self):self.assertEqual(self.result()['series'][0]['angles'],[])
 def test_snapshot_does_not_change_inputs_or_call_providers(self):
  items=self.items();posts=[self.post()];before=copy.deepcopy((items,posts))
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):self.result(items,posts)
  self.assertEqual((items,posts),before)
 def test_endpoint_requires_owner_authentication(self):
  import server
  handler=object.__new__(server.Handler);handler.path='/api/book-series';handler.headers={};handler.local_host=lambda:True;handler.send=Mock()
  with patch.object(server.access,'valid',return_value=False),patch.object(server,'inventory',side_effect=AssertionError('Must authenticate')):handler.do_GET()
  self.assertEqual(handler.send.call_args.kwargs['status'],401)
if __name__=='__main__':unittest.main()
