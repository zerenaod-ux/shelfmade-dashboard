import sys,unittest
from pathlib import Path
import cv2,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'doodles_engine'))
import performance as p

def fixture():
 a=np.full((400,600,3),(95,145,175),dtype='uint8')
 cv2.ellipse(a,(145,145),(55,75),0,0,360,(225,175,145),-1)
 cv2.ellipse(a,(145,270),(90,80),0,0,360,(235,190,40),-1)
 for x in (125,165):
  cv2.line(a,(x-12,113),(x+10,110),(35,30,25),4)
  cv2.ellipse(a,(x,135),(12,8),0,0,360,(245,245,235),-1)
  cv2.circle(a,(x,135),4,(25,25,20),-1)
 cv2.line(a,(129,178),(162,180),(80,35,35),3)
 face={'x':90.,'y':70.,'w':110.,'h':150.,'eyes':((125.,135.),(165.,135.))}
 return a,face

class PerformanceTests(unittest.TestCase):
 def timeline(self):return [{'lines':[{'start':1.,'end':4.,'who':'leo','feel':'panicked','listener_feel':None}]}]
 def test_emotion_drives_speaker_and_distinct_listener(self):
  speaker=p.state(2,'leo',self.timeline());listener=p.state(2,'mia',self.timeline())
  self.assertEqual(speaker['role'],'speaker');self.assertEqual(listener['role'],'listener')
  self.assertEqual(listener['feel'],'concerned');self.assertGreater(listener['brow'],0)
  self.assertNotEqual(speaker['eye'],listener['eye'])
 def test_explicit_listener_direction_is_used(self):
  tl=self.timeline();tl[0]['lines'][0]['listener_feel']='amused'
  self.assertEqual(p.state(2,'mia',tl)['feel'],'amused')
 def test_existing_voice_emotions_have_visual_profiles(self):
  for feel in ('dramatic','smug','surprised','realizing','grim','determined','strained','relieved','happy','sleepy','serious','curious '):
   tl=self.timeline();tl[0]['lines'][0]['feel']=feel
   self.assertNotEqual(p.state(2,'leo',tl)['feel'],'neutral',feel)
 def test_expression_releases_smoothly_and_returns_to_rest(self):
  a=p.state(4,'leo',self.timeline());b=p.state(4.01,'leo',self.timeline())
  self.assertLess(abs(a['brow']-b['brow']),.02)
  self.assertEqual(p.state(7,'leo',self.timeline())['brow'],0)
 def test_foreground_warp_cannot_change_outside_pixels(self):
  a,f=fixture();r=p.rig(a,f,'leo');out=p.apply(a,r,p.state(2,'leo',self.timeline()))
  support=np.zeros(a.shape[:2],bool);x0,y0,x1,y1=r['box'];support[y0:y1,x0:x1]=r['alpha']>0
  self.assertTrue(np.array_equal(a[~support],out[~support]));self.assertTrue(np.any(a[support]!=out[support]))
  self.assertTrue(np.array_equal(a[:,300:],out[:,300:]))
 def test_upper_face_expression_does_not_rewrite_mouth(self):
  a,f=fixture();r=p.rig(a,f,'leo');s=p.state(2,'leo',self.timeline())
  s.update(tilt=0,nod=0,shrug=0)
  out=p.apply(a,r,s)
  self.assertTrue(np.array_equal(a[170:195,115:180],out[170:195,115:180]))
 def test_dark_desk_microphone_is_excluded_from_shoulder_motion(self):
  a,f=fixture();a[270:305,130:160]=(20,20,20)
  r=p.rig(a,f,'leo');out=p.apply(a,r,p.state(2,'leo',self.timeline()))
  self.assertTrue(np.array_equal(a[275:300,135:155],out[275:300,135:155]))
 def test_neutral_frame_is_exact_identity(self):
  a,f=fixture();r=p.rig(a,f,'leo');out=p.apply(a,r,p.state(0,'leo',[]))
  self.assertTrue(np.array_equal(a,out))
 def test_episode_mode_does_not_enable_short_performance(self):
  import importlib.util,os
  from unittest.mock import patch
  with patch.dict(os.environ,{'DOODLES_EPISODE_SCENE':'1','DOODLES_PERFORMANCE':'1'}):
   spec=importlib.util.spec_from_file_location('episode_renderer_test',Path(__file__).resolve().parents[1]/'doodles_engine/render.py')
   module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   self.assertFalse(module.PERFORMANCE)

if __name__=='__main__':unittest.main()
