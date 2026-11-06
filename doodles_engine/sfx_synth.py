"""Action sounds for AnimationDoodles, synthesized from noise/sine math (no downloads, no licenses). Sample rate = render.py SR (24000). seed(n) makes a cue repeatable."""
import numpy as np
from scipy.signal import butter, sosfilt
SR=24000; rng=np.random.default_rng(7)
def seed(n):
    global rng
    rng=np.random.default_rng(int(n)%(2**32))
def t(d): return np.arange(int(SR*d))/SR
def env(n,a=0.002,d=0.05,sustain=0.0):
    e=np.exp(-np.arange(n)/(SR*d)); k=max(1,int(SR*a)); e[:k]*=np.linspace(0,1,k); return e
def bp(x,lo,hi,o=3):
    hi=min(hi,SR/2*0.92); lo=min(lo,hi*0.8)
    return sosfilt(butter(o,[lo,hi],btype='band',fs=SR,output='sos'),x)
def lp(x,f,o=3): return sosfilt(butter(o,min(f,SR/2*0.9),btype='low',fs=SR,output='sos'),x)
def hp(x,f,o=3): return sosfilt(butter(o,min(f,SR/2*0.9),btype='high',fs=SR,output='sos'),x)
def place(buf,x,at,g=1.0):
    i=int(at*SR); j=min(len(buf),i+len(x))
    if i<len(buf): buf[i:j]+=x[:j-i]*g
def mix(dur,items):
    b=np.zeros(int(SR*dur))
    for x,at,g in items: place(b,x,at,g)
    return b
def tap(bright=1.0,f=1800):
    n=int(SR*0.06); x=bp(rng.standard_normal(n),f*0.6,min(9000,f*3))*env(n,0.0005,0.008)
    th=np.sin(2*np.pi*140*t(0.06))*env(n,0.0005,0.012)*0.6
    return (x*bright+th)
def typing(d=2.6,key=1.0,f=1800):
    b=np.zeros(int(SR*d)); at=0.1
    while at<d-0.15:
        place(b,tap(rng.uniform(.6,1.1),f*rng.uniform(.85,1.2)),at,rng.uniform(.5,1)*key)
        at+=rng.choice([.07,.09,.11,.14,.22,.35])
    return b
def clack(): # laptop key
    n=int(SR*0.09); x=bp(rng.standard_normal(n),900,7000)*env(n,.0005,.010)
    return x+np.sin(2*np.pi*220*t(.09))*env(n,.0005,.02)*0.7
def laptop(d=2.6):
    b=np.zeros(int(SR*d)); at=.1
    while at<d-.2: place(b,clack(),at,rng.uniform(.6,1)); at+=rng.choice([.06,.08,.1,.13,.2,.4])
    return b
def ping():
    x=np.zeros(int(SR*1.2))
    for f,at,g in ((1318.5,0,1),(1760,0.16,1.0)):
        s=t(1.0); w=(np.sin(2*np.pi*f*s)+.3*np.sin(2*np.pi*2*f*s)+.1*np.sin(2*np.pi*3*f*s))*np.exp(-s*5.5)
        place(x,w,at,g*0.6)
    return x
def buzz(n=3):
    x=np.zeros(int(SR*(n*0.4+.1))); 
    for k in range(n):
        s=t(.25); w=np.sign(np.sin(2*np.pi*165*s))*0.4+np.sin(2*np.pi*165*s)*.6
        w=lp(w*(1+0.3*np.sin(2*np.pi*40*s)),1200)*np.minimum(1,np.minimum(s*40,(.25-s)*40))
        place(x,w,0.05+k*.4,0.8)
    return x
def whoosh(d=.55):
    n=int(SR*d); x=rng.standard_normal(n); out=np.zeros(n); m=24
    for i in range(m):
        a,b=int(n*i/m),int(n*(i+1)/m); fc=500+3500*(i/m)**1.5
        out[a:b]=bp(x[a:b],fc*.7,fc*1.5,2) if b-a>64 else 0
    return out*np.sin(np.pi*np.arange(n)/n)**1.5*1.4
def knock(n=3):
    b=np.zeros(int(SR*(n*.26+.5)))
    for k in range(n):
        m=int(SR*.22); s=t(.22); body=np.sin(2*np.pi*(95-30*s*3)*s)*np.exp(-s*28); cl=bp(rng.standard_normal(m),300,1800)*np.exp(-s*60)
        place(b,(body*1.0+cl*.6),.05+k*.26,1)
    return b
def step(h=1.0):
    m=int(SR*.2); s=t(.2); x=lp(rng.standard_normal(m),420)*np.exp(-s*30)+np.sin(2*np.pi*70*s)*np.exp(-s*22)*.9
    return x*h
def steps(n=6,gap=.46):
    b=np.zeros(int(SR*(n*gap+.3)))
    for k in range(n): place(b,step(rng.uniform(.8,1.1)),.05+k*gap+rng.uniform(-.02,.02),.9)
    return b
def tick(n=8):
    b=np.zeros(int(SR*(n*.5+.2)))
    for k in range(n):
        m=int(SR*.05); f=2400 if k%2==0 else 1900
        x=bp(rng.standard_normal(m),f*.7,f*1.4)*np.exp(-t(.05)*120)+np.sin(2*np.pi*f/2*t(.05))*np.exp(-t(.05)*90)*.5
        place(b,x,.05+k*.5,.9)
    return b
def mug():
    s=t(.9); x=sum(g*np.sin(2*np.pi*f*s)*np.exp(-s*d) for f,g,d in ((2140,1,9),(3330,.7,12),(5210,.4,16),(1020,.5,7)))
    n=int(SR*.02); x[:n]+=rng.standard_normal(n)*.8
    return x*.5
def blanket(d=1.2):
    n=int(SR*d); x=lp(hp(rng.standard_normal(n),200),2200)
    am=np.abs(lp(rng.standard_normal(n),9,2)); am/=am.max()
    return x*(am**1.5)*np.sin(np.pi*np.arange(n)/n)**.7*1.5
def sigh(d=1.5):
    n=int(SR*d); x=rng.standard_normal(n); out=np.zeros(n)
    for f,g in ((600,1),(1500,.6),(2800,.35)): out+=bp(x,f*.85,f*1.15,2)*g
    e=np.sin(np.pi*(np.arange(n)/n)**.6)**1.6; return out*e*.9
def alarm(n=4):
    b=np.zeros(int(SR*(n*.22+.1)))
    for k in range(n):
        s=t(.12); w=np.sign(np.sin(2*np.pi*2200*s))*.5*np.minimum(1,np.minimum(s*200,(.12-s)*200)); place(b,lp(w,5000),.03+k*.22,.8)
    return b
def heartbeat(n=4):
    b=np.zeros(int(SR*(n*.9+.3)))
    for k in range(n):
        for off,g in ((0,1),(.22,.7)):
            s=t(.18); place(b,np.sin(2*np.pi*(60-15*s*5)*s)*np.exp(-s*20),.05+k*.9+off,g)
    return b
def boing():
    s=t(.7); f=300+200*np.exp(-s*5)*np.sin(2*np.pi*14*s)+600*np.exp(-s*10)
    ph=2*np.pi*np.cumsum(f)/SR; return np.sin(ph)*np.exp(-s*5)*.8
def pop():
    s=t(.18); return np.sin(2*np.pi*np.cumsum(900*np.exp(-s*22)+200)/SR)*np.exp(-s*20)

CUES={'phone_typing':lambda:typing(),'laptop_typing':lambda:laptop(),'ping':ping,'phone_buzz':lambda:buzz(2),'swoosh':whoosh,'door_knock':knock,
      'footsteps':lambda:steps(4),'mug':mug,'blanket':blanket,'sigh':sigh,'alarm':lambda:alarm(3),'heartbeat':lambda:heartbeat(3),'boing':boing,'pop':pop}
def tick_loop(seconds):
    n=int(seconds/0.5)+1; x=tick(n); return x[:int(SR*seconds)]
def make(name,peak=0.8):
    x=CUES[name]() if name in CUES else np.zeros(1)
    return x/(np.max(np.abs(x))+1e-9)*peak
