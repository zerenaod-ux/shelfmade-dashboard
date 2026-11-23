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
def _eye_mask(rgb,E,x0,y0,x1,y1):
    """Measure the real eye opening from the picture (the landmark can sit off the eye). Seed = the iris (dark compact blob nearest the landmark);
    GrabCut grows it to the sclera/outline, bright-white sclera touching it is added, then hull + grow ~1.5px so the lid covers the outline too.
    Returns a float mask for the box, or None when the shape is implausible (the ellipse fallback is used then)."""
    d=E['d'];a=E['a'];b=E['b'];cx=E['cx']-x0;cy=E['cy']-y0
    roi=np.ascontiguousarray(rgb[y0:y1,x0:x1]);h,w=roi.shape[:2]
    hsv=cv2.cvtColor(roi,cv2.COLOR_RGB2HSV);V=hsv[...,2]/255.0;S=hsv[...,1]/255.0
    dark=cv2.morphologyEx((V<0.32).astype('uint8'),cv2.MORPH_OPEN,np.ones((3,3),'uint8'))
    n,lab,st,ce=cv2.connectedComponentsWithStats(dark,connectivity=8);best=None;bs=1e9
    for i in range(1,n):
        ww,hh,ar=st[i,2],st[i,3],st[i,4]
        if ar<0.012*d*d or ar>0.30*d*d or max(ww,hh)/max(1,min(ww,hh))>2.2:continue
        dist=math.hypot(ce[i][0]-cx,ce[i][1]-cy)
        if dist<bs:bs=dist;best=i
    if best is None or bs>0.6*d:return None
    ix,iy=ce[best];ir=math.sqrt(st[best,4]/3.14159)
    ys,xs=np.mgrid[0:h,0:w].astype('float32')
    m=np.full((h,w),cv2.GC_BGD,'uint8')
    m[(((xs-ix)/(0.58*d))**2+((ys-iy)/(0.34*d))**2)<=1]=cv2.GC_PR_BGD
    m[(((xs-ix)/(0.58*d))**2+((ys-iy)/(0.26*d))**2)<=1]=cv2.GC_PR_FGD
    m[((xs-ix)**2+(ys-iy)**2)<=(0.8*ir)**2]=cv2.GC_FGD
    cv2.grabCut(roi,m,None,np.zeros((1,65)),np.zeros((1,65)),6,cv2.GC_INIT_WITH_MASK)
    r=((m==cv2.GC_FGD)|(m==cv2.GC_PR_FGD)).astype('uint8')
    # bright white sclera right next to the iris (GrabCut often keeps only the iris on big white eyes)
    white=((V>0.78)&(S<0.28)).astype('uint8');white=cv2.morphologyEx(white,cv2.MORPH_OPEN,np.ones((3,3),'uint8'))
    nw,lw,sw,cw=cv2.connectedComponentsWithStats(white,connectivity=8)
    near=cv2.dilate(r,np.ones((2*int(0.10*d)+1,)*2,'uint8'))>0
    for i in range(1,nw):
        comp=(lw==i)
        if (comp&near).any() and sw[i,cv2.CC_STAT_AREA]<2.2*3.14*a*b:r=r|comp.astype('uint8')
    r=cv2.morphologyEx(r,cv2.MORPH_CLOSE,np.ones((3,3),'uint8'),iterations=2)
    nn,l2,s2,_=cv2.connectedComponentsWithStats(r,connectivity=8)
    k=l2[min(h-1,int(iy)),min(w-1,int(ix))]
    if k==0:return None
    cnt,_=cv2.findContours((l2==k).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not cnt:return None
    hull=cv2.convexHull(max(cnt,key=cv2.contourArea));mk=np.zeros((h,w),'uint8');cv2.fillPoly(mk,[hull],1)
    area=float(mk.sum());ell=3.14159*a*b
    xx=np.where(mk.any(0))[0];yy=np.where(mk.any(1))[0];W_=xx[-1]-xx[0]+1;H_=yy[-1]-yy[0]+1
    if area<0.55*ell or area>3.0*ell or W_>1.2*d or H_>0.75*d or W_/max(1,H_)<0.9 or W_/max(1,H_)>3.2:return None
    # a real eye differs clearly from the skin around it; a skin patch picked up by mistake does not
    lab_=cv2.cvtColor(roi,cv2.COLOR_RGB2LAB).astype('float32');inner=cv2.erode(mk,np.ones((3,3),'uint8'),iterations=1)>0
    ringm=(cv2.dilate(mk,np.ones((3,3),'uint8'),iterations=max(3,int(0.10*d)))>0)&(cv2.dilate(mk,np.ones((3,3),'uint8'),iterations=2)==0)
    if inner.sum()<8 or ringm.sum()<8:return None
    if float(np.linalg.norm(lab_[inner].mean(0)-lab_[ringm].mean(0)))<16:return None
    mk=cv2.dilate(mk,np.ones((3,3),'uint8'),iterations=max(1,int(round(0.03*d))))
    return mk.astype('float32')
def geom(rgb,face):
    """Two eyes: landmark centre, nominal half-width a / half-height b, skin colour, and the MEASURED eye-opening mask + lid texture."""
    (x1,y1),(x2,y2)=face['eyes']
    if x1>x2:(x1,y1),(x2,y2)=(x2,y2),(x1,y1)
    d=max(10.0,math.hypot(x2-x1,y2-y1));out=[];H,W=rgb.shape[:2]
    for (x,y) in ((x1,y1),(x2,y2)):
        E={'cx':x,'cy':y,'a':0.31*d,'b':0.24*d,'d':d,'skin':_skin(rgb,x,y,d)}
        R=int(0.95*d)+3;X0,X1=max(0,int(x-R)),min(W,int(x+R));Y0,Y1=max(0,int(y-R)),min(H,int(y+R));E['box']=(X0,Y0,X1,Y1)
        try:mk=_eye_mask(rgb,E,X0,Y0,X1,Y1)
        except Exception:mk=None
        E['measured']=mk is not None
        if mk is None:   # not measurable (extreme angle, shadow): leave this eye alone rather than paint a lid that does not fit
            E['mask']=None;E['tex']=None;out.append(E);continue
        E['mask']=mk
        try:   # lid texture = the surrounding skin continued across the eye (inpaint), so shading and colour match
            roi=np.ascontiguousarray(rgb[Y0:Y1,X0:X1]);hole=(cv2.dilate(mk.astype('uint8'),np.ones((3,3),'uint8'),iterations=2)*255).astype('uint8')
            inp=cv2.inpaint(roi,hole,max(3,int(0.12*d)),cv2.INPAINT_TELEA).astype('float32')
            E['tex']=cv2.GaussianBlur(inp,(0,0),max(1.5,0.05*d))
        except Exception:E['tex']=None
        out.append(E)
    return out
def apply(arr,eyes,blink,gaze):
    """arr: HxWx3 uint8 (modified in place). blink 0 open..1 closed. gaze (gx,gy) in units of eye distance d."""
    for E in eyes:
        cx,cy,d=E['cx'],E['cy'],E['d'];x0,y0,x1,y1=E['box']
        if x1-x0<8 or y1-y0<8:continue
        mk=E.get('mask')
        if mk is None:continue
        roi=arr[y0:y1,x0:x1].astype('float32');h,w=roi.shape[:2]
        if mk.shape!=(h,w):continue
        ys,xs=np.mgrid[0:h,0:w].astype('float32')
        gx,gy=gaze[0]*d,gaze[1]*d
        if abs(gx)>0.05 or abs(gy)>0.05:
            M=np.float32([[1,0,gx],[0,1,gy]]);sh=cv2.warpAffine(roi,M,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            m=cv2.erode(mk,np.ones((3,3),'uint8'),iterations=1);m=cv2.GaussianBlur(m,(0,0),max(0.8,0.04*d))[...,None]
            roi=roi*(1-m)+sh*m
        if blink>0.02:
            bl=float(min(1.0,blink));bl_s=bl*bl*(3-2*bl)
            on=mk>0.5
            if not on.any():continue
            col=on.any(0);top=np.where(on.any(0),on.argmax(0),0).astype('float32');bot=np.where(col,h-1-on[::-1].argmax(0),0).astype('float32')
            # smooth the top/bottom edge curves along x so the lid line is a clean arc
            def sm(a_):
                idx=np.where(col)[0]
                if len(idx)<5:return a_
                o=a_.copy();o[idx]=np.convolve(np.pad(a_[idx],2,mode='edge'),np.ones(5)/5,mode='valid');return o
            top=sm(top);bot=sm(bot);hh=bot-top
            up=top+bl_s*0.64*hh;lo=bot-bl_s*0.36*hh
            Y=ys;soft=max(1.0,0.04*d)
            below=np.clip((up[None,:]-Y)/soft+0.5,0,1);above=np.clip((Y-lo[None,:])/soft+0.5,0,1)
            cov=np.maximum(below,above)
            cover=cv2.GaussianBlur(mk*cov*col[None,:],(0,0),0.6)[...,None]
            tex=E.get('tex')
            lidtex=(tex if tex is not None and tex.shape[:2]==(h,w) else E['skin'][None,None,:]*np.ones((h,w,1),'float32'))
            lidtex=lidtex*(0.98-0.03*bl)
            roi=roi*(1-cover)+lidtex*cover
            thick=max(1.1,0.04*d);dist=np.abs(Y-up[None,:])
            lash=np.clip(1-dist/thick,0,1)*mk*min(1.0,bl*2.5)*col[None,:]
            lash=cv2.GaussianBlur(lash,(0,0),0.6)[...,None]*0.80
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
