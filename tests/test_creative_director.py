import unittest,sys,copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import creative_director as d,creative_quality as q,cinematic_content,content_logic
class Tests(unittest.TestCase):
 def script(self):
  return {'title':'Learning','hook':'You learn knowledge by examining the reasons behind your beliefs.','thumbnail_headline':'QUESTION WHAT YOU KNOW','public_title':'Examine what you know','points':['Knowledge grows when people learn to examine their judgments carefully.','The wise person must learn to question a confident explanation.'],'source_evidence':[{'kind':'source passage','chapter':'Learning','excerpt':'You learn knowledge by examining the reasons behind your beliefs.','source_url':'https://www.gutenberg.org/ebooks/1497'}]}
 def rows(self):
  return ['You must learn to examine every belief before repeating it.','Knowledge requires patient attention to the reasons behind each claim.','The wise person learns when to question an easy answer.','If you seek knowledge you must first examine your assumptions.','Never accept a confident explanation without learning its reasons first.','People learn wisdom by giving every question their careful attention.']
 def test_exactly_five_distinct_candidates_and_deterministic_ranking(self):
  s=self.script();result=d.short(s,self.rows());receipt=result['creative_director'];self.assertEqual(len(receipt['candidates']),5);self.assertEqual(len({c['hook'] for c in receipt['candidates']}),5);self.assertEqual(d.short(s,self.rows()),result)
  selected=next(c for c in receipt['candidates'] if c['id']==receipt['selected_id']);self.assertEqual(selected['score'],max(c['score'] for c in receipt['candidates'] if c['eligible']));self.assertEqual(selected['hook'],result['hook']);self.assertTrue(q.script_review(result,result['source_evidence'])['director'])
 def test_short_never_invents_a_source_sentence_or_rewrites_lessons(self):
  s=self.script();original=copy.deepcopy(s);result=d.short(s,self.rows());self.assertEqual(s,original);self.assertIn(result['hook'],[s['hook'],*self.rows()]);self.assertEqual(result['points'],s['points']);self.assertTrue(any(q.norm(result['hook']) in q.norm(e['excerpt']) for e in result['source_evidence']))
 def test_insufficient_choices_stop_without_filler(self):
  with self.assertRaisesRegex(ValueError,'five distinct'):d.short(self.script(),self.rows()[:2])
 def test_sensational_candidates_cannot_win(self):
  s=self.script();s['hook']='Guaranteed wisdom will cure every problem in your life instantly.';result=d.short(s,self.rows());bad=result['creative_director']['candidates'][0];self.assertFalse(bad['eligible']);self.assertNotEqual(result['creative_director']['selected_id'],1)
 def test_all_unfilmable_candidates_stop(self):
  with patch.object(d,'brief_for',return_value=None),self.assertRaisesRegex(ValueError,'all five'):d.short(self.script(),self.rows())
 def test_selection_metadata_must_agree_with_script(self):
  result=d.short(self.script(),self.rows());result['creative_director']['selected_id']=999;self.assertTrue(q.script_review(result,result['source_evidence'])['errors'])
 def test_ranking_never_calls_network_or_fetches_assets(self):
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')),patch.object(d.footage_director,'acquire',side_effect=AssertionError('No footage acquisition')):result=d.short(self.script(),self.rows())
  self.assertEqual(len(result['creative_director']['scene_plan']),3);self.assertTrue(result['creative_director']['scene_plan'][0]['queries'])
 def test_full_candidates_are_existing_editorial_text_and_pay_off(self):
  script=cinematic_content.build('1497');receipt=script['creative_director'];self.assertEqual(len(receipt['candidates']),5);self.assertTrue(script['sections'][0]['narration'].startswith(script['hook']));self.assertFalse(q.script_review(script,script['source_evidence'],True)['errors']);self.assertEqual(script['sections'][script['opening_payoff']['section']]['title'],script['opening_payoff']['chapter'])
 def test_short_integration_binds_selected_evidence(self):
  text=' '.join(self.rows()+self.script()['points']);script,evidence=content_logic.build({'id':'1497','title':'The Republic','author':'Plato'},text);self.assertEqual(evidence['hook'],script['hook']);self.assertEqual(len(evidence['creative_director']['candidates']),5);self.assertFalse(q.script_review(script,script['source_evidence'])['errors'])
if __name__=='__main__':unittest.main()
