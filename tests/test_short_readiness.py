import sys,unittest,tempfile,json,copy,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import short_motion as s,render_readiness as r,cinematic_pipeline as cp
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'generator'))
import make_video as mv
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.audio=self.root/'voice.wav';self.audio.write_bytes(b'fixture')
  self.script={'hook':'Observe the forest now.','points':['Notice your response.'],'cta':'Follow for more.'}
  self.segments=[(kind,text,str(self.audio),2.0) for kind,text in [('hook',self.script['hook']),('point1',self.script['points'][0]),('cta',self.script['cta'])]]
 def probe(self,p):return {'format':{'duration':2},'streams':[{'codec_type':'audio'}]}
 def test_narration_is_read_only_and_timing_is_explicit_estimate(self):
  before=copy.deepcopy(self.segments);report=s.narration(self.script,self.segments,self.root,self.probe)
  self.assertEqual(report['duration'],6);self.assertEqual(report['format'],'short');self.assertIn('not model',report['timing_basis']);self.assertEqual(before,self.segments)
 def test_actual_audio_missing_or_duration_changed_stops(self):
  with self.assertRaisesRegex(ValueError,'differs'):s.narration(self.script,self.segments,self.root,lambda p:{'format':{'duration':5},'streams':[{'codec_type':'audio'}]})
  self.audio.unlink()
  with self.assertRaisesRegex(ValueError,'missing'):s.narration(self.script,self.segments,self.root,self.probe)
 def test_missing_and_swapped_script_segments_stop(self):
  with self.assertRaises(ValueError):s.narration(self.script,self.segments[:-1],self.root,self.probe)
  self.segments[0],self.segments[1]=self.segments[1],self.segments[0]
  with self.assertRaisesRegex(ValueError,'order or text'):s.narration(self.script,self.segments,self.root,self.probe)
 def test_invalid_and_empty_durations_stop(self):
  for value in (0,-1,float('nan'),float('inf'),True):
   with self.subTest(value=value):
    segments=copy.deepcopy(self.segments);segments[0]=(*segments[0][:3],value)
    with self.assertRaises(ValueError):s.narration(self.script,segments,self.root,self.probe)
 def test_caption_duration_is_exact_even_for_fast_speech(self):
  for duration,count in ((1,12),(2.13,9),(5,3)):
   self.assertAlmostEqual(s.caption_interval(duration,count)*count,duration)
  with self.assertRaises(ValueError):s.caption_interval(3,0)
 def test_dependencies_stop_before_voice(self):
  music=self.root/'music.mp3';music.write_bytes(b'music')
  with patch.dict(os.environ,{'SHELFMADE_LOCAL_MOTION':'1','USE_STICKMAN':'0'}),patch.object(s,'music_asset',return_value=music),patch.object(s,'prerequisites',side_effect=ValueError('missing prerequisite')),patch.object(mv,'_voice_segment') as voice:
   with self.assertRaisesRegex(ValueError,'prerequisite'):mv.produce(self.script,self.root,(1,2,3))
   voice.assert_not_called()
 def test_audio_gate_stops_before_footage(self):
  music=self.root/'music.mp3';music.write_bytes(b'music')
  with patch.dict(os.environ,{'SHELFMADE_LOCAL_MOTION':'1','USE_STICKMAN':'0'}),patch.object(s,'music_asset',return_value=music),patch.object(s,'prerequisites'),patch.object(mv,'_voice_segment',return_value=(str(self.audio),2)),patch.object(s,'narration',side_effect=ValueError('audio mismatch')),patch.object(s,'montage') as montage:
   with self.assertRaisesRegex(ValueError,'audio mismatch'):mv.produce(self.script,self.root,(1,2,3))
   montage.assert_not_called()
 def montage(self):return s.montage(self.script,[(kind,text,duration,'query') for kind,text,path,duration in self.segments],self.root)
 def test_missing_receipt_stops_before_provider_acquisition(self):
  import footage_director as f
  with patch.object(f,'acquire') as acquire:
   with self.assertRaisesRegex(ValueError,'checks are missing'):self.montage()
   acquire.assert_not_called()
  self.assertEqual(json.loads((self.root/'render-readiness.json').read_text())['state'],'blocked')
 def test_source_failure_prevents_encoding(self):
  import footage_director as f,creative_quality as q
  report=s.narration(self.script,self.segments,self.root,self.probe);r.record(self.root,'short_audio_checked',lambda:report)
  with patch.object(f,'acquire',return_value=[]),patch.object(cp,'plan_shots',return_value=[]),patch.object(q,'script_review',return_value={}),patch.object(q,'scene_review',return_value={}),patch.object(q,'require',return_value={}),patch.object(cp,'run') as encode:
   with self.assertRaisesRegex(ValueError,'no planned scenes'):self.montage()
   encode.assert_not_called()
 def test_receipt_is_bound_to_segment_text_duration_and_order(self):
  report=s.narration(self.script,self.segments,self.root,self.probe);changed=copy.deepcopy(self.segments);changed[0]=(*changed[0][:3],3)
  self.assertNotEqual(report['segment_signature'],s.segment_signature(changed))
 def test_optional_music_preserves_existing_narration_only_shorts(self):
  with patch.object(r.shutil,'which',return_value='/tools/media'),patch('PIL.ImageFont.truetype'):
   report=r.prerequisites({'music_path':str(self.root/'no-music.mp3'),'music_optional':True},True,'font',self.probe)
   self.assertIn('narration-only',report['music'])
   with self.assertRaisesRegex(ValueError,'missing'):r.prerequisites({'music_path':str(self.root/'no-music.mp3')},True,'font',self.probe)
 def test_shorts_use_the_configured_full_video_music_asset(self):
  import cinematic_pipeline as cinema
  music=self.root/'music.mp3';music.write_bytes(b'music')
  with patch.object(cinema,'settings',return_value={'music_path':str(music)}):
   self.assertEqual(s.music_asset(),music)
 def test_short_composite_mixes_soft_ducked_music_under_voice(self):
  import types
  bg=self.root/'bg.mp4';bg.write_bytes(b'video')
  music=self.root/'music.mp3';music.write_bytes(b'music')
  with patch.object(mv,'audio_seconds',return_value=9),patch.object(s,'music_asset',return_value=music),patch.object(mv.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stderr=b'')) as run:
   mv._assemble_video_bg_timed([('frame.png',1)],str(self.audio),self.root,str(bg))
  command=run.call_args.args[0]
  mix=command[command.index('-filter_complex')+1]
  self.assertIn(str(music),command)
  self.assertIn('volume=0.06',mix)
  self.assertIn('sidechaincompress',mix)
  self.assertIn('alimiter',mix)
 def test_full_video_gate_still_accepts_shared_scene_validation(self):
  source=self.root/'source.mp4';source.write_bytes(b'fixture')
  shots=[{'start':0,'unit':2,'duration':2.35,'source_start':1,'source':str(source)}]
  result=r.scene_sources([{'duration':2}],shots,lambda p:{'format':{'duration':20},'streams':[{'codec_type':'video'}]})
  self.assertEqual(result,{'scene_count':1,'source_count':1})
if __name__=='__main__':unittest.main()
