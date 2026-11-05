import sys,unittest,tempfile,json,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import render_readiness as r,cinematic_pipeline as cp
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'.render').mkdir();self.clip=self.root/'clip.mp4';self.clip.write_bytes(b'fixture');(self.root/'.render/chapter_00.wav').write_bytes(b'fixture')
  self.script={'sections':[{'narration':'Observe the forest.'}]};self.chapters=[{'index':0,'start':0,'duration':8,'narration':'Observe the forest.'}];self.words=[{'text':w,'start':i,'end':i+.5} for i,w in enumerate('Observe the forest.'.split())];self.shots=[{'source':str(self.clip),'start':0,'unit':8,'duration':8.65,'source_start':1}]
 def probe(self,p):return {'format':{'duration':8 if Path(p).suffix=='.wav' else 20},'streams':[{'codec_type':'audio' if Path(p).suffix=='.wav' else 'video'}]}
 def ready(self):return r.footage(self.script,self.chapters,self.words,self.shots,self.root,self.probe)
 def test_valid_report_is_read_only_and_probes_each_source_once(self):
  before=copy.deepcopy((self.script,self.chapters,self.words,self.shots));calls=[]
  def probe(p):calls.append(str(p));return self.probe(p)
  result=r.footage(self.script,self.chapters,self.words,self.shots,self.root,probe);self.assertEqual(result['stage'],'ready_for_encoding');self.assertEqual(len(calls),2);self.assertEqual(before,(self.script,self.chapters,self.words,self.shots))
 def test_missing_and_unreadable_media_stops(self):
  with self.assertRaisesRegex(ValueError,'missing or empty'):r.media(self.root/'missing','video',self.probe)
  with self.assertRaisesRegex(ValueError,'unreadable'):r.media(self.clip,'audio',self.probe)
 def test_changed_source_duration_cannot_rely_on_cached_asset_duration(self):
  with self.assertRaisesRegex(ValueError,'real source duration'):r.footage(self.script,self.chapters,self.words,self.shots,self.root,lambda p:{'format':{'duration':5},'streams':[{'codec_type':'video'}]})
 def test_chapter_audio_must_match_timeline(self):
  def probe(p):return {'format':{'duration':5},'streams':[{'codec_type':'audio'}]} if p.suffix=='.wav' else self.probe(p)
  with self.assertRaisesRegex(ValueError,'audio duration'):r.footage(self.script,self.chapters,self.words,self.shots,self.root,probe)
 def test_bad_numeric_values_and_chapter_gap_stop(self):
  for value in (float('nan'),float('inf'),-1,True,'8'):
   with self.subTest(value=value):
    chapters=copy.deepcopy(self.chapters);chapters[0]['duration']=value
    with self.assertRaises(ValueError):r.narration(self.script,chapters,self.words)
  self.chapters[0]['start']=1
  with self.assertRaisesRegex(ValueError,'chapter order'):self.ready()
 def test_subtitle_text_and_timeline_mismatch_stop(self):
  for change in ({'text':'wrong'},{'start':4,'end':3},{'end':99}):
   words=copy.deepcopy(self.words);words[0].update(change)
   with self.assertRaises(ValueError):r.narration(self.script,self.chapters,words)
 def test_missing_scenes_and_scene_gaps_stop(self):
  self.shots[0]['start']=1
  with self.assertRaisesRegex(ValueError,'gap or overlap'):self.ready()
  self.shots=[]
  with self.assertRaisesRegex(ValueError,'no planned scenes'):self.ready()
 def test_dependency_failure_stops_before_script_voice_and_footage(self):
  import cinematic_content,footage_director
  with patch.object(r.shutil,'which',return_value=None),patch.object(cinematic_content,'build') as script,patch.object(cp,'run') as run,patch.object(footage_director,'acquire') as acquire:
   with self.assertRaisesRegex(ValueError,'ffmpeg'):cp.build('1497',self.root)
   script.assert_not_called();run.assert_not_called();acquire.assert_not_called()
  self.assertEqual(json.loads((self.root/'render-readiness.json').read_text())['state'],'blocked')
 def test_encoding_gate_failure_prevents_ffmpeg(self):
  (self.root/'.render/word-timing.json').write_text(json.dumps({'words':self.words}))
  with patch.object(cp,'validate_duration'),patch.object(cp,'plan_shots',return_value=self.shots),patch('creative_quality.require',return_value={}),patch('creative_quality.scene_review',return_value={}),patch('creative_quality.script_review',return_value={}),patch.object(r,'footage',side_effect=ValueError('fixture readiness failure')),patch.object(cp,'run') as encode:
   with self.assertRaisesRegex(ValueError,'fixture readiness'):cp.render(self.script,self.root,self.chapters,[])
   encode.assert_not_called()
 def test_tool_failure_is_not_reported_as_corrupt_music(self):
  with patch.object(r.media_runtime,'require_ready',side_effect=r.media_runtime.MediaRuntimeError('Video tools need repair')):
   with self.assertRaisesRegex(r.media_runtime.MediaRuntimeError,'Video tools need repair'):
    r.media(self.clip,'audio',lambda p: (_ for _ in ()).throw(RuntimeError('probe failed')))
 def test_probe_uses_app_local_media_environment(self):
  import subprocess
  with patch.object(cp.media_runtime,'environment',return_value={'APP_MEDIA':'fixture'}),patch.object(cp.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'{}','')) as run:
   cp.probe(self.clip)
   self.assertEqual(run.call_args.kwargs['env'],{'APP_MEDIA':'fixture'})
 def test_records_pass_and_safe_failure_without_changing_inputs(self):
  report=r.record(self.root,'fixture',self.ready);self.assertEqual(report['state'],'passed')
  def fail():raise RuntimeError('private fixture detail')
  with self.assertRaises(RuntimeError):r.record(self.root,'fixture',fail)
  saved=json.loads((self.root/'render-readiness.json').read_text());self.assertEqual(saved['state'],'blocked');self.assertNotIn('private',saved['message'])
if __name__=='__main__':unittest.main()
