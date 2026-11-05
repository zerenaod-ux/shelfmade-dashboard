"""Natural eye life for the still-picture Shorts: blinks (eyelid closes over the eye) and eye movement (iris glances, listener looks at the speaker).
Free, no AI model, milliseconds per frame. Landmarks come from fastlip.detect (YuNet). Works on the shot picture at its own resolution."""
import math,random
import numpy as np,cv2
def _skin(rgb,cx,cy,d):
    H,W=rgb.shape[:2];r=int(0.9*d);x0,x1=max(0,int(cx-r)),min(W,int(cx+r));y0,y1=max(0,int(cy-r)),min(H,int(cy+0.9*r))
    b=rgb[y0:y1,x0:x1].reshape(-1,3).astype('int');
    if len(b)==0:return np.array([222,160,140],'float32')
    m=(b[:,0]>b[:,1])&(b[:,1]>b[:,2])&(b[:,0]-b[:,2]>35)&(b.sum(1)>360)
    if m.sum()<20:return np.array([222,160,140],'float32')
    return np.median(b[m],axis=0).astype('float32')
def geom(rgb,face):
    """Two eyes: centre, half-width a, half-height b, skin colour for the lid."""
    (x1,y1),(x2,y2)=face['eyes']
    if x1>x2:(x1,y1),(x2,y2)=(x2,y2),(x1,y1)
    d=max(10.0,math.hypot(x2-x1,y2-y1));out=[]
    for (x,y) in ((x1,y1),(x2,y2)):
        E={'cx':x,'cy':y,'a':0.31*d,'b':0.24*d,'d':d,'skin':_skin(rgb,x,y,d)}
        a,b=E['a'],E['b'];H,W=rgb.shape[:2];R=int(1.7*a)+3;x0,x1=max(0,int(x-R)),min(W,int(x+R));y0,y1=max(0,int(y-R)),min(H,int(y+R))
        try:
            roi=np.ascontiguousarray(rgb[y0:y1,x0:x1]).astype('float32');h,w=roi.shape[:2]
            lx0=int(max(0,x-1.55*a-x0));lx1=int(max(lx0+2,x-1.30*a-x0));rx0=int(min(w-3,x+1.30*a-x0));rx1=int(min(w,x+1.55*a-x0))
            Lc=np.median(roi[:,lx0:lx1],axis=1);Rc=np.median(roi[:,rx0:rx1],axis=1)   # h x 3 skin colour left/right of the eye, per row
            Lc=cv2.GaussianBlur(Lc[None],(0,0),sigmaX=max(1.5,0.08*d))[0];Rc=cv2.GaussianBlur(Rc[None],(0,0),sigmaX=max(1.5,0.08*d))[0]
            t=np.linspace(0,1,w,dtype='float32')[None,:,None]
            tx=Lc[:,None,:]*(1-t)+Rc[:,None,:]*t
            sk=E['skin'];lum=tx.mean(2,keepdims=True);tx=np.where(lum<0.82*float(sk.mean()),sk[None,None,:]*np.ones_like(tx),tx)
            E['tex']=cv2.GaussianBlur(tx,(0,0),max(1.5,0.06*d))
        except Exception:E['tex']=None
        out.append(E)
    return out
def _lid_masks(G,shape):
    return None
def apply(arr,eyes,blink,gaze):
    """arr: HxWx3 uint8 (modified in place). blink 0 open..1 closed. gaze (gx,gy) in units of eye distance d."""
    H,W=arr.shape[:2]
    for E in eyes:
        cx,cy,a,b,d=E['cx'],E['cy'],E['a'],E['b'],E['d']
        R=int(1.7*a)+3;x0,x1=max(0,int(cx-R)),min(W,int(cx+R));y0,y1=max(0,int(cy-R)),min(H,int(cy+R))
        if x1-x0<8 or y1-y0<8:continue
        roi=arr[y0:y1,x0:x1].astype('float32');h,w=roi.shape[:2]
        ys,xs=np.mgrid[0:h,0:w].astype('float32');u=xs+x0-cx;v=ys+y0-cy
        gx,gy=gaze[0]*d,gaze[1]*d
        if abs(gx)>0.05 or abs(gy)>0.05:
            M=np.float32([[1,0,gx],[0,1,gy]]);sh=cv2.warpAffine(roi,M,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            m=np.clip(1-((u/(0.92*a))**2+(v/(0.88*b))**2),0,1);m=np.clip(m*3.0,0,1);m=cv2.GaussianBlur(m,(0,0),max(0.8,0.04*d))[...,None]
            roi=roi*(1-m)+sh*m
        if blink>0.02:
            bl=float(min(1.0,blink));bl_s=bl*bl*(3-2*bl)
            curve=(1-np.clip(u/(1.05*a),-1,1)**2)
            line=cy-1.05*b+bl_s*(1.55*b+0.35*b*curve)
            line2=cy+1.12*b-bl_s*(0.62*b+0.30*b*curve)
            Y=ys+y0;soft=max(1.2,0.05*d)
            inside=np.clip(1-((u/(1.10*a))**2+(np.where(v<0,v/(1.05*b),v/(1.55*b)))**2),0,1);inside=np.clip(inside*4.0,0,1)
            below=np.clip((line-Y)/soft+0.5,0,1);above=np.clip((Y-line2)/soft+0.5,0,1)
            cov=np.maximum(below,above*(1.0 if bl_s>0.05 else 0.0));cov=cov*(bl_s>0.05)+below*(bl_s<=0.05)
            cover=cv2.GaussianBlur(inside*cov,(0,0),0.7)[...,None]
            tex=E.get('tex')
            lidtex=(tex[y0-y0:y1-y0,:,:] if tex is not None and tex.shape[:2]==(h,w) else E['skin'][None,None,:]*np.ones((h,w,1),'float32'))
            lidtex=lidtex*(0.97-0.04*bl)
            roi=roi*(1-cover)+lidtex*cover
            thick=max(1.1,0.045*d);dist=np.abs(Y-line)
            lash=np.clip(1-dist/thick,0,1)*np.clip(inside*3.0,0,1)*min(1.0,bl*2.5)
            lash=cv2.GaussianBlur(lash,(0,0),0.6)[...,None]*0.85
            roi=roi*(1-lash)+np.array([52,30,28],'float32')*lash
        arr[y0:y1,x0:x1]=np.clip(roi,0,255).astype('uint8')
    return arr
class Life:
    """Per-character timeline: blink(t) in 0..1 and gaze(t) in eye-distance units; deterministic from a seed."""
    def __init__(self,seed,total):
        r=random.Random(seed);self.blinks=[];t=r.uniform(0.6,1.6)
        while t<total:
            self.blinks.append(t)
            if r.random()<0.14:self.blinks.append(t+0.30)
            t+=r.uniform(2.3,5.0)
        self.r=r;self.sac=[];t=0.0;g=(0.0,0.0)
        while t<total+3:
            self.sac.append((t,r.uniform(-0.028,0.028),r.uniform(-0.016,0.02)));t+=r.uniform(0.9,2.4)
    def blink(self,t,extra=()):
        v=0.0
        for b in list(self.blinks)+list(extra):
            x=t-b
            if x<0 or x>0.30:continue
            v=max(v,x/0.07 if x<0.07 else (1.0 if x<0.10 else max(0.0,1-(x-0.10)/0.15)))
        return v
    def gaze(self,t,toward=0.0,away=False):
        """toward: horizontal look direction (-1 left .. +1 right) at strength 0.09 d; micro saccades on top."""
        gx=gy=0.0
        cur=None
        for s in self.sac:
            if s[0]<=t:cur=s
            else:break
        if cur:
            k=min(1.0,(t-cur[0])/0.10);k=k*k*(3-2*k)
            idx=self.sac.index(cur);prev=self.sac[idx-1] if idx>0 else (0,0,0)
            gx=prev[1]+(cur[1]-prev[1])*k;gy=prev[2]+(cur[2]-prev[2])*k
        return (gx+0.085*toward,gy+(0.04 if away else 0.0))
