"""Fast mouth animation for the still-picture Shorts: jaw-drop warp + dark mouth interior, driven by each voice's loudness.
Seconds per video, no AI model. Face landmarks come from the free YuNet detector (OpenCV). Needs: opencv-python-headless."""
import numpy as np
from pathlib import Path
import cv2
YUNET=Path('/tmp/yunet.onnx') if Path('/tmp/yunet.onnx').exists() else Path(__file__).resolve().parent.parent/'data/engines/yunet/face_detection_yunet_2023mar.onnx'
def detect(rgb):
    """All faces in an RGB uint8 image -> list of dict(x,y,w,h,score,corners=((x1,y1),(x2,y2)))."""
    bgr=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR);h,w=bgr.shape[:2]
    d=cv2.FaceDetectorYN.create(str(YUNET),'',(w,h),0.25,0.3,10);d.setInputSize((w,h));_,f=d.detect(bgr)
    out=[]
    for r in ([] if f is None else f):
        out.append({'x':float(r[0]),'y':float(r[1]),'w':float(r[2]),'h':float(r[3]),'score':float(r[14]),
                    'corners':((float(r[10]),float(r[11])),(float(r[12]),float(r[13]))),
                    'eyes':((float(r[4]),float(r[5])),(float(r[6]),float(r[7])))})
    return out
def pick(faces,who,width):
    if not faces:return None
    want=0.30*width if who=='leo' else 0.70*width
    return min(faces,key=lambda f:abs((f['x']+f['w']/2)-want)-30*f['score'])
def mouth_geom(face):
    (ax,ay),(bx,by)=face['corners']
    if ax>bx:(ax,ay),(bx,by)=(bx,by),(ax,ay)
    cx=(ax+bx)/2;cy=(ay+by)/2;mw=max(12.0,((bx-ax)**2+(by-ay)**2)**.5)
    return {'cx':cx,'cy':cy,'mw':mw,'tilt':float(np.arctan2(by-ay,bx-ax))}
def _smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
def is_open(rgb,g):
    """True when the picture already shows an open mouth (large dark interior) - then we leave it alone."""
    H,W=rgb.shape[:2];cx,cy,mw=int(g['cx']),int(g['cy']),g['mw']
    b=rgb[max(0,int(cy-.25*mw)):int(cy+.35*mw),max(0,int(cx-.4*mw)):int(cx+.4*mw)]
    if b.size==0:return False
    L=cv2.cvtColor(b,cv2.COLOR_RGB2GRAY);return float((L<80).mean())>0.30 or float((L>205).mean())>0.04
def apply(rgb,g,o):
    """Return a copy of rgb with the mouth opened by o (0 closed .. 1 wide). Works in the mouth's own tilted frame."""
    if o<=0.05:return rgb
    H,W=rgb.shape[:2];cx,cy,mw,t=g['cx'],g['cy'],g['mw'],g.get('tilt',0.0)
    ct,st=float(np.cos(t)),float(np.sin(t));opx=float(o)*0.42*mw
    R=int(mw*2.0);x0=max(0,int(cx-R));x1=min(W,int(cx+R));y0=max(0,int(cy-1.4*mw));y1=min(H,int(cy+2.2*mw))
    roi=rgb[y0:y1,x0:x1].copy();h,w=roi.shape[:2]
    ys,xs=np.mgrid[0:h,0:w].astype('float32');px=xs+x0-cx;py=ys+y0-cy
    u=px*ct+py*st;v=-px*st+py*ct          # u along the mouth, v down from the lip line
    # 1) erase the old closed lip line (soft band along the mouth) by inpainting from the skin around it
    band=((np.abs(v-0.05*mw)<0.16*mw)&(np.abs(u)<0.85*mw)).astype('uint8')*255
    roi=cv2.inpaint(roi,band,4,cv2.INPAINT_TELEA)
    # 2) slide the lower face down along the mouth's own 'down' direction
    wu=np.exp(-(u/(0.85*mw))**2);ease=1.0-_smooth((v-0.25*mw)/(1.2*mw))
    dy=(opx*wu*ease*_smooth((v+0.10*mw)/(0.35*mw))).astype('float32')
    out=cv2.remap(roi,(xs+dy*st).astype('float32'),(ys-dy*ct).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    # 3) draw lips + interior between the upper lip line (v=0) and the lowered lower lip (v=opx)
    a=0.36*mw*(0.75+0.25*o);b=max(0.7,opx*0.5);vc=opx*0.5
    e=np.sqrt((u/a)**2+((v-vc)/b)**2)
    inner=np.clip(1-_smooth((e-0.86)/0.14),0,1)[...,None]
    rim=np.clip(1-_smooth((e-1.0)/0.30),0,1)[...,None]-inner
    base=out.astype('float32');lipc=np.array([178,84,86],'float32')
    r=np.clip(rim,0,1)*0.8;base=base*(1-r)+lipc*r
    col=np.broadcast_to(np.array([66,26,32],'float32'),base.shape).copy()
    tt=np.clip(1-(v-(vc-b))/(0.38*b+1e-3),0,1)[...,None]*np.clip(1-(np.abs(u)/(0.80*a))**2,0,1)[...,None]*0.85
    col=col*(1-tt)+np.array([232,224,210],'float32')*tt
    tg=np.clip((v-(vc+0.15*b))/(0.8*b+1e-3),0,1)[...,None]*np.clip(1-(np.abs(u)/(0.6*a))**2,0,1)[...,None]*0.85
    col=col*(1-tg)+np.array([170,66,78],'float32')*tg
    res=base*(1-inner)+col*inner
    full=rgb.copy();full[y0:y1,x0:x1]=np.clip(res,0,255).astype('uint8');return full
