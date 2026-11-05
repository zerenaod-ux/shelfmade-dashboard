"""Step 1 of cloud lip-sync: cut one face crop + one voice line per spoken line (inputs for LatentSync on the free Kaggle GPU).
Usage: python ls_prep.py <workdir>   -> <workdir>/ls_in/{jobs.json, ls_SS_LL.mp4, ls_SS_LL.wav}"""
import json,subprocess,sys,wave
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fastlip
SR_OUT=16000;PAD=0.35
def prep(work):
    work=Path(work);st=json.loads((work/'story.json').read_text());out=work/'ls_in';out.mkdir(exist_ok=True);jobs=[]
    for si,sh in enumerate(st['shots']):
        im=Image.open(work/f'shot_{si:02d}.png').convert('RGB');W,H=im.size;fs=fastlip.detect(np.asarray(im))
        for li,ln in enumerate(sh['lines']):
            f=fastlip.pick(fs,ln['who'],W)
            if not f or f['w']<40:print('no face for',si,li,ln['who'],flush=True);continue
            g=fastlip.mouth_geom(f);mw=g['mw']
            side=int(min(W,H,max(f['w']*2.3,mw*6)));cx=f['x']+f['w']/2;cy=f['y']+f['h']*0.52
            x0=int(round(min(max(cx-side/2,0),W-side)));y0=int(round(min(max(cy-side/2,0),H-side)))
            crop=im.crop((x0,y0,x0+side,y0+side)).resize((512,512),Image.LANCZOS)
            key=f'ls_{si:02d}_{li:02d}';crop.save(out/f'{key}.png')
            with wave.open(str(work/f'line_{si:02d}_{li:02d}.wav')) as w:
                sr=w.getframerate();ch=w.getnchannels();a=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype('float32')/32768
            if ch>1:a=a.reshape(-1,ch).mean(1)
            d=len(a)/sr;a=np.concatenate([a,np.zeros(int(PAD*sr),dtype='float32')])
            tmp=out/f'{key}_src.wav'
            with wave.open(str(tmp),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(tmp),'-ar',str(SR_OUT),'-ac','1',str(out/f'{key}.wav')],check=True);tmp.unlink()
            dur=d+PAD+0.3
            subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','25','-i',str(out/f'{key}.png'),'-t',f'{dur:.2f}','-c:v','libx264','-crf','12','-pix_fmt','yuv420p',str(out/f'{key}.mp4')],check=True)
            (out/f'{key}.png').unlink()
            hx,hy=1.45*mw,1.2*mw;ccx,ccy=g['cx'],g['cy']+0.70*mw
            win=[int(max(x0,ccx-hx)),int(max(y0,ccy-hy)),int(min(x0+side,ccx+hx)),int(min(y0+side,ccy+hy))]
            jobs.append({'key':key,'si':si,'li':li,'who':ln['who'],'x0':x0,'y0':y0,'side':side,'win':win,'mw':float(mw),'dur':round(d,3)})
            print('prepared',key,ln['who'],'face',round(f['w']),'crop',side,flush=True)
    (out/'jobs.json').write_text(json.dumps({'jobs':jobs}))
    print('LS_PREP_DONE',len(jobs),'lines',flush=True);return jobs
if __name__=='__main__':prep(sys.argv[1])
