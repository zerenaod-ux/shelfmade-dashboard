"""AnimationDoodles Short renderer: still pictures + two voices -> 1080x1920 video.
Camera push/pull, speaker-follow, speech bounce, word-highlight captions, concept chip, end card, ducked music.
No AI video model needed. Usage: python render.py <workdir>   (workdir holds story.json, shot_XX.png, line_XX_YY.wav)"""
import json,math,re,subprocess,sys,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
    import eyes
except Exception as _e:
    eyes=None;print('eyes unavailable:',_e,flush=True)
try:
    import fastlip
except Exception as _e:
    fastlip=None;print('fast mouth unavailable:',_e,flush=True)
from PIL import Image,ImageDraw,ImageFont,ImageFilter
W,H,FPS=1080,1920,30
GAP=0.24;LEAD=0.35;SHOT_TAIL=0.30;END=0.0;SR=24000
FONTS=['/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf','/System/Library/Fonts/Supplemental/Arial Bold.ttf','/System/Library/Fonts/Helvetica.ttc',
       '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
def font(size):
    for f in FONTS:
        try:return ImageFont.truetype(f,size)
        except Exception:pass
    return ImageFont.load_default()
COLOR={'leo':(255,214,90),'mia':(127,224,208)}
FOCUS={'leo':0.30,'mia':0.70,'both':0.50}
def read_wav(p):
    with wave.open(str(p)) as w:
        n=w.getnframes();sr=w.getframerate();a=np.frombuffer(w.readframes(n),dtype='<i2').astype('float32')/32768.0
        if w.getnchannels()>1:a=a.reshape(-1,w.getnchannels()).mean(1)
    if sr!=SR:a=np.interp(np.linspace(0,len(a)-1,int(len(a)*SR/sr)),np.arange(len(a)),a).astype('float32')
    return a
def weight(w):return max(1,len(re.findall(r'[aeiouy]+',w.lower())))+(0.6 if re.search(r'[,;:]$',w) else 0)+(0.9 if re.search(r'[.!?…]$',w) else 0)
def wrap(draw,words,fnt,maxw):
    lines=[[]]
    for i,w in enumerate(words):
        t=' '.join(words[j] for j in lines[-1]+[i])
        if lines[-1] and draw.textlength(t,font=fnt)>maxw:lines.append([i])
        else:lines[-1].append(i)
    return lines
class Caption:
    def __init__(self):self.cache={};self.f=font(74);self.d=ImageDraw.Draw(Image.new('RGBA',(10,10)))
    def get(self,text,who,active):
        key=(text,who,active)
        if key in self.cache:return self.cache[key]
        words=text.split();lines=wrap(self.d,words,self.f,900)
        lh=92;h=lh*len(lines)+40;img=Image.new('RGBA',(W,h),(0,0,0,0));d=ImageDraw.Draw(img)
        for li,idxs in enumerate(lines):
            full=' '.join(words[i] for i in idxs);x=(W-d.textlength(full,font=self.f))/2;y=20+li*lh
            for i in idxs:
                col=COLOR.get(who,(255,255,255)) if i==active else (255,255,255)
                d.text((x,y),words[i],font=self.f,fill=col,stroke_width=9,stroke_fill=(15,10,5))
                x+=d.textlength(words[i]+' ',font=self.f)
        self.cache[key]=img
        if len(self.cache)>400:self.cache.clear()
        return img
def chip(text):
    f=font(46);d=ImageDraw.Draw(Image.new('RGBA',(10,10)));w=int(d.textlength(text,font=f))+70
    img=Image.new('RGBA',(w,92),(0,0,0,0));dd=ImageDraw.Draw(img)
    dd.rounded_rectangle((0,0,w-1,91),radius=46,fill=(18,32,30,215),outline=(224,189,118,255),width=3)
    dd.text((35,20),text,font=f,fill=(255,236,190));return img
def build(work):
    work=Path(work);st=json.loads((work/'story.json').read_text())
    shots=st['shots'];t=LEAD;timeline=[];voice=[];seg=[]
    for si,sh in enumerate(shots):
        s0=t;lines=[]
        for li,ln in enumerate(sh['lines']):
            a=read_wav(work/f'line_{si:02d}_{li:02d}.wav');d=len(a)/SR
            lines.append({'who':ln['who'],'text':ln['text'],'start':t,'end':t+d,'audio':a,'si':si,'li':li});t+=d+GAP
        t+=SHOT_TAIL-GAP;timeline.append({'start':s0,'end':t,'lines':lines});
    total=t+END
    n=int(total*SR);track=np.zeros(n,dtype='float32')
    for sh in timeline:
        for ln in sh['lines']:
            i=int(ln['start']*SR);track[i:i+len(ln['audio'])]+=ln['audio']
    pk=float(np.max(np.abs(track)))or 1.0
    if pk>0.97:track*=0.97/pk
    # speech envelope per frame
    nf=int(total*FPS);env=np.zeros(nf,dtype='float32');hop=SR//FPS
    for f in range(nf):
        seg_=track[f*hop:(f+1)*hop]
        env[f]=math.sqrt(float(np.mean(seg_**2))) if len(seg_) else 0
    ref=float(np.percentile(env[env>0.004],90)) if (env>0.004).any() else 1.0
    env=np.clip(env/ref,0,1.2);k=np.array([.25,.5,.25]);env=np.convolve(env,k,mode='same')
    wav_path=work/'voice.wav'
    with wave.open(str(wav_path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(track,-1,1)*32767).astype('<i2').tobytes())
    return st,timeline,total,env,wav_path
def load_lips(work,timeline):
    lips={}
    for sh in timeline:
        for ln in sh['lines']:
            p=work/f"lip_{ln['si']:02d}_{ln['li']:02d}.npz"
            if not p.is_file():continue
            try:
                z=np.load(p);fr=z['frames']
                if len(fr)==0:continue
                x1,y1,x2,y2=[int(v) for v in z['box']];bw,bh=x2-x1,y2-y1
                mask=Image.new('L',(bw,bh),0)
                if 'mc' in z.files:
                    mx_,my_,mw2=[float(v) for v in z['mc']];ImageDraw.Draw(mask).ellipse((mx_-.72*mw2,my_-.42*mw2,mx_+.72*mw2,my_+.62*mw2),fill=255);mask=mask.filter(ImageFilter.GaussianBlur(max(1.5,mw2*.08)))
                else:
                    ImageDraw.Draw(mask).ellipse((bw/2-bw*.43,bh*.73-bh*.23,bw/2+bw*.43,bh*.73+bh*.23),fill=255);mask=mask.filter(ImageFilter.GaussianBlur(3.5))
                lips[(ln['si'],ln['li'])]={'frames':[Image.fromarray(np.ascontiguousarray(f[:,:,::-1])).resize((bw,bh),Image.LANCZOS) for f in fr],'xy':(x1,y1),'mask':mask,'fps':int(z['fps']),'alpha':(z['alpha'] if 'alpha' in z.files else None)}
            except Exception as ex:print('lip file unusable',p.name,ex)
    print('lip-synced lines:',len(lips),flush=True);return lips
def variant_mask(base,vp,face):
    """Real drawn open mouth: align the 'open' picture to the shot (so nose/cheeks do not shift), then use it ONLY inside a tight soft ellipse around the mouth."""
    import cv2
    H,W=base.shape[:2]
    op=np.asarray(Image.open(vp).convert('RGB').resize((W,H),Image.LANCZOS))
    x,y,w,h=face['x'],face['y'],face['w'],face['h']
    try:
        ry0,ry1=int(max(0,y)),int(min(H,y+0.50*h));rx0,rx1=int(max(0,x)),int(min(W,x+w))
        g1=cv2.cvtColor(base[ry0:ry1,rx0:rx1],cv2.COLOR_RGB2GRAY).astype('float32');g2=cv2.cvtColor(op[ry0:ry1,rx0:rx1],cv2.COLOR_RGB2GRAY).astype('float32')
        warp=np.eye(2,3,dtype='float32');_,warp=cv2.findTransformECC(g1,g2,warp,cv2.MOTION_TRANSLATION,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,80,1e-5),None,5)
        if abs(warp[0,2])<0.12*w and abs(warp[1,2])<0.12*h:op=cv2.warpAffine(op,warp,(W,H),flags=cv2.INTER_LINEAR+cv2.WARP_INVERSE_MAP,borderMode=cv2.BORDER_REPLICATE)
    except Exception as ex:print('align skipped',ex,flush=True)
    g=fastlip.mouth_geom(face);cx,cy,mw=g['cx'],g['cy'],g['mw']
    # exact fit: the mask is where the open picture really differs from the closed one (the real mouth shape + the old closed lips), limited to the mouth window so nose/cheeks never change
    win=np.zeros((H,W),'uint8');cv2.ellipse(win,(int(cx),int(cy+0.58*mw)),(int(1.35*mw),int(0.78*mw)),0,0,360,255,-1)
    df=np.abs(op.astype('int16')-base.astype('int16')).max(2)
    k=(df>26).astype('uint8')*255;k=cv2.bitwise_and(k,win)
    _bl=cv2.GaussianBlur(base,(0,0),max(1.5,0.12*mw)).astype('int16');hp=np.abs(base.astype('int16')-_bl).max(2)
    band=np.zeros((H,W),'uint8');cv2.ellipse(band,(int(cx),int(cy+0.15*mw)),(int(1.35*mw),int(0.50*mw)),0,0,360,255,-1)
    k=cv2.bitwise_or(k,cv2.bitwise_and(((hp>9)*255).astype('uint8'),band))   # the original drawn lip line is always covered
    seed=np.zeros((H,W),'uint8');cv2.ellipse(seed,(int(cx),int(cy+0.18*mw)),(int(0.95*mw),int(0.30*mw)),0,0,360,255,-1)
    k=cv2.bitwise_or(k,seed)   # always cover the old closed lip line
    ks=max(3,int(0.22*mw))|1;k=cv2.morphologyEx(k,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(ks,ks)))
    n,lab,stats,_=cv2.connectedComponentsWithStats(k);cl=lab[min(H-1,int(cy+0.2*mw)),min(W-1,int(cx))]
    if cl>0:k=((lab==cl)*255).astype('uint8')
    ds=max(3,int(0.16*mw))|1;k=cv2.dilate(k,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(ds,ds)))
    k=cv2.bitwise_and(k,win)
    kf=k.astype('float32')/255.0;m=cv2.GaussianBlur(kf,(0,0),max(1.6,0.07*mw));core=cv2.GaussianBlur(kf,(0,0),max(2.0,0.22*mw))
    return {'mask':m.astype('float32'),'open':op,'core':core.astype('float32')}
def render(work):
    work=Path(work);st,timeline,total,env,wav_path=build(work)
    imgs=[Image.open(work/f'shot_{i:02d}.png').convert('RGB') for i in range(len(timeline))]
    lips=load_lips(work,timeline)
    geo={};fc={};eg={};life={'leo':eyes.Life(11,total+3),'mia':eyes.Life(23,total+3)} if eyes else {}
    if fastlip and (__import__('os').environ.get('FASTLIP') or any(work.glob('open_*.png')) or (work/'ls_out').is_dir()):
        for si_,im_ in enumerate(imgs):
            try:
                fs_=fastlip.detect(np.asarray(im_))
                for who_ in ('leo','mia'):
                    f_=fastlip.pick(fs_,who_,im_.size[0])
                    if f_ and f_['w']>40:
                        g_=fastlip.mouth_geom(f_)
                        if eyes:
                            try:eg[(si_,who_)]=eyes.geom(np.asarray(im_),f_)
                            except Exception as ex:print('eye geom failed',ex,flush=True)
                        fc[(si_,who_)]=((f_['x']+f_['w']/2)/im_.size[0],(f_['y']+f_['h']*0.55)/im_.size[1])
                        vp_=work/f'open_{si_:02d}_{who_}.png';cp_=work/f'closed_{si_:02d}_{who_}.png'
                        if cp_.is_file():
                            try:
                                _b=np.asarray(imgs[si_]);_G=variant_mask(_b,cp_,f_);_M=_G['mask'][...,None]
                                imgs[si_]=Image.fromarray((_b.astype('float32')*(1-_M)+_G['open'].astype('float32')*_M).clip(0,255).astype('uint8'))
                                geo[(si_,who_)]={'mask':_G['mask'],'open':_b.copy()};print('closed-mouth swap for shot',si_,who_,flush=True)
                            except Exception as ex:print('closed variant unusable',cp_.name,ex,flush=True)
                        elif vp_.is_file():
                            try:geo[(si_,who_)]=variant_mask(np.asarray(im_),vp_,f_)
                            except Exception as ex:print('variant unusable',vp_.name,ex,flush=True)
                        elif not fastlip.is_open(np.asarray(im_),g_):geo[(si_,who_)]=g_
            except Exception as ex:print('face detect failed',si_,ex,flush=True)
        print('fast mouths ready for',len(geo),'faces',flush=True)
    align={}
    for _p in work.glob('align_*.json'):
        try:
            _z=json.loads(_p.read_text());_s=_p.stem.split('_');_sg=np.array(_z['segs'],dtype='float64');_hz=200;_n=int((_sg[-1,1]+0.5)*_hz);_c=np.zeros(_n)
            for _a,_b,_l in _sg:_c[int(_a*_hz):int(_b*_hz)]=_l
            _k=np.exp(-0.5*((np.arange(-int(0.18*_hz),int(0.18*_hz)+1)/_hz)/0.045)**2);_k/=_k.sum();_c=np.convolve(_c,_k,mode='same')*1.25
            align[(int(_s[1]),int(_s[2]))]={'c':np.clip(_c,0,1),'hz':_hz}
        except Exception as ex:print('align file unusable',_p.name,ex,flush=True)
    print('aligned lines:',len(align),flush=True)
    ls_clips={}
    _lj=work/'ls_in'/'jobs.json'
    if (work/'ls_out').is_dir() and _lj.is_file():
        import cv2 as _cv
        for _j in json.loads(_lj.read_text())['jobs']:
            _p=work/'ls_out'/f"{_j['key']}.mp4"
            if not _p.is_file():continue
            try:
                _wx0,_wy0,_wx1,_wy1=_j['win'];_s=512.0/_j['side'];_ww,_wh=_wx1-_wx0,_wy1-_wy0
                _cap=_cv.VideoCapture(str(_p));_fr=[]
                while True:
                    _ok,_b=_cap.read()
                    if not _ok:break
                    if _b.shape[0]!=512 or _b.shape[1]!=512:_b=_cv.resize(_b,(512,512),interpolation=_cv.INTER_AREA)
                    _sub=_b[int(round((_wy0-_j['y0'])*_s)):int(round((_wy1-_j['y0'])*_s)),int(round((_wx0-_j['x0'])*_s)):int(round((_wx1-_j['x0'])*_s))]
                    _fr.append(_cv.cvtColor(_cv.resize(_sub,(_ww,_wh),interpolation=_cv.INTER_CUBIC),_cv.COLOR_BGR2RGB))
                if not _fr:continue
                _mk=np.zeros((_wh,_ww),'float32');_cv.ellipse(_mk,(_ww//2,_wh//2),(int(_ww*0.48),int(_wh*0.48)),0,0,360,1.0,-1)
                _mk=_cv.GaussianBlur(_mk,(0,0),max(1.5,0.16*_j['mw']))
                ls_clips[(_j['si'],_j['li'])]={'fr':_fr,'mask':_mk,'xy':(_wx0,_wy0)}
            except Exception as ex:print('lip-sync clip unusable',_p.name,ex,flush=True)
    print('cloud lip-sync lines:',len(ls_clips),flush=True)
    def lvl(a,t):
        i=int(t*a['hz'])
        return float(a['c'][i]) if 0<=i<len(a['c']) else 0.0
    def omap(om):
        if align:o=float(min(1.0,max(0.0,(om-0.28)/0.32)))
        else:o=float(min(1.0,max(0.0,(om-0.10)/0.40)))
        return o*o*(3-2*o)
    cap=Caption();explain=int(st.get('explain_shot',4));chip_img=chip(st.get('concept',''));
    silent=work/'silent.mp4'
    ff=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p',str(silent)],stdin=subprocess.PIPE)
    mouth={};cam={'z':1.12,'pulse':0.0,'aw':-1,'li':None};fx=0.5;nf=int(total*FPS);end_t=total-END;endfont=font(92);smallfont=font(52)
    for f in range(nf):
        tt=f/FPS
        si=0
        for i,sh in enumerate(timeline):
            if tt>=sh['start']:si=i
        sh=timeline[si];last=si==len(timeline)-1
        D=(sh['end']-sh['start']) + (END if last else 0);u=min(1,max(0,(tt-sh['start'])/D))
        active=None
        for ln in sh['lines']:
            if ln['start']-0.02<=tt<=ln['end']+0.12:active=ln
        tgt=FOCUS.get(active['who'] if active else st['shots'][si].get('focus','both'),0.5);_fy=None
        if active and (si,active['who']) in fc:tgt,_fy=fc[(si,active['who'])]
        fx+=(tgt-fx)*0.07
        e=float(env[min(f+1,len(env)-1)]) if active else 0.0
        # talk-driven camera: wide when quiet, push toward the speaker while talking, punch-in at each line start, pulse on key words
        if active:
            lp=min(1,max(0,(tt-active['start'])/max(active['end']-active['start'],0.01)))
            zt=(1.30+0.11*lp) if si%2==0 else (1.24+0.12*lp)
            pun=0.055*max(0.0,1-(tt-active['start'])/0.30)**2
            _w=active['text'].split();_ws=[weight(x) for x in _w];_tot=sum(_ws);_p=lp*_tot;_acc=0;_aw=len(_w)-1
            for _i,_wt in enumerate(_ws):
                _acc+=_wt
                if _p<_acc:_aw=_i;break
            if _aw!=cam['aw'] or cam['li']!=(active['si'],active['li']):
                cam['aw']=_aw;cam['li']=(active['si'],active['li'])
                if len(_w[_aw].strip('.,!?;:'))>=6 or re.search(r'[!?]$',_w[_aw]):cam['pulse']=1.0
        else:
            u2=min(1,max(0,(tt-sh['start'])/max(sh['end']-sh['start'],0.01)));zt=1.12+0.04*u2;pun=0.0;cam['aw']=-1;cam['li']=None
        cam['z']+=(zt-cam['z'])*0.10;cam['pulse']*=0.86
        z=cam['z']+pun+0.025*cam['pulse']+0.012*e
        fx+=0.004*math.sin(2*math.pi*0.35*tt)*0.15
        fy=((_fy-0.02) if _fy is not None else 0.43-(0.03 if active else 0))-0.004*e+0.004*math.sin(2*math.pi*0.27*tt)
        img=imgs[si]
        _real=bool(active) and isinstance(geo.get((si,active['who'])),dict) and 'open' in geo[(si,active['who'])]
        if active and (active['si'],active['li']) in ls_clips:
            C=ls_clips[(active['si'],active['li'])];_k=min(len(C['fr'])-1,max(0,int((tt-active['start'])*25+0.5)));_wt=max(0.0,min(1.0,(tt-active['start']+0.02)/0.08,(active['end']+0.12-tt)/0.12))
            _a=np.array(img);_x,_y=C['xy'];_hh,_ww2=C['mask'].shape;_m=(C['mask']*_wt)[...,None]
            _a[_y:_y+_hh,_x:_x+_ww2]=(_a[_y:_y+_hh,_x:_x+_ww2].astype('float32')*(1-_m)+C['fr'][_k].astype('float32')*_m).clip(0,255).astype('uint8');img=Image.fromarray(_a)
        elif active and not _real and (active['si'],active['li']) in lips:
            L=lips[(active['si'],active['li'])];_kf=(tt-active['start'])*L['fps'];k=min(len(L['frames'])-1,max(0,int(_kf)));_k2=min(len(L['frames'])-1,k+1);_tb=min(1.0,max(0.0,_kf-k));_patch=L['frames'][k] if (_k2==k or _tb<0.06) else Image.blend(L['frames'][k],L['frames'][_k2],_tb)
            img=img.copy();a_=1.0 if L['alpha'] is None else float(L['alpha'][min(k,len(L['alpha'])-1)])
            if a_>0.02:img.paste(_patch,L['xy'],L['mask'] if a_>=0.98 else L['mask'].point(lambda v,a_=a_:int(v*a_)))
        elif active and (si,active['who']) in geo:
            raw=float(min(1.0,max(0.0,e)**0.8*1.1));_al=align.get((active['si'],active['li']))
            if _al is not None:raw=lvl(_al,tt-active['start']+0.035)
            om_=mouth.get(active['who'],0.0)
            if _al is not None:om_+=(raw-om_)*0.92
            else:om_+=(raw-om_)*(0.66 if raw>om_ else 0.38)
            mouth[active['who']]=om_;o=omap(om_)
            G=geo[(si,active['who'])]
            if 'mask' in G:
                m_=(G['mask']*(np.clip((G['core']-(0.5+0.45*(1-o))+0.08)/0.08,0,1) if 'core' in G else min(1.0,o)))[...,None];img=Image.fromarray((np.asarray(img).astype('float32')*(1-m_)+G['open']*m_).clip(0,255).astype('uint8'))
            else:img=Image.fromarray(fastlip.apply(np.asarray(img),G,o))
        elif not active and mouth:
            for _w in list(mouth):
                mouth[_w]*=0.62
                if mouth[_w]<0.03:mouth[_w]=0.0;continue
                _G=geo.get((si,_w))
                if isinstance(_G,dict) and 'mask' in _G:
                    _o=omap(mouth[_w])
                    if _o>0.01:
                        m_=(_G['mask']*(np.clip((_G['core']-(0.5+0.45*(1-_o))+0.08)/0.08,0,1) if 'core' in _G else min(1.0,_o)))[...,None];img=Image.fromarray((np.asarray(img).astype('float32')*(1-m_)+_G['open']*m_).clip(0,255).astype('uint8'))
        if eyes and eg:
            _arr=None
            for _who in ('leo','mia'):
                _E=eg.get((si,_who))
                if not _E:continue
                if _arr is None:_arr=np.array(img)
                _ex=[ln['start']+0.04 for ln in sh['lines'] if ln['who']==_who and (ln['li']%2==1 or ln['si']%3==0)]
                _bl=life[_who].blink(tt,_ex);_tw=0.0
                if active and active['who']!=_who:_tw=1.0 if FOCUS[active['who']]>FOCUS[_who] else -1.0
                elif active:_tw=0.0
                _gz=life[_who].gaze(tt,_tw,away=(not active and u>0.6))
                eyes.apply(_arr,_E,_bl,_gz)
            if _arr is not None:img=Image.fromarray(_arr)
        iw,ih=img.size;bw,bh=iw/z,ih/z
        cx=min(max(fx*iw,bw/2),iw-bw/2);cy=min(max(fy*ih,bh/2),ih-bh/2)
        frame=img.resize((W,H),Image.BICUBIC,box=(cx-bw/2,cy-bh/2,cx+bw/2,cy+bh/2)).convert('RGBA')
        if tt>=end_t:
            a=min(1,(tt-end_t)/0.45);dark=Image.new('RGBA',(W,H),(10,12,16,int(190*a)));frame=Image.alpha_composite(frame,dark)
            d=ImageDraw.Draw(frame);c=st.get('concept','');ins=st.get('insight','')
            def center(text,y,fnt,fill,wmax=900):
                ws=text.split();ls=wrap(d,ws,fnt,wmax)
                for li,idx in enumerate(ls):
                    s=' '.join(ws[i] for i in idx);x=(W-d.textlength(s,font=fnt))/2
                    d.text((x,y+li*(fnt.size+14)),s,font=fnt,fill=fill+(int(255*a),),stroke_width=0)
                return y+len(ls)*(fnt.size+14)
            y=center(c,640,endfont,(255,214,90));y=center(ins,y+50,smallfont,(255,255,255));center('Follow for more  ·  AnimationDoodles',y+120,font(46),(127,224,208))
        else:
            if active:
                ci=cap.get(active['text'],active['who'],-1)
                words=active['text'].split();ws=[weight(w) for w in words];tot=sum(ws);dur=active['end']-active['start'];p=min(max((tt-active['start'])/max(dur,0.01),0),0.999)*tot
                acc=0;aw=len(words)-1
                for i,wt in enumerate(ws):
                    acc+=wt
                    if p<acc:aw=i;break
                ci=cap.get(active['text'],active['who'],aw)
                frame.alpha_composite(ci,(0,1330))
            if si>=explain and st.get('concept'):frame.alpha_composite(chip_img,((W-chip_img.size[0])//2,150))
        ff.stdin.write(frame.convert('RGB').tobytes())
    ff.stdin.close();ff.wait()
    return silent,wav_path,total
def mix(work,silent,wav_path,total,mood):
    work=Path(work);out=work/'short.mp4'
    music=None
    try:
        for _p in (Path(__file__).resolve().parent.parent,Path(__file__).resolve().parent,Path.home()/'Documents/Codex/2026-10-12/referenced-chatgpt-conversation-this-is-an/outputs/shelfmade-dashboard'):
            if (_p/'music_lab.py').is_file():sys.path.insert(0,str(_p))
        import music_lab,hashlib
        mood={'tense':'dramatic','hopeful':'warm','suspense':'mysterious','sad':'reflective'}.get(mood,mood);_key=work.name
        _v=[music_lab.track(mood)]+sorted((music_lab.BASE/'music').glob(mood+'_v*.mp3'));_h=int(hashlib.md5(_key.encode()).hexdigest(),16);music=_v[_h%len(_v)];_off=(_h>>8)%50;print('music:',music.name,'start',_off,'s',flush=True)
    except Exception as ex:print('music unavailable:',ex)
    if music:
        flt=(f'[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[vo][sc];'
             f'[2:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.9,afade=t=in:st=0:d=0.15,afade=t=out:st={total-0.2:.2f}:d=0.2[mu];'
             '[mu][sc]sidechaincompress=threshold=0.03:ratio=3:attack=40:release=500[du];[vo][du]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[a]')
        cmd=['ffmpeg','-v','error','-y','-i',str(silent),'-i',str(wav_path),'-stream_loop','-1','-ss',str(_off),'-i',str(music),'-filter_complex',flt,'-map','0:v','-map','[a]']
    else:
        cmd=['ffmpeg','-v','error','-y','-i',str(silent),'-i',str(wav_path),'-map','0:v','-map','1:a']
    cmd+=['-t',f'{total:.3f}','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)]
    subprocess.run(cmd,check=True);return out
if __name__=='__main__':
    wd=Path(sys.argv[1]);silent,wav,total=render(wd);o=mix(wd,silent,wav,total,json.loads((wd/'story.json').read_text()).get('mood','curious'));print('RENDERED',o,round(total,1),'s')
