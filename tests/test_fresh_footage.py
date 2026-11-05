import unittest,tempfile,sys,json,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import footage_director as f,cinematic_pipeline as cp
class Tests(unittest.TestCase):
 def test_concrete_brief_and_unknown_stop(self):
  self.assertEqual(f.brief('Control your response to anger.','An idea')['theme'],'control')
  with self.assertRaises(ValueError):f.brief('An entirely abstract proposition.','Unclear')
 def test_reject_search_homonyms(self):
  self.assertFalse(f.metadata_match({'url':'https://www.pexels.com/video/ambulance-responding-123/'},'person responding'))
  self.assertFalse(f.metadata_match({'url':'https://www.pexels.com/video/pre-concert-scene-123/'},'person thinking window'))
  self.assertTrue(f.metadata_match({'url':'https://www.pexels.com/video/woman-writing-in-notebook-123/'},'person writing journal reflection'))
 def test_no_cross_video_reuse(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'DB',Path(d)/'state.db'),patch.object(f,'CACHE',Path(d)/'cache'):
   f.commit(d,[{'id':'pexels-1'}]);self.assertIn('pexels-1',f.used_ids())
   with f.connect() as c:c.execute('insert into reserved values (?,?,?)',('pexels-2','other',time.time()+60))
   self.assertIn('pexels-2',f.used_ids('mine'));self.assertNotIn('pexels-2',f.used_ids('other'))
 def test_no_repeats_or_unrelated_fallback(self):
  chapter={'index':0,'title':'Control','narration':'Control your response.','start':0,'duration':9}
  a=[{'id':str(i),'provider':'Pexels','themes':['control'],'duration':20,'path':'test.mp4','description':'A response','tags':['control']} for i in range(3)]
  shots=cp.plan_shots([chapter],a);self.assertEqual(len(shots),3);self.assertEqual(len({s['asset_id'] for s in shots}),3)
  with self.assertRaisesRegex(ValueError,'exhausted'):cp.plan_shots([chapter],a[:1])
  a[0]['themes']=['nature']
  with self.assertRaisesRegex(ValueError,'exhausted'):cp.plan_shots([chapter],a)
 def test_completed_manifest_excludes_even_if_commit_interrupted(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'BASE',Path(d)),patch.object(f,'DB',Path(d)/'state.db'),patch.object(f,'CACHE',Path(d)/'cache'):
   p=Path(d)/'full-generated/example';p.mkdir(parents=True);(p/'POST_THIS.txt').write_text('Done');(p/'footage-selection.json').write_text(json.dumps({'assets':[{'id':'pexels-100'}]}));self.assertIn('pexels-100',f.used_ids())
if __name__=='__main__':unittest.main()

class EditorialBriefRegressions(unittest.TestCase):
 def test_carving_is_filmable_without_generic_life_fallback(self):
  b=f.brief('You must carve nothing but what has life','point2')
  self.assertEqual(b['theme'],'craft');self.assertEqual(b['subject'],'carving and sculpture')
  self.assertIn('carve',b['keywords']);self.assertTrue(all('carv' in q or 'sculpt' in q for q in b['queries']))
 def test_seneca_benefit_anchors_help_not_literal_violence(self):
  b=f.brief('A man does not save your life who does not kill you; nor does he confer a benefit, but merely gives you your discharge','point2')
  self.assertEqual(b['theme'],'community');self.assertEqual(b['subject'],'practical help')
  self.assertIn('benefit',b['keywords']);self.assertTrue(b['review_required'])
 def test_book_title_cannot_invent_narration_meaning(self):
  with self.assertRaises(ValueError):f.brief('An entirely opaque proposition.','carving benefit','Craft and Community')
