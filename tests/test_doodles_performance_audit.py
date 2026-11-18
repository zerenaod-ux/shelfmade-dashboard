import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'doodles_engine'))
from performance_audit import audit
class AuditTests(unittest.TestCase):
 def prepare(self,folder):
  states=[{'leo':{'role':'speaker','feel':'excited'},'mia':{'role':'listener','feel':'amused'}},{'leo':{'role':'listener','feel':'curious'},'mia':{'role':'speaker','feel':'deadpan'}}]
  report={'policy':'dialogue-performance-v1','outside_masks_max_delta':0,'samples':[{'states':states[i%2]} for i in range(4)]}
  (folder/'performance-report.json').write_text(json.dumps(report))
  a=np.zeros((100,100,3),'uint8');b=a.copy();b[20:30,20:30]=100;b[20:30,70:80]=100
  Image.fromarray(a).save(folder/'performance-before-000.png');Image.fromarray(b).save(folder/'performance-after-000.png')
  return report
 def test_checks_actual_image_change_and_both_roles(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);self.prepare(p);r=audit(p)
   self.assertTrue(r['technical_evidence_pass']);self.assertFalse(r['human_visual_approval'])
 def test_rejects_static_images_despite_claimed_emotions(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);self.prepare(p)
   (p/'performance-after-000.png').write_bytes((p/'performance-before-000.png').read_bytes())
   with self.assertRaisesRegex(ValueError,'visible change'):audit(p)
 def test_rejects_missing_listener_and_background_motion(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);report=self.prepare(p);report['outside_masks_max_delta']=1
   (p/'performance-report.json').write_text(json.dumps(report))
   with self.assertRaisesRegex(ValueError,'escaped'):audit(p)
   report['outside_masks_max_delta']=0
   for s in report['samples']:s['states']['mia']['role']='speaker'
   (p/'performance-report.json').write_text(json.dumps(report))
   with self.assertRaisesRegex(ValueError,'listening'):audit(p)
if __name__=='__main__':unittest.main()
