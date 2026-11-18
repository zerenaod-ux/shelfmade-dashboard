"""No AI calls or video generation: dialogue policy and encoded-media regressions."""
import importlib.util,json,sys,tempfile,unittest,wave,os
from pathlib import Path
from unittest.mock import patch,Mock
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'doodles_engine'))
import dialogue_quality as q
def story():
    line="I moved your chair because you keep leaving snacks on mine."
    return {'id':'fixture-story','title':'Why You Moved My Chair','concept':'chair','caption':'fixture','dialogue_policy':q.POLICY,
      'dialogue_review':{'complete':True,'natural':True,'spoken':8,'ending':8},
      'shots':[{'scene':'A desk with a plain mug.','focus':'both','lines':[{'who':'leo','feel':'amused','beat':'quick','text':line},{'who':'mia','feel':'deadpan','beat':'normal','text':line}]} for _ in range(6)]}
class DialogueTests(unittest.TestCase):
 def test_complete_reviewed_story_passes(self):
    self.assertEqual(q.story_errors(story(),True),[])
 def test_dangling_loop_and_old_micro_story_are_rejected(self):
    s=story();s['shots'][-1]['lines'][-1]['text']='So what if I just...'
    self.assertTrue(any('dangling' in e for e in q.story_errors(s)))
    s=story();s['shots']=[dict(sh,lines=[sh['lines'][0]]) for sh in s['shots']]
    self.assertTrue(any('spoken words' in e for e in q.story_errors(s)))
 def test_unavailable_or_failed_editor_is_not_a_pass(self):
    for review in [{},{'complete':False,'natural':True,'spoken':8,'ending':8},{'complete':True,'natural':True,'spoken':float('nan'),'ending':8}]:
     s=story();s['dialogue_review']=review;self.assertTrue(q.story_errors(s,True))
 def test_duration_boundaries_and_reaction(self):
    q.require_duration(40,39);q.require_duration(70,69)
    for seconds in (39.9,70.1,float('nan')):
     with self.assertRaises(ValueError):q.require_duration(seconds)
    with self.assertRaises(ValueError):q.require_duration(50,49.8)
 def test_encoded_video_requires_both_tracks_and_full_ending(self):
    with tempfile.TemporaryDirectory() as p:
     media={'format':{'duration':'52'},'streams':[{'codec_type':'video','duration':'52'},{'codec_type':'audio','duration':'52'}]}
     with patch.object(q.subprocess,'check_output',return_value=json.dumps(media).encode()),patch.object(q.subprocess,'run') as decode:
      report=q.verify_encoded(p,52,50.9);self.assertGreater(report['reaction_seconds'],.7);decode.assert_called_once()
     media['streams'][1]['duration']='50'
     with patch.object(q.subprocess,'check_output',return_value=json.dumps(media).encode()):
      with self.assertRaises(ValueError):q.verify_encoded(p,52,50.9)
 def test_writer_requires_real_resolution_review_even_for_one_candidate(self):
    import types
    spec=importlib.util.spec_from_file_location('dialogue_writer_under_test',ROOT/'doodles_engine/story_writer.py')
    writer=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'stories':types.SimpleNamespace(STORIES=[])}):
     spec.loader.exec_module(writer)
    good={'scores':[{'i':0,'spoken':8,'ending':8,'complete':True,'natural':True}],'best':0,'why':'A resolved exchange'}
    with patch.object(writer,'gemini',return_value=json.dumps(good)):
     self.assertEqual(writer.judge([story()])[0],0)
    with patch.object(writer,'gemini',side_effect=RuntimeError('provider unavailable')):
     self.assertEqual(writer.judge([story()]),(None,None))
    s=story();s['shots'][0]['lines'][0]['text']='I moved your chair. You left snacks.'
    with patch.object(writer,'_recent_scripts',return_value=[]):
     self.assertTrue(writer.valid(s,set(),'complete'))
 def test_writer_repairs_rejected_candidate_and_retains_diagnostics(self):
    import types
    spec=importlib.util.spec_from_file_location('dialogue_repair_under_test',ROOT/'doodles_engine/story_writer.py')
    writer=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'stories':types.SimpleNamespace(STORIES=[])}):spec.loader.exec_module(writer)
    good=story();good['shots'][0]['lines'][0]['text']='I moved your chair. You left snacks.'
    bad=json.loads(json.dumps(good));bad['shots'][-1]['lines'][-1]['text']='But what if I...'
    score={'scores':[{'i':0,'spoken':8,'ending':8,'complete':True,'natural':True}],'best':0,'why':'Complete conversation'}
    with tempfile.TemporaryDirectory() as folder,patch.object(writer,'ATTEMPTS',Path(folder)),patch.object(writer,'BESTOF',1),patch.object(writer,'_recent_scripts',return_value=[]),patch.object(writer,'gemini',side_effect=[json.dumps(bad),json.dumps(good),json.dumps(score)]) as call:
     result=writer.pick_best('a chair disagreement',set(),'complete','')
     self.assertEqual(result['id'],good['id']);self.assertEqual(call.call_count,3)
     self.assertEqual(len(list(Path(folder).glob('*.json'))),2)
 def test_final_quiet_audio_is_preserved_without_padding_to_target(self):
    import render as renderer
    with tempfile.TemporaryDirectory() as p,patch.dict(os.environ,{'DOODLES_SFX':'0'}),patch.object(renderer,'LAND',False):
     p=Path(p);(p/'story.json').write_text(json.dumps(story()))
     samples=(np.sin(np.arange(4*24000)*.1)*.04).astype('float32')
     quiet=samples.copy();quiet[-12000:]*=.08
     for si in range(6):
      for li in range(2):
       a=quiet if si==5 and li==1 else samples
       with wave.open(str(p/f'line_{si:02d}_{li:02d}.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes((a*32767).astype('<i2').tobytes())
     _,timeline,total,_,_=renderer.build(p)
     self.assertAlmostEqual(timeline[-1]['lines'][-1]['end']-timeline[-1]['lines'][-1]['start'],4,places=3)
     self.assertGreater(total-timeline[-1]['lines'][-1]['end'],.8)
     with wave.open(str(p/'line_00_00.wav'),'wb') as w:
      w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(bytes(24000*2))
     # A later shortening changes measured duration; no automatic silent padding is added.
     self.assertLess(renderer.build(p)[2],total)
if __name__=='__main__':unittest.main()
