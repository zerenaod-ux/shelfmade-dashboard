import unittest,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
import footage_director as f
class CachedPageTests(unittest.TestCase):
 def test_exhausted_cache_is_skipped_but_unknown_page_is_not(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'DB',Path(d)/'state.db'),patch.object(f,'CACHE',Path(d)/'cache'):
   with f.connect() as c:c.execute('insert into searches values (?,?,?)',('reading book',time.time(),json.dumps({'videos':[{'id':1,'duration':20,'url':'https://www.pexels.com/video/reading-book-1/'}]})))
   self.assertTrue(f.cached_page_exhausted('reading book',1,{'pexels-1'}));self.assertFalse(f.cached_page_exhausted('reading book',2,{'pexels-1'}));self.assertFalse(f.cached_page_exhausted('reading book',1,set()))
 def test_expired_cache_must_be_refreshed(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'DB',Path(d)/'state.db'),patch.object(f,'CACHE',Path(d)/'cache'):
   with f.connect() as c:c.execute('insert into searches values (?,?,?)',('reading book',time.time()-90000,json.dumps({'videos':[{'id':1,'duration':20,'url':'https://www.pexels.com/video/reading-book-1/'}]})))
   self.assertFalse(f.cached_page_exhausted('reading book',1,{'pexels-1'}))
if __name__=='__main__':unittest.main()
