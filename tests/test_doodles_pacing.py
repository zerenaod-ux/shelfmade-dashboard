import json,sys,tempfile,unittest,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'doodles_engine'))
from dialogue_pacing import prepare
from test_doodles_dialogue_quality import story

class PacingTests(unittest.TestCase):
 def assets(self,p,seconds):
  (p/'story.json').write_text(json.dumps(story()))
  a=(np.sin(np.arange(int(seconds*24000))*2*np.pi*220/24000)*.1*32700).astype('<i2')
  for si in range(6):
   for li in range(2):
    with wave.open(str(p/f'line_{si:02d}_{li:02d}.wav'),'wb') as audio:
     audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(a.tobytes())
    (p/f'align_{si:02d}_{li:02d}.json').write_text(json.dumps({'text':'fixture','segs':[[0,seconds,1]]}))
 def test_modest_speed_repair_preserves_originals_and_aligns_before_lipsync(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);self.assets(p,6);original=(p/'line_00_00.wav').read_bytes()
   report=prepare(p)
   self.assertTrue(report['changed']);self.assertLessEqual(report['speed_factor'],1.2)
   self.assertTrue(40<=report['after']<=70);self.assertEqual((p/'voice-originals/line_00_00.wav').read_bytes(),original)
   self.assertFalse(report['spoken_words_removed']);self.assertEqual(len(report['lines']),12)
   self.assertLess(json.loads((p/'align_00_00.json').read_text())['segs'][0][1],6)
   self.assertFalse(prepare(p)['changed'])
 def test_extreme_lengths_are_held_without_touching_audio(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);self.assets(p,10);original=(p/'line_00_00.wav').read_bytes()
   with self.assertRaisesRegex(ValueError,'bounded natural pacing'):prepare(p)
   self.assertEqual((p/'line_00_00.wav').read_bytes(),original)
 def test_existing_lipsync_blocks_audio_timing_change(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);self.assets(p,6);(p/'ls_out').mkdir();(p/'ls_out/example.mp4').write_bytes(b'fixture')
   with self.assertRaisesRegex(ValueError,'before lip-sync'):prepare(p)

if __name__=='__main__':unittest.main()
