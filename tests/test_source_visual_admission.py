import unittest
from unittest.mock import patch
import content_logic as c,footage_director as f
class SourceVisualAdmission(unittest.TestCase):
 def test_opaque_high_action_sentence_is_not_selected_as_a_lesson(self):
  rows=['You must never fold these several opaque entities into one.',
   'You must learn to examine every belief before repeating it.',
   'Knowledge requires patient attention to the reasons behind each claim.',
   'The wise person learns when to question an easy answer.',
   'If you seek knowledge you must first examine your assumptions.',
   'Never accept a confident explanation without learning its reasons first.',
   'People learn wisdom by giving every question their careful attention.',
   'A careful reader must question every claim before accepting its truth.',
   'Your wisdom grows when you practice patient reflection on new knowledge.',
   'We must examine the evidence before judging the nature of this claim.']
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
   script,evidence=c.build({'id':'1497','title':'The Republic','author':'Plato'},' '.join(rows))
  self.assertNotIn(rows[0],script['points']);self.assertNotEqual(rows[0],script['hook'])
  for passage in [script['hook'],*script['points']]:self.assertTrue(f.brief(passage)['keywords'])
  self.assertEqual(evidence['version'],'hook-first-v5-passage-editions')
 def test_source_without_visual_meaning_stops_before_voice_or_footage(self):
  text='You must never fold these several opaque entities into one. You should always align these several opaque entities in sequence. If you could only arrange these opaque entities differently today.'
  with patch.object(f,'acquire',side_effect=AssertionError('No downloads')),self.assertRaisesRegex(ValueError,'before narration'):
   c.build({'id':'999','title':'Opaque','author':'Author'},text)
