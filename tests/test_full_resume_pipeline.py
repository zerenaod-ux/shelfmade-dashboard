import unittest,tempfile,json,os
from pathlib import Path
from unittest.mock import patch
import cinematic_pipeline as cp,full_checkpoint as checkpoint,footage_preflight,footage_director,creative_quality
from generation_recovery import RecoverableGenerationError

class ResumePipeline(unittest.TestCase):
 def test_missing_preflight_stops_before_voice_or_render(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(cp.render_readiness,'prerequisites',return_value={}),patch.object(cp.cinematic_content,'build',return_value={'title':'Book','sections':[{'title':'Lesson','narration':'Choose your response.'}]}),patch.object(creative_quality,'require',return_value={}),patch.object(creative_quality,'save'),patch.object(creative_quality,'script_review',return_value={}),patch.object(footage_preflight,'check',side_effect=RecoverableGenerationError('Missing matching footage','footage_shortage')),patch.object(cp,'run') as voice,patch.object(cp,'render') as render,patch.dict(os.environ,{'SHELFMADE_FULL_RESUME_FROM':''}):
   with self.assertRaises(RecoverableGenerationError):cp.build('1497',Path(temp)/'job')
   voice.assert_not_called();render.assert_not_called()
 def test_failed_footage_retry_reuses_voice_and_subtitles(self):
  script={'title':'Book','sections':[{'title':'Lesson','narration':'Choose your response.'}]}
  def voice_run(cmd,timeout):
   work=Path(cmd[-1]);(work/'chapter_00.wav').write_bytes(b'fixture audio');(work/'audio.txt').write_text("file 'chapter_00.wav'\n")
   (work/'chapters.json').write_text(json.dumps([{'index':0,'title':'Lesson','narration':'Choose your response.','start':0,'duration':350}]))
   (work/'word-timing.json').write_text(json.dumps({'words':[{'text':w,'start':i,'end':i+.5} for i,w in enumerate('Choose your response.'.split())]}))
  with tempfile.TemporaryDirectory() as temp,patch.object(cp.render_readiness,'prerequisites',return_value={}),patch.object(cp.cinematic_content,'build',side_effect=lambda book:json.loads(json.dumps(script))),patch.object(creative_quality,'require',return_value={}),patch.object(creative_quality,'save'),patch.object(creative_quality,'script_review',return_value={}),patch.object(footage_preflight,'check',return_value={}) as preflight,patch.object(cp,'run',side_effect=voice_run) as voice,patch.object(cp,'probe',return_value={'format':{'duration':350},'streams':[{'codec_type':'audio'}]}),patch.object(footage_director,'acquire',side_effect=[RecoverableGenerationError('Missing clips','footage_shortage'),[]]),patch.object(cp,'render',side_effect=RuntimeError('stop after resume')):
   source=Path(temp)/'job';target=Path(temp)/'job-attempt-2'
   with patch.dict(os.environ,{'SHELFMADE_FULL_RESUME_FROM':''}):
    with self.assertRaises(RecoverableGenerationError):cp.build('1497',source)
   before=checkpoint.file_hash(source/'.render/chapter_00.wav')
   with patch.dict(os.environ,{'SHELFMADE_FULL_RESUME_FROM':str(source)}):
    with self.assertRaisesRegex(RuntimeError,'stop after resume'):cp.build('1497',target)
   self.assertEqual(voice.call_count,1);self.assertEqual(preflight.call_count,1);self.assertEqual(checkpoint.file_hash(source/'.render/chapter_00.wav'),before);self.assertEqual(checkpoint.file_hash(target/'.render/chapter_00.wav'),before)
   self.assertIn('voice',json.loads((target/'recovery-restored.json').read_text())['verified_stages'])
if __name__=='__main__':unittest.main()
