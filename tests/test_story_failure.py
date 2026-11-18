import tempfile,unittest
from pathlib import Path
import story_failure as f
class StoryFailureTests(unittest.TestCase):
 def test_outage_is_not_content_failure(self):
  for text in ['urllib.error.HTTPError: HTTP Error 503: Service Unavailable','TimeoutError: timed out','HTTP Error 429: capacity']:
   self.assertTrue(f.temporary(text))
  for text in ['ValueError: script facts do not match','HTTP Error 404: missing source','HTTP Error 403: forbidden']:
   self.assertFalse(f.temporary(text))
 def test_diagnostics_keep_root_trace_and_no_decision(self):
  with tempfile.TemporaryDirectory() as p:
   self.assertTrue(f.record(p,'test-story','worker.py fetch_source\nHTTP Error 503: Service Unavailable'))
   self.assertIn('fetch_source',(Path(p)/'test-story.log').read_text())
   self.assertIn('false',(Path(p)/'test-story.json').read_text())
if __name__=='__main__':unittest.main()
