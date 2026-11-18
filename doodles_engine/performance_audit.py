"""Independent inspection evidence checks; never approves or publishes a video."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

def audit(work):
 work=Path(work);report=json.loads((work/'performance-report.json').read_text())
 if report.get('policy')!='dialogue-performance-v1':raise ValueError('Unknown performance evidence')
 if report.get('outside_masks_max_delta')!=0:raise ValueError('Movement escaped character masks')
 samples=report.get('samples',[])
 if len(samples)<3:raise ValueError('Not enough performance observations')
 coverage={};tones=set()
 for who in ('leo','mia'):
  states=[sample.get('states',{}).get(who,{}) for sample in samples]
  roles={s.get('role') for s in states}
  if not {'speaker','listener'}<=roles:raise ValueError(who+' is missing speaking or listening evidence')
  tones.update(s.get('feel') for s in states if s.get('feel') not in (None,'neutral'))
  coverage[who]={'speaking_samples':sum(s.get('role')=='speaker' for s in states),'listening_samples':sum(s.get('role')=='listener' for s in states)}
 if len(tones)<2:raise ValueError('The proof does not demonstrate varied expressions')
 changed={'leo':0.,'mia':0.};pairs=0
 for before in sorted(work.glob('performance-before-*.png')):
  after=work/before.name.replace('before','after')
  if not after.is_file():continue
  a=np.array(Image.open(before).convert('RGB'));b=np.array(Image.open(after).convert('RGB'))
  if a.shape!=b.shape:raise ValueError('Before/after images have inconsistent geometry')
  delta=np.max(abs(a.astype('int16')-b.astype('int16')),axis=2)>2
  mid=delta.shape[1]//2
  for who,region in [('leo',delta[:,:mid]),('mia',delta[:,mid:])]:changed[who]=max(changed[who],float(region.mean()))
  pairs+=1
 if not pairs or any(value<.0005 for value in changed.values()):raise ValueError('Rendered evidence does not show a visible change for both characters')
 result={'role_coverage':coverage,'expression_tones':sorted(tones),'before_after_pairs':pairs,'changed_pixel_ratio':changed,
         'technical_evidence_pass':True,'human_visual_approval':False,'limit':'Pixel changes and role coverage do not prove natural acting, undistorted faces or perfect lip-sync.'}
 (work/'performance-inspection.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
 import sys
 print(json.dumps(audit(sys.argv[1]),indent=2))
