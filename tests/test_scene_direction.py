import sys,unittest,tempfile,json,copy,sqlite3
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import scene_direction as d,cinematic_pipeline as cp,footage_director as f,creative_quality as q
class Tests(unittest.TestCase):
 def chapter(self):return {'index':0,'title':'Attention and response','narration':'Observe water moving in the forest stream. Control your response to the message on your phone.','start':0,'duration':12}
 def words(self):
  text=self.chapter()['narration'].split();return [{'text':word,'start':i*12/len(text),'end':(i+1)*12/len(text)} for i,word in enumerate(text)]
 def assets(self,theme='control',query='person reading message phone'):
  return [{'id':str(i),'provider':'Pexels','themes':[theme],'duration':20,'path':'test.mp4','description':'Illustrative '+theme,'tags':[theme],'query':query,'source_url':'https://www.pexels.com/video/'+query.replace(' ','-')+'-'+str(i),'shot_intent':f.query_role(query)} for i in range(12)]
 def test_timeline_covers_chapter_and_roles_progress(self):
  chapter=self.chapter();before=copy.deepcopy(chapter);beats=d.plan([chapter],self.words());self.assertEqual(len(beats),4);self.assertEqual(beats[0]['start'],0);self.assertAlmostEqual(beats[-1]['start']+beats[-1]['unit'],12);self.assertEqual([b['planned_intent'] for b in beats],['establish','detail','action','resolve']);self.assertEqual(chapter,before)
 def test_long_mindlore_scenes_reduce_unique_clip_demand_without_changing_default(self):
  chapter={'index':1,'title':'Learning','narration':'A student studies a book to understand the lesson.','start':0,'duration':337}
  self.assertEqual(len(d.plan([chapter])),43)
  beats=d.plan([chapter],long_scene_seconds=12)
  self.assertEqual(len(beats),29);self.assertAlmostEqual(beats[-1]['start']+beats[-1]['unit'],337,places=5)
 def test_exact_word_fragment_uses_its_own_theme(self):
  beats=d.plan([self.chapter()],self.words());self.assertEqual(beats[0]['visual']['theme'],'nature');self.assertEqual(beats[-1]['visual']['theme'],'control');self.assertTrue(all(b['narration_anchor'] for b in beats))
 def test_short_without_word_timing_has_explicit_estimated_context(self):
  beats=d.plan([self.chapter()],short_mode=True);self.assertTrue(all(b['context_basis']=='estimated_sentence' for b in beats));self.assertEqual(beats[-1]['visual']['theme'],'control')
 def test_unmatched_timing_is_never_claimed_as_exact_sentence_context(self):
  beats=d.plan([self.chapter()],[{'text':'Unmatched transcription','start':0}]);self.assertFalse(any(b['context_basis']=='timed_sentence' for b in beats))
 def test_unknown_meaning_stops_and_invalid_duration_stops(self):
  c={'index':0,'title':'Abstract','narration':'An entirely opaque proposition.','duration':9,'start':0}
  with self.assertRaises(ValueError):d.plan([c])
  c['duration']=0
  with self.assertRaises(ValueError):d.plan([c])
 def test_concrete_phone_passage_cannot_take_unrelated_control_scene(self):
  c={'index':0,'title':'Control','narration':'Control your response to the message on your phone.','start':0,'duration':6}
  with self.assertRaisesRegex(ValueError,'exhausted'):cp.plan_shots([c],self.assets(query='person walking busy city'))
  shots=cp.plan_shots([c],self.assets());self.assertEqual(len(shots),2);self.assertTrue(all(s['context_basis']=='estimated_sentence' for s in shots));self.assertEqual(len({s['asset_id'] for s in shots}),2)
 def test_plan_and_edit_share_identical_anchors_and_briefs(self):
  chapter=self.chapter();beats=d.plan([chapter],self.words());assets=self.assets()+[{**a,'id':'nature-'+a['id']} for a in self.assets('nature','forest stream rocks')]
  shots=cp.plan_shots([chapter],assets,self.words());self.assertEqual([s['narration_anchor'] for s in shots],[b['narration_anchor'] for b in beats]);self.assertEqual([s['visual_theme'] for s in shots],[b['visual']['theme'] for b in beats]);self.assertTrue(all(s['direction_version']==d.VERSION for s in shots))
 def test_planning_never_calls_network_or_changes_input(self):
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):receipt=d.receipt([self.chapter()],self.words(),d.plan([self.chapter()],self.words()))
  self.assertEqual(receipt['version'],d.VERSION);self.assertEqual(len(receipt['input_sha256']),64)
 def test_acquisition_uses_same_beat_counts_as_editing(self):
  chapter=self.chapter();words=self.words();counter=[0]
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'.render').mkdir();(root/'.render/word-timing.json').write_text(json.dumps({'words':words}))
   def search(query,page):
    rows=[]
    for _ in range(15):counter[0]+=1;rows.append({'id':counter[0],'duration':20,'url':'https://www.pexels.com/video/'+query.replace(' ','-')+'-'+str(counter[0])})
    return {'videos':rows}
   def download(video,selection,budget):return {'id':'pexels-'+str(video['id']),'duration':20,'sha256':str(video['id']),'query':selection['query'],'themes':[selection['theme']],'provider':'Pexels','path':'test.mp4','description':selection['reason'],'creator':'Test','source_url':video['url'],'shot_intent':f.query_role(selection['query'])}
   with patch.object(f,'BASE',root),patch.object(f,'DB',root/'state.db'),patch.object(f,'CACHE',root/'cache'),patch.object(f,'used_ids',return_value=set()),patch.object(f,'historical_hashes',return_value=set()),patch.object(f,'search',side_effect=search),patch.object(f,'download',side_effect=download):
    assets=f.acquire({'title':'Example','sections':[{'title':chapter['title'],'narration':chapter['narration']}]},root,chapters=[chapter]);stored=json.loads((root/'scene-direction.json').read_text());shots=cp.plan_shots([chapter],assets,words)
   self.assertEqual(len(stored['beats']),len(shots));self.assertEqual([s['visual_theme'] for s in shots],[b['visual']['theme'] for b in stored['beats']]);self.assertEqual([s['context_basis'] for s in shots],[b['context_basis'] for b in stored['beats']])
if __name__=='__main__':unittest.main()
