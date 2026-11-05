import unittest,tempfile,json
from pathlib import Path
import full_checkpoint as c

class Checkpoints(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.source=self.root/'job';self.target=self.root/'job-attempt-2';self.work=self.source/'.render';self.work.mkdir(parents=True)
  self.audio=self.work/'chapter_00.wav';self.audio.write_bytes(b'original audio')
 def test_verified_voice_restores_but_approval_and_final_never_copy(self):
  c.seal(self.source,'voice','script-v1',[self.audio]);(self.source/'POST_THIS.txt').write_text('not a checkpoint');(self.source/'cinematic_LONGFORM.mp4').write_text('not a checkpoint')
  self.assertEqual(c.restore(self.source,self.target,'script-v1'),['voice']);self.assertEqual((self.target/'.render/chapter_00.wav').read_bytes(),b'original audio');self.assertFalse((self.target/'POST_THIS.txt').exists());self.assertFalse((self.target/'cinematic_LONGFORM.mp4').exists());self.assertTrue(c.valid(self.source,'voice','script-v1'))
 def test_changed_script_and_corrupt_media_are_not_reused(self):
  c.seal(self.source,'voice','script-v1',[self.audio]);self.assertEqual(c.restore(self.source,self.target,'script-v2'),[])
  self.audio.write_bytes(b'changed');self.assertFalse(c.valid(self.source,'voice','script-v1'));self.assertEqual(c.restore(self.source,self.target,'script-v1'),[])
 def test_partial_narration_survives_without_complete_voice(self):
  timing=self.work/'chapter_00-timing.json';timing.write_text('{}');c.seal(self.source,'narration-0','voice-v1',[self.audio,timing])
  self.assertEqual(c.restore(self.source,self.target,'voice-v1'),['narration-0']);self.assertTrue(c.valid(self.target,'narration-0','voice-v1'))
 def test_duplicate_voice_files_are_not_overwritten(self):
  c.seal(self.source,'narration-0','voice-v1',[self.audio]);c.seal(self.source,'voice','voice-v1',[self.audio]);self.assertEqual(len(c.restore(self.source,self.target,'voice-v1')),2)
 def test_symlink_and_unsupported_files_fail_closed(self):
  c.seal(self.source,'voice','v1',[self.audio]);self.audio.unlink();self.audio.symlink_to(self.root/'external');(self.root/'external').write_bytes(b'original audio');self.assertFalse(c.valid(self.source,'voice','v1'))
  with self.assertRaises(ValueError):c.seal(self.source,'bad','v1',[self.root/'external'])
if __name__=='__main__':unittest.main()
