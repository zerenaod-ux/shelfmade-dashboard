import unittest,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
import footage_director as f

class CacheBudgetTests(unittest.TestCase):
 def test_later_cached_query_is_used_after_provider_allowance_is_spent(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);brief={'theme':'choice','subject':'theme','queries':['walking fork road','writing journal'],'keywords':['choice'],'reason':'A decision metaphor','chapter':'Decision'}
   videos=[{'id':i,'duration':30,'url':f'https://www.pexels.com/video/writing-journal-{i}/'} for i in range(1,5)]
   beat={'visual':brief};script={'title':'A new source','sections':[{'title':'Decision','narration':'Choose your response.'}]}
   def cached(query,page):return {'videos':videos} if query=='writing journal' and page==1 else None
   def download(video,selection,budget):return {'id':'pexels-'+str(video['id']),'sha256':str(video['id']),'creator':'Fixture','source_url':video['url'],'query':selection['query']}
   with patch.object(f,'DB',root/'footage.sqlite'),patch.object(f,'CACHE',root/'cache'),patch.object(f.media_runtime,'require_ready'),patch.object(f,'brief',return_value=brief),patch.object(f,'used_ids',return_value=set()),patch.object(f,'historical_hashes',return_value=set()),patch.object(f,'cached_page_exhausted',return_value=False),patch.object(f,'cached_search_page',side_effect=cached),patch.object(f,'search_allowance',return_value=1),patch.object(f,'download',side_effect=download),patch('scene_direction.plan',return_value=[beat,beat]),patch('scene_direction.receipt',return_value={}),patch.object(f,'search',return_value={'videos':[]}) as search:
    result=f.acquire(script,root)
   self.assertGreaterEqual(len(result),2);self.assertEqual(search.call_count,1)
   self.assertEqual(json.loads((root/'footage-selection.json').read_text())['searches'],1)
 def test_cache_miss_expiry_and_valid_page(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(f,'DB',Path(folder)/'state.sqlite'),patch.object(f,'CACHE',Path(folder)/'cache'):
   self.assertIsNone(f.cached_search_page('decision',1))
   with f.connect() as c:c.execute('insert into searches values (?,?,?)',('decision',time.time(),json.dumps({'videos':[]})))
   self.assertEqual(f.cached_search_page('decision'),{'videos':[]})
   with f.connect() as c:c.execute('update searches set created=?',(time.time()-90000,))
   self.assertIsNone(f.cached_search_page('decision'))
if __name__=='__main__':unittest.main()
