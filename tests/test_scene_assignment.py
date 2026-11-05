import unittest
import cinematic_pipeline as cp
class SceneAssignmentTests(unittest.TestCase):
 def beat(self,subject='theme'):
  return {'chapter':0,'chapter_title':'Lesson','start':0 if subject=='theme' else 8,'unit':8,'narration_anchor':'Observe and learn','preferred_shot_role':'detail','visual':{'theme':'learning','subject':subject,'queries':['hands drawing diagram']}}
 def asset(self,ident,url,**kw):
  return {'id':ident,'duration':20,'themes':['learning'],'source_url':url,'query':'reading book',**kw}
 def test_general_scene_cannot_consume_only_concrete_match(self):
  result=cp.assign_fresh_scenes([self.beat(),self.beat('diagram')],[self.asset('specific','https://www.pexels.com/video/hands-drawing-diagram/'),self.asset('general','https://www.pexels.com/video/reading-book/')])
  self.assertEqual(result[(0,8)]['id'],'specific');self.assertEqual(result[(0,0)]['id'],'general')
 def test_insufficient_unique_matches_still_block(self):
  with self.assertRaisesRegex(ValueError,'no repeated'):cp.assign_fresh_scenes([self.beat(),self.beat('diagram')],[self.asset('one','https://www.pexels.com/video/hands-drawing-diagram/')])
 def test_explicit_subject_reservation_is_respected(self):
  with self.assertRaises(ValueError):cp.assign_fresh_scenes([self.beat()],[self.asset('one','https://www.pexels.com/video/reading-book/',visual_subject='diagram')])
if __name__=='__main__':unittest.main()
