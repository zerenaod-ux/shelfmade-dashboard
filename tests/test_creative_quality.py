import unittest,sys,tempfile,json,copy,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import creative_quality as q,cinematic_content as content,cinematic_pipeline as cinema,quality,opening_design,content_logic,short_motion
class Creative(unittest.TestCase):
 def fixture(self):
  s={'hook':'Who controls your response to an insult?','thumbnail_headline':'CHOOSE YOUR RESPONSE','public_title':'Choose your response','sections':[{'title':'Opening','narration':'Who controls your response to an insult? Consider a familiar disagreement.'},{'title':'The response','narration':'Control your response to an insult by examining your judgment.'}],'opening_payoff':{'section':1,'chapter':'The response'}}
  e=[{'chapter':'Response','kind':'local summary','excerpt':'Control your response.','source_url':'https://www.gutenberg.org/ebooks/45109'}]
  return s,e
 def test_concrete_passage_overrides_generic_theme(self):
  import footage_director as f
  brief=f.brief('An insult arrives in a message. Choose your response.','Control')
  self.assertEqual(brief['theme'],'control');self.assertEqual(brief['queries'][0],'person reading message phone')
  self.assertEqual(f.brief('Notice water moving in a forest stream.','Nature')['subject'],'forest attention')
 def test_pair_and_payoff_are_checked(self):
  s,e=self.fixture();self.assertFalse(q.script_review(s,e,True)['errors'])
  s['thumbnail_headline']='GET RICH INSTANTLY';self.assertTrue(q.script_review(s,e,True)['errors'])
  s,e=self.fixture();s['sections'][1]['narration']='Trees stand beside the lake.';self.assertTrue(q.script_review(s,e,True)['errors'])
 def test_source_and_repeated_lessons_stop(self):
  s,e=self.fixture();self.assertTrue(q.script_review(s,[],True)['errors'])
  s['sections'].append(s['sections'][1].copy());self.assertTrue(q.script_review(s,e,True)['errors'])
  s,e=self.fixture();e[0]['kind']='source passage';self.assertTrue(q.script_review(s,e)['errors'])
 def test_catalog_has_content_specific_openings_and_evidence(self):
  supported=content.available_books();self.assertGreater(len(supported),10);scenes=set()
  for b in supported:
   s=content.build(b['id']);self.assertFalse(q.script_review(s,s['source_evidence'],True)['errors']);self.assertTrue(s['opening_payoff']['chapter']);scenes.add(s['sections'][0]['narration'])
   self.assertNotIn('Start with a moment you recognize: something happens',s['sections'][0]['narration'])
  self.assertEqual(len(scenes),len(supported))
 def test_scene_coverage_repeats_and_theme_mismatch(self):
  s,e=self.fixture();report=q.script_review(s,e,True)
  chapters=[{'index':0,'title':'Control','narration':'Control your response to anger.','start':0,'duration':6}]
  assets=[{'id':str(i),'provider':'Pexels','themes':['control'],'duration':20,'path':'test.mp4','description':'Illustrative control','tags':['control'],'source_url':'https://www.pexels.com/video/'+str(i)} for i in range(2)]
  shots=cinema.plan_shots(chapters,assets);self.assertEqual(q.scene_review(report,shots,chapters,assets)['state'],'checked')
  bad=copy.deepcopy(shots);bad[1]['asset_id']=bad[0]['asset_id'];self.assertTrue(q.scene_review(report,bad,chapters,assets)['errors'])
  bad=copy.deepcopy(shots);bad[1]['start']+=1;self.assertTrue(q.scene_review(report,bad,chapters,assets)['errors'])
  bad=copy.deepcopy(shots);bad[0]['visual_theme']='nature';self.assertTrue(q.scene_review(report,bad,chapters,assets)['errors'])
 def test_sealed_inputs_change_invalidates_review(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   for name in ('script.json','content-review.json','storyboard.json','cover.jpg'):(root/name).write_text('{}')
   report={'version':q.VERSION,'state':'checked','errors':[]};q.seal(root,report,'cover.jpg');self.assertTrue(q.verified(root))
   (root/'cover.jpg').write_text('changed');self.assertFalse(q.verified(root))
 def test_incomplete_creative_receipt_cannot_be_approved(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'final.mp4').write_bytes(b'video');(root/'POST_THIS.txt').write_text('Caption');(root/'script.json').write_text(json.dumps({'creative_policy':q.VERSION}))
   class Result:stdout=json.dumps({'format':{'duration':'30'},'streams':[{'codec_type':'video','width':1080,'height':1920},{'codec_type':'audio'}]})
   with patch.object(quality,'CACHE',root/'cache'),patch.object(quality.subprocess,'run',return_value=Result()):
    result=quality.inspect(root);self.assertFalse(result['can_approve']);self.assertEqual(result['creative']['state'],'needs_attention')
 def test_short_cover_uses_spoken_hook_and_transitions_preserve_timeline(self):
  self.assertEqual(opening_design.short_headline('Despite disappointment I determined that I would learn something anyway.'),'LEARN THROUGH THE SETBACK')
  script={'title':'Control','hook':'Who controls your response to an insult?','points':['Control your response.'],'thumbnail_headline':'CHOOSE YOUR RESPONSE','public_title':'Choose your response'}
  script['source_evidence']=self.fixture()[1]
  segments=[('hook',script['hook'],4,'query'),('point1','Control your response.',4,'query'),('cta','Follow ShelfMade.',2,'query')]
  assets=[{'id':str(i),'provider':'Pexels','themes':['control'],'duration':20,'path':'test.mp4','description':'Illustrative control','tags':['control'],'query':'person reading message phone','source_url':'https://www.pexels.com/video/person-reading-message-phone-'+str(i)} for i in range(5)]
  from PIL import Image
  with tempfile.TemporaryDirectory() as temp,patch('footage_director.acquire',return_value=assets),patch.object(cinema,'run') as run,patch.object(opening_design,'footage_frame',return_value=Image.new('RGB',(1080,1920))) as frame:
   import render_readiness as readiness
   signature=short_motion.segment_signature([(kind,text,None,duration) for kind,text,duration,query in segments])
   (Path(temp)/'render-readiness.json').write_text(json.dumps({'state':'passed','stage':'short_audio_checked','segment_signature':signature}))
   with patch.object(readiness,'media',return_value=20):short_motion.montage(script,segments,temp)
   command=run.call_args.args[0];self.assertIn('xfade=transition=fade:duration=0.35',command[command.index('-filter_complex')+1]);self.assertEqual(command[command.index('-t')+1],'10')
   self.assertEqual(frame.call_args.args[0],'test.mp4');self.assertEqual(frame.call_args.args[2],1)
   report=json.loads((Path(temp)/'creative-review.json').read_text());self.assertEqual(report['state'],'checked');self.assertEqual(report['scene_count'],report['distinct_clips'])
if __name__=='__main__':unittest.main()
