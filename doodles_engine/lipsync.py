"""Lip-sync for the still-picture Shorts, using the approved local JoyVASA + LivePortrait engine (free, no cloud).
Run with the MindDoodles native python (.venv), working directory = minddoodles-studio:
    .venv/bin/python doodles_engine/lipsync.py <workdir>
For every spoken line: find that character's face in the shot picture, make speech-driven mouth motion from the line's audio,
draw 16 mouth frames per second and save them (lip_SS_LL.npz). render.py blends them into the picture. Resumable; a line that
fails is skipped (the video still renders, just without that mouth motion)."""
import json,os,sys,time
from pathlib import Path
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK','1')
HERE=Path(__file__).resolve().parent;NATIVE=HERE.parent
sys.path.insert(0,str(NATIVE))
from studio import speech_runtime as R
import numpy as np,cv2,torch,soundfile as sf
from scipy.signal import resample_poly
FPS=16;YUNET=NATIVE/'data/engines/yunet/face_detection_yunet_2023mar.onnx'
def log(*a):print(time.strftime('%H:%M:%S'),*a,flush=True)
def faces(img_bgr):
    d=cv2.FaceDetectorYN.create(str(YUNET),'',(0,0),0.25,0.3,10);h,w=img_bgr.shape[:2];d.setInputSize((w,h));_,f=d.detect(img_bgr)
    return [] if f is None else [tuple(float(x) for x in r[:4])+(float(r[14]),) for r in f]
def pick_face(fs,who,w):
    if not fs:return None
    want=0.30*w if who=='leo' else 0.70*w
    return min(fs,key=lambda r:abs((r[0]+r[2]/2)-want)-30*r[4])
def square(f,w,h,grow=1.25):
    x,y,bw,bh,_=f;s=max(bw,bh)*grow;cx=x+bw/2;cy=y+bh/2+0.02*bh
    x1=int(round(cx-s/2));y1=int(round(cy-s/2));x2=int(round(cx+s/2));y2=int(round(cy+s/2))
    x1=max(0,x1);y1=max(0,y1);x2=min(w,x2);y2=min(h,y2)
    return x1,y1,x2,y2
def prepare(m,dev,crop):
    image=R.frame_tensor(crop).to(dev)
    k=R.kp_info(image,m['motion_extractor']);r=R.get_rotation_matrix(k['pitch'],k['yaw'],k['roll']);f=m['appearance_feature_extractor'](image)
    xs=k['scale'][...,None]*(k['kp']@r+k['exp']);xs[:,:,:2]+=k['t'][:,None,:2]
    idx=[6,12,14,17,19,20]
    def run(exp):
        delta=k['exp'].clone();delta[:,idx]=torch.as_tensor(exp,dtype=torch.float32,device=dev)[None,idx]
        xd=k['scale'][...,None]*(k['kp']@r+delta);xd[:,:,:2]+=k['t'][:,None,:2]
        out=m['spade_generator'](feature=m['warping_module'](f,kp_source=xs,kp_driving=xd)['out'])
        return cv2.cvtColor((out[0].permute(1,2,0).clamp(0,1).float().cpu().numpy()*255).astype(np.uint8),cv2.COLOR_RGB2BGR)
    return run
def motion(model,a,wav,cache):
    if cache.exists():return np.load(cache)['exp']
    audio,rate=sf.read(wav);audio=resample_poly(audio,16000,rate).astype(np.float32)
    audio=torch.from_numpy(audio);audio=torch.nn.functional.pad(audio,(1280,640))
    n=round(len(audio)/16000*25);required=round(a.n_motions*16000/a.fps)
    if len(audio)>required:raise ValueError('line longer than the motion window')
    audio=torch.nn.functional.pad(audio,(0,required-len(audio)))
    ind=torch.ones((1,a.n_motions)) if a.use_indicator else None
    if ind is not None:ind[:,n:]=0
    mo,_,_=model.sample(audio[None],indicator=ind,cfg_mode='incremental',cfg_scale=2.8,dynamic_threshold=0)
    import pickle
    class U(pickle.Unpickler):
        def find_class(self,module,name):
            if (module,name) in [('numpy.core.multiarray','_reconstruct'),('numpy','ndarray'),('numpy','dtype')]:return super().find_class(module,name)
            raise pickle.UnpicklingError('Unexpected template global')
    with open(R.MODELS/'JoyVASA/motion_template/motion_template.pkl','rb') as f:t=U(f).load()
    exp=mo[0,:n,:63].cpu().numpy()*np.asarray(t['std_exp'])+np.asarray(t['mean_exp'])
    exp=exp[2:2+round(sf.info(wav).duration*25)].reshape(-1,21,3)
    np.savez(cache,exp=exp);return exp
def main():
    work=Path(sys.argv[1]);st=json.loads((work/'story.json').read_text())
    torch.set_num_threads(max(2,(os.cpu_count() or 8)-2))
    m=R.load_live();model,a=R.load_motion()
    dev=torch.device('cpu')
    if torch.backends.mps.is_available() and os.environ.get('LIPSYNC_CPU')!='1':
        try:
            for k in m:m[k]=m[k].to('mps')
            dev=torch.device('mps')
        except Exception as e:log('MPS unavailable, using CPU:',e)
    log('lip-sync device:',dev)
    t_all=time.time();done=0;skipped=0
    for si,sh in enumerate(st['shots']):
        img=cv2.imread(str(work/f'shot_{si:02d}.png'))
        if img is None:continue
        h,w=img.shape[:2];fs=faces(img)
        runs={}
        for li,ln in enumerate(sh['lines']):
            out=work/f'lip_{si:02d}_{li:02d}.npz'
            if out.exists():done+=1;continue
            try:
                f=pick_face(fs,ln['who'],w)
                if f is None:raise ValueError('no face found')
                box=square(f,w,h);x1,y1,x2,y2=box
                if min(x2-x1,y2-y1)<60:raise ValueError('face too small')
                key=ln['who']
                if key not in runs:runs[key]=prepare(m,dev,img[y1:y2,x1:x2])
                wav=work/f'line_{si:02d}_{li:02d}.wav';t0=time.time()
                exp=motion(model,a,str(wav),work/f'motion_{si:02d}_{li:02d}.npz')
                dur=len(exp)/25;n=int(dur*FPS)+1;frames=[]
                for i in range(n):
                    frames.append(runs[key](exp[min(len(exp)-1,round(i/FPS*25))]))
                np.savez_compressed(out,frames=np.stack(frames),box=np.array(box),fps=FPS)
                done+=1;log(f'shot {si} line {li} ({ln["who"]}) {n} mouth frames in {time.time()-t0:.0f}s')
            except Exception as e:
                skipped+=1;log(f'shot {si} line {li} skipped: {e}')
    log(f'LIPSYNC DONE lines={done} skipped={skipped} total={time.time()-t_all:.0f}s')
if __name__=='__main__':main()
