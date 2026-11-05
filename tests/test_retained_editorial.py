import json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import retained_editorial,retained_sources,cinematic_content,visual_admission

BASE=Path(__file__).resolve().parents[1]
class OriginalEvidence(unittest.TestCase):
 def setUp(self):self.script=json.loads((BASE/'cinematic-scripts/23347.json').read_text())
 def test_each_new_chapter_has_exact_original_evidence(self):
  evidence=retained_editorial.evidence(self.script,'23347')
  self.assertEqual(len(evidence),7);self.assertTrue(all(e['exact_passage_verified'] for e in evidence))
 def test_missing_chapter_evidence_stops_admission(self):
  self.script['source_passages'].pop()
  with self.assertRaisesRegex(ValueError,'Each editorial chapter'):retained_editorial.evidence(self.script,'23347')
 def test_changed_excerpt_stops_admission(self):
  self.script['source_passages'][1]['excerpt']='This invented source passage never existed in this original book.'
  with self.assertRaisesRegex(ValueError,'absent'):retained_editorial.evidence(self.script,'23347')
 def test_wrong_source_identity_or_pin_stops_admission(self):
  with self.assertRaisesRegex(ValueError,'identity'):retained_editorial.evidence(self.script,'12811')
  self.script['retained_source_sha256']='wrong'
  with self.assertRaisesRegex(ValueError,'different original'):retained_editorial.evidence(self.script,'23347')
 def test_malformed_evidence_has_an_actionable_error(self):
  for bad in [None,[None],[{'section':True,'excerpt':'invalid'}]]:
   self.script['source_passages']=bad
   with self.assertRaisesRegex(ValueError,'invalid structure'):retained_editorial.evidence(self.script,'23347')
 def test_changed_original_stops_admission(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);catalog=[e for e in json.loads((retained_sources.ROOT/'catalogue.json').read_text()) if e['id']=='23347']
   (root/'catalogue.json').write_text(json.dumps(catalog));(root/'23347.txt').write_text('changed')
   with patch.object(retained_sources,'ROOT',root),self.assertRaisesRegex(ValueError,'changed or is missing'):retained_editorial.evidence(self.script,'23347')
 def test_new_script_passes_creative_and_visual_checks_without_rendering(self):
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
   script=cinematic_content.build('23347');coverage=visual_admission.require(script)
  self.assertEqual(coverage['chapters'],7);self.assertFalse(coverage['stock_availability_verified'])
  self.assertTrue(850<=sum(len(s['narration'].split()) for s in script['sections'])<=1300)
  self.assertTrue(any(e.get('exact_passage_verified') for e in script['source_evidence']))

 def test_all_retained_editorial_scripts_pass_before_any_media_work(self):
  for path in (BASE/'cinematic-scripts').glob('*.json'):
   raw=json.loads(path.read_text())
   if 'source_passages' not in raw:continue
   with self.subTest(book=path.stem),patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
    evidence=retained_editorial.evidence(raw,path.stem)
    script=cinematic_content.build(path.stem)
    self.assertEqual(len(evidence),len(raw['sections']))
    self.assertTrue(visual_admission.require(script)['owner_review_required'])
 def test_wrong_canonical_link_blocks_editorial(self):
  self.script['source_url']='https://www.gutenberg.org/ebooks/12811'
  with self.assertRaisesRegex(ValueError,'source link'):retained_editorial.evidence(self.script,'23347')
 def test_short_curated_script_stops_before_creative_or_rendering(self):
  short={'sections':[{'title':'Too short','narration':'Practice a useful habit.'}]}
  with patch.object(cinematic_content,'_build',return_value=short),self.assertRaisesRegex(ValueError,'5–8 minute'):
   cinematic_content.build('fixture')
