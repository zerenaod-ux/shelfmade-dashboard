import unittest,tempfile,json,hashlib,sys
from pathlib import Path
from unittest.mock import patch
import retained_sources as r
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'generator'))
import booksummary
class RetainedSources(unittest.TestCase):
 def fixture(self,root):
  data=b'*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\nOriginal text.\n*** END OF THE PROJECT GUTENBERG EBOOK TEST ***'
  (root/'123.txt').write_bytes(data);entry={'id':'123','file':'123.txt','canonical_url':'https://www.gutenberg.org/ebooks/123','source_url':'https://www.gutenberg.org/cache/epub/123/pg123.txt','sha256':hashlib.sha256(data).hexdigest()};(root/'catalogue.json').write_text(json.dumps([entry]));return entry
 def test_verified_text_is_used_without_network(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'ROOT',Path(d)),patch.object(booksummary.urllib.request,'urlopen',side_effect=AssertionError('No network')):
   self.fixture(Path(d));self.assertIn('Original text.',booksummary.fetch_book('123'));self.assertIsNone(r.read('456'))
 def test_changed_text_blocks_instead_of_silent_online_fallback(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'ROOT',Path(d)),patch.object(booksummary.urllib.request,'urlopen') as network:
   self.fixture(Path(d));(Path(d)/'123.txt').write_text('changed')
   with self.assertRaisesRegex(ValueError,'changed'):booksummary.fetch_book('123')
   network.assert_not_called()
 def test_identity_change_is_rejected(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'ROOT',Path(d)):
   entry=self.fixture(Path(d));entry['file']='../other.txt';(Path(d)/'catalogue.json').write_text(json.dumps([entry]))
   with self.assertRaises(ValueError):r.read('123')
if __name__=='__main__':unittest.main()
