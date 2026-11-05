import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import footage_director as footage,visual_admission as admission,full_jobs

class VisualAdmission(unittest.TestCase):
 def test_mentorship_section_has_specific_modern_education_brief(self):
  text='Washington studied under an influential mentor. This educational lineage shaped his intellectual development through mentorship.'
  brief=footage.brief(text,'Educational Lineage Shapes Leaders')
  self.assertEqual(brief['theme'],'learning');self.assertEqual(brief['subject'],'education and mentorship')
  self.assertIn('teacher helping student',brief['queries'])
 def test_unknown_text_not_rescued_by_a_promising_title(self):
  with self.assertRaises(ValueError):admission.require({'sections':[{'title':'Education','narration':'Zqxv abcdef ghi.'}]})
 def test_every_chapter_must_be_filmable(self):
  script={'sections':[{'title':'Practice','narration':'Practice one simple habit at work.'},{'title':'Unclear','narration':'Zqxv abcdef ghi.'}]}
  with self.assertRaises(ValueError):admission.require(script)
 def test_cta_uses_explicit_previous_context(self):
  script={'sections':[{'title':'Lesson','narration':'A teacher helps a student learn.'},{'title':'cta','narration':'Subscribe for another episode.'}]}
  result=admission.require(script);self.assertEqual(result['chapters'],2);self.assertFalse(result['stock_availability_verified'])
 def test_invalid_visual_script_cannot_allocate_daily_job(self):
  script={'sections':[{'title':'Unknown','narration':'Zqxv abcdef ghi.'}]}
  with patch('local_voice.available',return_value=True),patch('cinematic_content.build',return_value=script),patch.object(full_jobs,'connect') as database:
   with self.assertRaises(ValueError):full_jobs.enqueue('fixture')
   database.assert_not_called()
 def test_actual_failed_book_now_passes_editorial_visual_coverage(self):
  path=Path(__file__).resolve().parents[1]/'full-generated/6eebf1b53ff949cc862e8eda0d34433b/script.json'
  result=admission.require(json.loads(path.read_text()));self.assertEqual(result['chapters'],7)
  self.assertTrue(result['owner_review_required']);self.assertFalse(result['source_accuracy_verified'])

if __name__=='__main__':unittest.main()
