"""No network or renders: regression coverage for the October 16 blockers."""
import sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import content_logic,opening_design,creative_quality as cq,footage_director as f
class Tests(unittest.TestCase):
 def test_mortality_quote_has_grounded_cover(self):
  hook='The perpetual work of your life is but to lay the foundation of death'
  line=opening_design.short_headline(hook)
  self.assertEqual(line,'WHAT DOES DEATH TEACH US?');self.assertTrue(cq.related(line,hook))
  self.assertFalse(cq.script_review({'hook':hook,'thumbnail_headline':line,'public_title':hook,'points':['Knowledge can guide choices when people learn to examine their judgments.']},[{'kind':'source passage','excerpt':hook,'source_url':'https://www.gutenberg.org/ebooks/3600'}])['errors'])
 def test_search_budget_follows_scene_demand_and_reserves_later_themes(self):
  self.assertGreaterEqual(f.search_allowance(30,[39,4,4,3,3,2]),18)
  budget=30
  demands=[39,4,4,3,3,2]
  for i in range(len(demands)):
   allocation=f.search_allowance(budget,demands[i:]);self.assertGreater(allocation,0);self.assertLessEqual(allocation,budget);budget-=allocation
  self.assertEqual(budget,0)
 def test_learning_has_relevant_query_variety(self):
  brief=f.brief('Knowledge and education help us understand reality.','Learning')
  self.assertGreaterEqual(len(brief['queries']),6);self.assertEqual(len(brief['queries']),len(set(brief['queries'])))
 def acquire(self,search,required=8,searches=30,used=None,download=None):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
  script={'title':'Learning','sections':[{'title':'Learning','narration':'Knowledge teaches us to learn.'}]}
  chapter=[{'duration':required*3,'start':0}]
  def fetch(video,selection,budget):
   return {'id':'pexels-'+str(video['id']),'sha256':str(video['id']),'creator':'Contributor','source_url':video['url'],'query':selection['query']}
  patches=[patch.object(f,'BASE',root),patch.object(f,'DB',root/'state.db'),patch.object(f,'CACHE',root/'cache'),patch.object(f,'used_ids',return_value=used or set()),patch.object(f,'historical_hashes',return_value=set()),patch.object(f,'brief',return_value={'theme':'learning','subject':'theme','queries':['reading book','writing notes','examining object'],'keywords':['knowledge']}),patch.object(f,'search',side_effect=search),patch.object(f,'download',side_effect=download or fetch),patch.object(f,'MAX_SEARCHES',searches)]
  for p in patches:p.start();self.addCleanup(p.stop)
  return f.acquire(script,root,chapters=chapter)
 def video(self,id):return {'id':id,'duration':20,'url':'https://www.pexels.com/video/reading-book-'+str(id)+'/'}
 def test_rich_matching_search_fills_exhausted_queries(self):
  calls=[]
  def search(query,page):
   calls.append((query,page));return {'videos':[self.video(i) for i in range(1,15)] if query=='reading book' and page==1 else []}
  assets=self.acquire(search);self.assertEqual(len(assets),8);self.assertEqual(len({a['id'] for a in assets}),len(assets));self.assertLessEqual(len(calls),30)
 def test_pages_expand_when_first_page_contains_only_used_clips(self):
  def search(query,page):return {'videos':[self.video(i) for i in (range(1,12) if page==1 else range(12,24))] if query=='reading book' else []}
  assets=self.acquire(search,used={'pexels-'+str(i) for i in range(1,12)})
  self.assertTrue(all(int(a['id'].split('-')[1])>=12 for a in assets))
 def test_budget_does_not_relax_reuse_or_relevance(self):
  calls=[]
  def search(query,page):calls.append((query,page));return {'videos':[self.video(i) for i in range(1,12)]}
  with self.assertRaisesRegex(ValueError,'Found 0 of 8'):self.acquire(search,searches=2,used={'pexels-'+str(i) for i in range(1,12)})
  self.assertLessEqual(len(calls),2)
 def test_rejected_download_releases_its_reservation(self):
  def search(query,page):return {'videos':[self.video(1)] if query=='reading book' else []}
  with self.assertRaises(ValueError):self.acquire(search,searches=3,download=lambda *args:None)
  with f.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM reserved').fetchone()[0],0)
if __name__=='__main__':unittest.main()
