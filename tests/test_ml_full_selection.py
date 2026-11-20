import json,tempfile,unittest
from pathlib import Path
from ml_full_selection import select_scripts

class FullSelectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for sid,title in [('used','Old video'),('fresh','Fresh explanation'),('copy','OLD VIDEO!'),('next','Another explanation')]:
   (self.root/(sid+'.json')).write_text(json.dumps({'story_v2':True,'public_title':title}))
  (self.root/'legacy.json').write_text(json.dumps({'public_title':'Legacy'}))
 def tearDown(self):self.tmp.cleanup()
 def test_daily_selection_uses_fresh_series_and_not_duplicate_titles(self):
  self.assertEqual(select_scripts(self.root,['used'],['fresh','used','fresh']),['fresh','next'])
 def test_explicit_replay_cannot_bypass_built_history(self):
  with self.assertRaisesRegex(ValueError,'already built'):select_scripts(self.root,['used'],[],'used')
 def test_requested_duplicate_title_is_also_blocked(self):
  with self.assertRaisesRegex(ValueError,'repeats'):select_scripts(self.root,['used'],[],'copy')
 def test_missing_or_legacy_request_does_not_silently_build_something_else(self):
  for sid in ['absent','legacy']:
   with self.assertRaises(ValueError):select_scripts(self.root,[],[],sid)
 def test_approved_titles_are_not_rebuilt(self):
  self.assertNotIn('fresh',select_scripts(self.root,[],[],known_titles=['FRESH EXPLANATION!']))
 def test_schedule_cannot_read_old_push_trigger(self):
  workflow=Path('.github/workflows/mindlore-2d.yml').read_text()
  self.assertIn("github.event_name == 'push'",workflow)
  self.assertIn('if [ "$ML2D_READ_TRIGGER" = "1" ]',workflow)
