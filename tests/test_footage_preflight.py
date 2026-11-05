import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import footage_preflight as p,footage_director as f
from generation_recovery import RecoverableGenerationError,transient

class Preflight(unittest.TestCase):
 def run_plan(self,folder,groups,payload):
  directions=[{'visual':{'theme':theme,'subject':'theme','queries':[query],'keywords':[theme]}} for theme,query in groups]
  script={'sections':[{'title':'Lesson','narration':'Choose your response and learn with care.'}]}
  with patch.object(p.scene_direction,'plan',return_value=directions),patch.object(f,'used_ids',return_value=set()),patch.object(f,'cached_page_exhausted',return_value=False),patch.object(f,'cached_search_page',side_effect=lambda q,page:payload(q) if page==1 else {'videos':[]}),patch.object(f,'invalid_cached_asset',return_value=False),patch.object(f,'search') as search:
   result=p.check(script,folder);search.assert_not_called();return result
 def video(self,id):return {'id':id,'duration':20,'url':f'https://www.pexels.com/video/writing-library-{id}/','video_files':[{'file_type':'video/mp4','width':1280,'height':720}]}
 def test_cached_candidate_plan_passes_before_narration(self):
  with tempfile.TemporaryDirectory() as folder:
   result=self.run_plan(Path(folder),[('learning','writing journal')],lambda q:{'videos':[self.video(1)]})
   self.assertEqual(result['state'],'passed');self.assertEqual(result['provider_searches'],0);self.assertTrue(result['distinct_assignment']);self.assertFalse((Path(folder)/'.render/chapter_00.wav').exists())
 def test_overlapping_themes_cannot_double_count_one_clip(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaisesRegex(RecoverableGenerationError,'share too few'):self.run_plan(Path(folder),[('learning','writing journal'),('choice','library')],lambda q:{'videos':[self.video(1)]})
 def test_matching_reserves_scarce_candidate_for_later_theme(self):
  with tempfile.TemporaryDirectory() as folder:
   result=self.run_plan(Path(folder),[('learning','writing journal'),('choice','library')],lambda q:{'videos':[self.video(1),self.video(2)] if q=='writing journal' else [self.video(1)]})
   self.assertTrue(result['distinct_assignment'])
 def test_missing_footage_is_bounded_recoverable_generation_only(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(RecoverableGenerationError) as error:self.run_plan(Path(folder),[('learning','writing journal')],lambda q:{'videos':[]})
   self.assertTrue(transient(error.exception));self.assertEqual(json.loads((Path(folder)/'footage-preflight.json').read_text())['state'],'waiting_for_footage')
 def test_provider_search_continues_after_four_exhausted_cache_pages(self):
  with tempfile.TemporaryDirectory() as folder:
   calls=[]
   def search(query,page):
    calls.append((query,page));return {'videos':[self.video(page*10+i) for i in range(3)]}
   script={'brand':'mindlore','format':'full','sections':[{'title':'Lesson','narration':'Choose your response and learn with care.'}]}
   directions=[{'visual':{'theme':'learning','subject':'theme','queries':['writing journal'],'keywords':['learning']}}]
   with patch.object(p.scene_direction,'plan',return_value=directions),patch.object(f,'used_ids',return_value=set()),patch.object(f,'cached_page_exhausted',return_value=False),patch.object(f,'cached_search_page',side_effect=lambda q,page:{'videos':[]} if page<=4 else None),patch.object(f,'invalid_cached_asset',return_value=False),patch.object(f,'search',side_effect=search):
    result=p.check(script,Path(folder))
   self.assertTrue(result['distinct_assignment']);self.assertTrue(any(page==5 for _,page in calls));self.assertLessEqual(result['provider_searches'],f.MAX_SEARCHES)
if __name__=='__main__':unittest.main()

class SharedCandidateRegression(unittest.TestCase):
 run_plan=Preflight.run_plan
 video=Preflight.video
 def test_four_related_groups_inspect_beyond_same_first_three_results(self):
  # Four distinct clips exist, but the old required+2 truncation kept only
  # the same first three in every group and incorrectly rejected the plan.
  with tempfile.TemporaryDirectory() as folder:
   groups=[(theme,'writing journal') for theme in ('learning','choice','practice','time')]
   result=self.run_plan(Path(folder),groups,lambda q:{'videos':[self.video(i) for i in range(1,5)]})
   self.assertTrue(result['distinct_assignment']);self.assertEqual(result['provider_searches'],0)
 def test_more_candidates_still_cannot_replace_freshness(self):
  with tempfile.TemporaryDirectory() as folder:
   groups=[(theme,'writing journal') for theme in ('learning','choice','practice','time')]
   with self.assertRaises(RecoverableGenerationError):self.run_plan(Path(folder),groups,lambda q:{'videos':[self.video(i) for i in range(1,4)]})
