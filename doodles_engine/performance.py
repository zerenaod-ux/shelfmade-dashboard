"""Bounded character performance from dialogue; never moves pixels outside its masks."""
import math
import cv2
import numpy as np

POLICY='dialogue-performance-v1'
# brow lift, inner brow, eye aperture, head tilt, nod, shoulder lift.
PROFILES={
 'neutral':(0,0,0,0,0,0), 'confident':(.25,-.15,.02,-.6,.25,.05),
 'deadpan':(-.12,-.1,-.22,.65,.05,.05), 'sheepish':(.2,.45,-.06,.8,.1,.3),
 'panicked':(.8,.3,.16,-.7,.4,.65), 'warm':(.18,.1,-.06,.45,.4,.06),
 'tired':(-.12,.1,-.24,.6,.12,.25), 'excited':(.65,-.12,.13,-.6,.65,.3),
 'hopeful':(.4,.25,.08,.45,.4,.06), 'amused':(.3,-.1,-.1,-.55,.4,.15),
 'anxious':(.35,.55,.1,.55,.15,.5), 'concerned':(.2,.45,.04,.5,.12,.12),
 'skeptical':(.15,-.2,-.13,.85,.05,.15), 'curious':(.55,.1,.1,.7,.15,.05)}
LISTENER={'panicked':'concerned','excited':'amused','confident':'skeptical',
 'deadpan':'amused','sheepish':'warm','tired':'concerned','hopeful':'warm','anxious':'concerned'}
ALIASES={'dramatic':'excited','smug':'confident','surprised':'excited',
 'realizing':'curious','grim':'deadpan','determined':'confident','strained':'anxious',
 'relieved':'warm','happy':'amused','sleepy':'tired','serious':'deadpan',
 'annoyed':'skeptical','angry':'anxious','sarcastic':'deadpan',
 'embarrassed':'sheepish','confused':'curious','shocked':'excited',
 'accusatory':'skeptical','defensive':'sheepish','proud':'confident',
 'resigned':'tired','playful':'amused','indignant':'anxious','calm':'warm',
 'patient':'warm','exasperated':'skeptical','melodramatic':'excited','dry':'deadpan',
 'defeated':'tired','teasing':'amused','pouting':'sheepish','affectionate':'warm'}

def smooth(x):
 x=max(0.,min(1.,x));return x*x*(3-2*x)

def state(t,who,timeline):
 """Blend overlapping onset/release envelopes, including the listening character."""
 result=np.zeros(6,dtype='float64');weight=0.;role='rest';feel='neutral'
 for shot in timeline:
  for line in shot['lines']:
   start,end=line['start'],line['end']
   if t<start-.16 or t>end+1.0:continue
   onset=smooth((t-start+.16)/.32);release=1-smooth((t-end)/1.0)
   w=onset*release
   speaking=line['who']==who
   tone=line.get('feel','neutral') if speaking else (line.get('listener_feel') or LISTENER.get(line.get('feel'),'curious'))
   tone=str(tone or 'neutral').strip().lower();tone=ALIASES.get(tone,tone)
   if tone not in PROFILES:tone='neutral'
   amount=1. if speaking else .72
   result+=np.array(PROFILES[tone])*w*amount;weight+=w
   if start<=t<=end:role='speaker' if speaking else 'listener';feel=tone
   # Discrete reactions follow the phrase, not continuous rhythmic head bobbing.
   pulse=math.sin(math.pi*smooth((t-start)/max(.4,min(1.3,end-start))))
   result[4]+=PROFILES[tone][4]*w*amount*pulse*.35
 if weight>1:result/=weight
 return {'brow':float(result[0]),'inner':float(result[1]),'eye':float(result[2]),
         'tilt':float(result[3]),'nod':float(result[4]),'shrug':float(result[5]),'role':role,'feel':feel}

def rig(rgb,face,who):
 """Conservative GrabCut foreground inside one character's half of the picture."""
 H,W=rgb.shape[:2];x,y,w,h=[face[k] for k in ('x','y','w','h')]
 cx=x+w/2;cy=y+h/2
 x0=max(0,int(cx-1.3*w));x1=min(W,int(cx+1.3*w))
 if who=='leo':x1=min(x1,W//2)
 else:x0=max(x0,W//2)
 y0=max(0,int(y-.35*h));y1=min(H,int(y+2.15*h))
 if x1-x0<30 or y1-y0<40:raise ValueError('Character crop is too small')
 roi=np.ascontiguousarray(rgb[y0:y1,x0:x1]);hh,ww=roi.shape[:2]
 yy,xx=np.mgrid[0:hh,0:ww].astype('float32');X=xx+x0;Y=yy+y0
 head=((X-cx)/(.68*w))**2+((Y-cy)/(.82*h))**2<1
 torso=((X-cx)/(1.1*w))**2+((Y-(y+1.5*h))/(.62*h))**2<1
 allowed=head|torso
 labels=np.where(allowed,cv2.GC_PR_FGD,cv2.GC_BGD).astype('uint8')
 inside=((X-cx)/(.26*w))**2+((Y-cy)/(.31*h))**2<1
 labels[inside]=cv2.GC_FGD;labels[[0,-1],:]=cv2.GC_BGD;labels[:,[0,-1]]=cv2.GC_BGD
 cv2.grabCut(cv2.cvtColor(roi,cv2.COLOR_RGB2BGR),labels,None,np.zeros((1,65)),np.zeros((1,65)),3,cv2.GC_INIT_WITH_MASK)
 foreground=((labels==cv2.GC_FGD)|(labels==cv2.GC_PR_FGD))&allowed
 count,components=cv2.connectedComponents(foreground.astype('uint8'))
 seed=components[min(hh-1,max(0,int(cy-y0))),min(ww-1,max(0,int(cx-x0)))]
 if seed==0:raise ValueError('No reliable character foreground at face centre')
 foreground=(components==seed)
 # Moving shoulders may include clothing, never a black microphone or desk prop.
 hsv=cv2.cvtColor(roi,cv2.COLOR_RGB2HSV)
 hue=hsv[...,0];sat=hsv[...,1];value=hsv[...,2]
 garment=((hue>=12)&(hue<=42) if who=='leo' else (hue>=65)&(hue<=115))&(sat>55)&(value>45)
 head_support=head&(Y<y+1.10*h)
 foreground&=head_support|(torso&garment)
 if foreground.sum()<.25*w*h:raise ValueError('Character segmentation is incomplete')
 # Erosion and a distance ramp keep silhouette/background pixels untouched.
 distance=cv2.distanceTransform(foreground.astype('uint8'),cv2.DIST_L2,3)
 alpha=np.clip((distance-1)/max(2.,.035*w),0,1).astype('float32')
 eyes=sorted(face['eyes'],key=lambda point:point[0]);d=max(8.,math.dist(*eyes))
 return {'box':(x0,y0,x1,y1),'alpha':alpha,'X':X,'Y':Y,'xx':xx,'yy':yy,
         'cx':cx,'cy':cy,'w':w,'h':h,'eyes':eyes,'d':d,'who':who}

def apply(rgb,R,S):
 """Upper-face expression excludes the mouth; pose then carries the whole face."""
 x0,y0,x1,y1=R['box'];original=rgb[y0:y1,x0:x1];xx,yy=R['xx'],R['yy'];X,Y=R['X'],R['Y']
 dx=np.zeros_like(xx);dy=np.zeros_like(yy);d=R['d'];mid=sum(p[0] for p in R['eyes'])/2
 for ex,ey in R['eyes']:
  # Move existing brow artwork; do not paint a second eyebrow or alter the lips.
  brow=np.exp(-((X-ex)/(.43*d))**4-((Y-(ey-.33*d))/(.22*d))**4)
  toward=1-np.clip(abs(X-mid)/(.65*d),0,1)
  dy+=brow*d*(.10*S['brow']+.09*S['inner']*toward)
  eye=np.exp(-((X-ex)/(.34*d))**4-((Y-ey)/(.24*d))**4)
  dy-=eye*(Y-ey)*S['eye']*.6
 upper=(Y<max(p[1] for p in R['eyes'])+.30*d).astype('float32')
 expression=cv2.remap(original,xx+dx*upper,yy+dy*upper,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
 expression=original*(1-R['alpha'][...,None])+expression*R['alpha'][...,None]
 head=np.exp(-((X-R['cx'])/(.65*R['w']))**4-((Y-R['cy'])/(.83*R['h']))**4)
 shoulder=np.exp(-((X-R['cx'])/(1.03*R['w']))**4-((Y-(R['cy']+R['h']))/(.44*R['h']))**4)
 angle=math.radians(S['tilt']*1.55);px,py=R['cx'],R['cy']+.65*R['h']
 mx=(-angle*(Y-py))*head;my=(angle*(X-px)+R['h']*.018*S['nod'])*head-R['h']*.026*S['shrug']*shoulder
 mx=np.clip(mx,-.035*R['w'],.035*R['w'])*R['alpha'];my=np.clip(my,-.035*R['h'],.035*R['h'])*R['alpha']
 posed=cv2.remap(np.rint(expression).clip(0,255).astype('uint8'),xx-mx,yy-my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
 out=rgb.copy();out[y0:y1,x0:x1]=np.rint(np.clip(original*(1-R['alpha'][...,None])+posed*R['alpha'][...,None],0,255)).astype('uint8')
 return out
