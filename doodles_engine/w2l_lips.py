"""Real lip-sync, free and fast: Wav2Lip (already installed in minddoodles-studio/Easy-Wav2Lip) driven by each spoken line's audio.
Run with the wav2lip-venv python:  wav2lip-venv/bin/python doodles_engine/w2l_lips.py <workdir>
For each line: find the speaker's face, make 25 mouth frames/second, save lip_SS_LL.npz (frames BGR, box, fps) - render.py blends them in."""
import json,sys,time,os
from pathlib import Path
import time as _t;_t0=_t.time()
print('importing torch...',flush=True)
import numpy as np,cv2,torch
print('torch ok',round(_t.time()-_t0),'s',flush=True)
NATIVE=Path(__file__).resolve().parent.parent;EW=Path.home()/'Dev/_ops/w2l'
sys.path.insert(0,str(EW))
from models import Wav2Lip
YUNET=NATIVE/'data/engines/yunet/face_detection_yunet_2023mar.onnx'
FPS=25
def log(*a):print(time.strftime('%H:%M:%S'),*a,flush=True)
def _hz2mel(f):
    f=np.asarray(f,dtype='float64');lin=f/(200./3);lg=np.log(6.4)/27.;return np.where(f>=1000,15+np.log(np.maximum(f,1e-9)/1000)/lg,lin)
def _mel2hz(m):
    m=np.asarray(m,dtype='float64');lg=np.log(6.4)/27.;return np.where(m>=15,1000*np.exp(lg*(m-15)),(200./3)*m)
def _melbank(sr=16000,n_fft=800,n_mels=80,fmin=55,fmax=7600):
    fr=np.linspace(0,sr/2,1+n_fft//2);pts=_mel2hz(np.linspace(_hz2mel(fmin),_hz2mel(fmax),n_mels+2));fd=np.diff(pts)
    ramps=pts[:,None]-fr[None];w=np.zeros((n_mels,len(fr)))
    for i in range(n_mels):w[i]=np.maximum(0,np.minimum(-ramps[i]/fd[i],ramps[i+2]/fd[i+1]))
    return w*(2.0/(pts[2:n_mels+2]-pts[:n_mels]))[:,None]
def _load16k(p):
    import wave
    with wave.open(str(p),'rb') as w:
        sr=w.getframerate();ch=w.getnchannels();raw=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype('float64')/32768
    if ch>1:raw=raw.reshape(-1,ch).mean(1)
    if sr!=16000:
        n=int(len(raw)*16000/sr);raw=np.interp(np.linspace(0,len(raw)-1,n),np.arange(len(raw)),raw)
    return raw
def mel(wav):
    y=_load16k(wav);y=np.append(y[0],y[1:]-0.97*y[:-1])
    n_fft,hop=800,200;y=np.pad(y,(n_fft//2,n_fft//2),mode='reflect');win=np.hanning(n_fft+1)[:-1]
    nfr=1+(len(y)-n_fft)//hop;idx=np.arange(n_fft)[None]+hop*np.arange(nfr)[:,None]
    S=np.abs(np.fft.rfft(y[idx]*win,axis=1)).T
    D=20*np.log10(np.maximum(1e-5,_melbank()@S))-20
    return np.clip(8*((D+100)/100)-4,-4,4).astype('float32')
def faces(img):
    d=cv2.FaceDetectorYN.create(str(YUNET),'',(0,0),0.25,0.3,10);h,w=img.shape[:2];d.setInputSize((w,h));_,f=d.detect(img)
    return [] if f is None else [tuple(float(x) for x in r[:4])+(float(r[14]),)+tuple(float(x) for x in r[10:14])+tuple(float(x) for x in r[4:8]) for r in f]
def pick(fs,who,w):
    if not fs:return None
    want=0.30*w if who=='leo' else 0.70*w
    return min(fs,key=lambda r:abs((r[0]+r[2]/2)-want)-30*r[4])
def load_model():
    m=Wav2Lip();ck=torch.load(str(Path.home()/'Dev/_ops/w2l/Wav2Lip_GAN.pth'),map_location='cpu')
    sd={k.replace('module.',''):v for k,v in ck['state_dict'].items()};m.load_state_dict(sd);return m.eval()
def main():
    work=Path(sys.argv[1]);st=json.loads((work/'story.json').read_text());print('loading Wav2Lip model...',flush=True);model=load_model();print('model ok',round(_t.time()-_t0),'s',flush=True);torch.set_num_threads(max(2,(os.cpu_count() or 8)-2))
    t_all=time.time();n_ok=0
    for si,sh in enumerate(st['shots']):
        img=cv2.imread(str(work/f'shot_{si:02d}.png'))
        if img is None:continue
        H,W=img.shape[:2];fs=faces(img)
        for li,ln in enumerate(sh['lines']):
            out=work/f'lip_{si:02d}_{li:02d}.npz'
            if out.exists() and not os.environ.get('W2L_FORCE'):n_ok+=1;continue
            try:
                f=pick(fs,ln['who'],W)
                if f is None:raise ValueError('no face')
                x,y,w,h=f[:4];x1=int(max(0,x-.04*w));x2=int(min(W,x+w+.04*w));y1=int(max(0,y+.02*h));y2=int(min(H,y+h*1.08))
                mx,my=(f[5]+f[7])/2,(f[6]+f[8])/2;mw_=max(12.,((f[7]-f[5])**2+(f[8]-f[6])**2)**.5)
                zb=img[max(0,int(my-.5*mw_)):int(my+.6*mw_),max(0,int(mx-.7*mw_)):int(mx+.7*mw_)];hsv=cv2.cvtColor(zb,cv2.COLOR_BGR2HSV);gr=cv2.cvtColor(zb,cv2.COLOR_BGR2GRAY)
                if float(((hsv[...,1]<80)&(hsv[...,2]>165)).mean())>0.01 or float((gr<80).mean())>0.15:
                    np.savez_compressed(out,frames=np.zeros((0,2,2,3),'uint8'),box=np.array([x1,y1,x2,y2]),fps=FPS);log(f'shot {si} line {li} mouth already open in the picture - left as drawn');continue
                # straighten the face first (Wav2Lip only works well on upright faces), then rotate the mouth frames back
                e1,e2=sorted([(f[9],f[10]),(f[11],f[12])]);c1,c2=sorted([(f[5],f[6]),(f[7],f[8])])
                ang=float(np.clip((np.arctan2(e2[1]-e1[1],e2[0]-e1[0])+np.arctan2(c2[1]-c1[1],c2[0]-c1[0]))/2,-0.6,0.6))
                cx_,cy_=x+w/2,y+h/2;R=cv2.getRotationMatrix2D((cx_,cy_),float(np.degrees(ang)),1.0);Rinv=cv2.invertAffineTransform(R)
                rimg=cv2.warpAffine(img,R,(W,H),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
                rm=R@np.array([mx,my,1.0]);ax1=int(max(0,cx_-.54*w));ax2=int(min(W,cx_+.54*w));ay1=int(max(0,y+.02*h));ay2=int(min(H,y+1.08*h))
                crop=rimg[ay1:ay2,ax1:ax2];face=cv2.resize(crop,(96,96),interpolation=cv2.INTER_AREA)
                M=mel(work/f'line_{si:02d}_{li:02d}.wav');n=int(M.shape[1]*200/16000*FPS)+1;chunks=[]
                for i in range(n):
                    s=int(i*80./FPS);c=M[:,s:s+16]
                    if c.shape[1]<16:c=M[:,-16:] if M.shape[1]>=16 else np.pad(M,((0,0),(0,16-M.shape[1])))
                    chunks.append(c)
                masked=face.copy();masked[48:]=0
                fin=np.concatenate([masked,face],axis=2).astype('float32')/255.   # 96x96x6
                t0=time.time();frames=[]
                with torch.no_grad():
                    for b in range(0,n,64):
                        mb=torch.from_numpy(np.stack(chunks[b:b+64])[:,None]).float();fb=torch.from_numpy(np.stack([fin]*len(mb)).transpose(0,3,1,2)).float()
                        o=model(mb,fb).cpu().numpy().transpose(0,2,3,1)*255.;frames.append(np.clip(o,0,255).astype('uint8'))
                fr=np.concatenate(frames);base_=crop.astype('float32')
                bh_,bw_=base_.shape[:2];yy,xx=np.mgrid[0:bh_,0:bw_];dd=np.hypot(xx-(rm[0]-ax1),yy-(rm[1]-ay1))/mw_
                ring=(dd>0.95)&(dd<1.7);bring=base_[ring].mean(0)                      # skin just around the mouth, as drawn in the picture
                def fin_(a):
                    a=cv2.resize(a,(bw_,bh_),interpolation=cv2.INTER_LANCZOS4).astype('float32')
                    a=a-(a[ring].mean(0)-bring)                                         # same skin tone as the real face (no pale lips)
                    bl=cv2.GaussianBlur(a,(0,0),1.0);a=a+0.9*(a-bl)                      # a little crispness
                    can=np.zeros((H,W,3),'uint8');can[ay1:ay2,ax1:ax2]=np.clip(a,0,255).astype('uint8')
                    return cv2.warpAffine(can,Rinv,(W,H),flags=cv2.INTER_LINEAR)[y1:y2,x1:x2]   # back to the picture's own tilt
                fr=np.stack([fin_(a) for a in fr])
                # per-frame safety: where the generated mouth shows dark maroon smears, fade back to the real picture
                ez,ey=int(mx-x1),int(my-y1);yy2,xx2=np.mgrid[0:fr.shape[1],0:fr.shape[2]];ell=(((xx2-ez)/(.8*mw_))**2+((yy2-ey)/(.55*mw_))**2)<1
                alpha=np.ones(len(fr),'float32')
                for k_,a_ in enumerate(fr):
                    px_=a_[ell].astype('float32');B,G,Rr=px_[:,0],px_[:,1],px_[:,2];lum=(Rr+G+B)/3
                    bad=float(((((Rr-G)>58)&(lum<85))|((lum<105)&(B>=G*0.95))).mean())
                    alpha[k_]=1.0 if bad<0.05 else float(np.clip(1-(bad-0.05)/0.07,0.0,1.0))
                alpha=np.convolve(np.pad(alpha,2,mode='edge'),np.ones(5)/5,mode='valid').astype('float32')
                np.savez_compressed(out,frames=fr,box=np.array([x1,y1,x2,y2]),fps=FPS,mc=np.array([mx-x1,my-y1,mw_],dtype='float32'),alpha=alpha);n_ok+=1
                log(f'shot {si} line {li} ({ln["who"]}) {n} frames in {time.time()-t0:.0f}s')
            except Exception as e:log(f'shot {si} line {li} skipped: {e}')
    log(f'W2L DONE lines={n_ok} total={time.time()-t_all:.0f}s')
if __name__=='__main__':main()
