"""Generates ORIGINAL ambient background tracks (no samples, no licences, no attribution).
Run once: python3 music_synth.py   -> music/<mood>.mp3 + music-library.json. Needs numpy + ffmpeg."""
import numpy as np,subprocess,json,sys
from pathlib import Path
SR=44100;BASE=Path(__file__).resolve().parent;OUT=BASE/'music'
def hz(n):return 440*2**((n-69)/12)
def reverb(x,sec=3.2,wet=.38,seed=1):
 r=np.random.default_rng(seed);n=int(SR*sec);t=np.arange(n)/SR
 ir=r.standard_normal((2,n))*np.exp(-t*2.1)/ (n**.5)*40
 out=np.zeros_like(x)
 for c in range(2):
  L=len(x[c])+n;F=1<<(L-1).bit_length()
  y=np.fft.irfft(np.fft.rfft(x[c],F)*np.fft.rfft(ir[c],F),F)[:len(x[c])]
  out[c]=y
 return x*(1-wet)+out*wet
def env(n,a,r):
 e=np.ones(n);ai=int(a*SR);ri=int(r*SR);ai=min(ai,n//2);ri=min(ri,n//2)
 e[:ai]=np.linspace(0,1,ai)**2;e[n-ri:]=np.linspace(1,0,ri)**2;return e
def pad(notes,dur,bright=.5,detune=.004,rng=None):
 n=int(dur*SR);t=np.arange(n)/SR;st=np.zeros((2,n))
 for m in notes:
  f=hz(m)
  for side,d in ((0,-detune),(1,detune),(0,detune/2),(1,-detune/2)):
   sig=np.zeros(n)
   for h in range(1,7):sig+=np.sin(2*np.pi*f*(1+d)*h*t+rng.random()*6.28)/(h**(1+2*(1-bright)))
   st[side]+=sig*(1+.15*np.sin(2*np.pi*.1*t+rng.random()*6))
 e=env(n,dur*.35,dur*.45);return st*e/ (len(notes)*2)
def bell(m,dur=3.5,vel=.5):
 n=int(dur*SR);t=np.arange(n)/SR;f=hz(m)
 s=np.sin(2*np.pi*f*t)+.4*np.sin(2*np.pi*2*f*t)*np.exp(-t*3)+.2*np.sin(2*np.pi*3.01*f*t)*np.exp(-t*5)
 return s*np.exp(-t*1.6)*vel*np.minimum(1,t*200)
def make(name,chords,scale,bpm_notes,rate,sub,bright,seed,loop=96.0):
 rng=np.random.default_rng(seed);N=int(loop*SR);tail=int(6*SR);mix=np.zeros((2,N+tail))
 cd=loop/len(chords)
 for i,ch in enumerate(chords):
  p=pad(ch,cd+6,bright,rng=rng);s=int(i*cd*SR);mix[:,s:s+p.shape[1]]+=p[:,:mix.shape[1]-s]*.55
  if sub:
   n=int((cd+6)*SR);t=np.arange(n)/SR;b=np.sin(2*np.pi*hz(ch[0]-12)*t)*env(n,cd*.4,cd*.5)*.16;mix[:,s:s+n]+=b[:mix.shape[1]-s]
 tt=0.0
 while tt<loop:
  m=int(rng.choice(scale))+12*int(rng.integers(0,2));b=bell(m,vel=float(rng.uniform(.25,.55)));s=int(tt*SR);pan=rng.random()
  seg=b[:mix.shape[1]-s];mix[0,s:s+len(seg)]+=seg*(1-pan)*.18;mix[1,s:s+len(seg)]+=seg*pan*.18
  tt+=float(rng.exponential(rate))+rate*.4
 mix=reverb(mix,wet=.42,seed=seed)
 mix[:,:tail]+=mix[:,N:N+tail];mix=mix[:,:N]
 mix/=np.max(np.abs(mix))*1.15;mix=mix-mix.mean(axis=1,keepdims=True)
 raw=Path('/tmp')/(name+'.f32');(mix.T.astype(np.float32)).tofile(raw)
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(raw),'-af','highpass=f=35,lowpass=f=9000,loudnorm=I=-20:TP=-2:LRA=7','-c:a','libmp3lame','-b:a','160k',str(OUT/(name+'.mp3'))],check=True)
 raw.unlink()
MOODS={
 'calm':   dict(chords=[[48,55,59,64,67],[45,52,60,64,67],[41,48,57,60,64],[43,50,59,62,67]],scale=[72,74,76,79,81,84],rate=4.5,sub=True,bright=.35,seed=11),
 'curious':dict(chords=[[45,52,60,64,67],[41,48,57,60,64],[48,55,60,64,67],[43,50,59,62,66]],scale=[69,72,74,76,79,81,84],rate=1.6,sub=True,bright=.5,seed=22),
 'dramatic':dict(chords=[[38,45,53,57,62],[34,41,50,53,58],[43,50,53,58,62],[38,45,50,57,60]],scale=[62,65,69,70,74],rate=7.0,sub=True,bright=.25,seed=33),
 'warm':   dict(chords=[[43,50,55,59,62],[40,47,55,59,64],[48,55,60,64,67],[50,57,62,66,69]],scale=[67,71,74,76,79,83],rate=3.2,sub=True,bright=.45,seed=44),
 'mysterious':dict(chords=[[38,45,50,57,64],[40,47,52,59,65],[38,45,52,55,62],[36,43,50,55,60]],scale=[74,77,79,81,84,86],rate=5.5,sub=True,bright=.3,seed=55),
 'reflective':dict(chords=[[41,48,57,60,64],[38,45,53,57,60],[34,41,50,53,57],[36,43,52,55,60]],scale=[69,72,74,77,81],rate=3.8,sub=True,bright=.4,seed=66),
}
if __name__=='__main__':
 OUT.mkdir(exist_ok=True)
 for k,v in MOODS.items():make(k,v['chords'],v['scale'],None,v['rate'],v['sub'],v['bright'],v['seed']);print('made',k,flush=True)
 (BASE/'music-library.json').write_text(json.dumps({k:'music/'+k+'.mp3' for k in MOODS},indent=1))
