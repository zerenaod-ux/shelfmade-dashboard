"""Word-and-sound timing for lip-sync. For every voice line, find exactly when each letter/sound is spoken (free wav2vec2 CTC forced alignment of the KNOWN text),
then write align_SS_LL.json = mouth-openness segments [[t0,t1,level],...] (seconds from line start). render.py drives the real drawn mouth from these.
Run with the img-lab python: python3 align.py <workdir>   (first run downloads facebook/wav2vec2-base-960h, ~360 MB; a failure never blocks the video)"""
import json,re,sys,wave
from pathlib import Path
import numpy as np
LEVEL={'A':1.0,'O':0.85,'U':0.65,'E':0.60,'I':0.50,'Y':0.35,'W':0.40,'M':0.0,'B':0.0,'P':0.0,'F':0.10,'V':0.10,"'":0.10}
def level(ch):return LEVEL.get(ch,0.18)
def read16k(p):
    with wave.open(str(p)) as w:
        n=w.getnframes();sr=w.getframerate();a=np.frombuffer(w.readframes(n),dtype='<i2').astype('float32')/32768.0
        if w.getnchannels()>1:a=a.reshape(-1,w.getnchannels()).mean(1)
    if sr!=16000:a=np.interp(np.linspace(0,len(a)-1,int(len(a)*16000/sr)),np.arange(len(a)),a).astype('float32')
    return a
def norm_text(t):
    t=t.upper().replace('’',"'");t=re.sub(r"[^A-Z' ]+",' ',t);t=re.sub(r"\s+",' ',t).strip();return t.replace(' ','|')
def trellis(em,tokens,blank=0):
    T=em.shape[0];J=len(tokens);tr=np.full((T,J+1),-np.inf,dtype='float64');tr[0,0]=0;tr[1:,0]=np.cumsum(em[1:,blank])
    for t in range(T-1):tr[t+1,1:]=np.maximum(tr[t,1:]+em[t,blank],tr[t,:-1]+em[t,tokens])
    return tr
def backtrack(tr,em,tokens,blank=0):
    t,j=tr.shape[0]-1,tr.shape[1]-1;path=[]
    while j>0 and t>0:
        stay=tr[t-1,j]+em[t-1,blank];chg=tr[t-1,j-1]+em[t-1,tokens[j-1]]
        path.append((j-1,t-1))
        if chg>stay:j-=1
        t-=1
    return path[::-1]
def segments(em,tokens,chars,dur,stride=0.02):
    """-> [[t0,t1,level],...] covering 0..dur"""
    tr=trellis(em,tokens);path=backtrack(tr,em,tokens)
    first={}
    for j,t in path:first.setdefault(j,t)
    starts=[(first[j]*stride,chars[j]) for j in sorted(first)]
    segs=[]
    if not starts:return [[0.0,dur,0.0]]
    if starts[0][0]>0:segs.append([0.0,starts[0][0],0.0])
    for k,(t0,ch) in enumerate(starts):
        t1=starts[k+1][0] if k+1<len(starts) else min(dur,t0+0.12)
        lv=0.0 if ch=='|' else level(ch)
        if segs and abs(segs[-1][2]-lv)<1e-6:segs[-1][1]=t1
        else:segs.append([t0,t1,lv])
    if segs[-1][1]<dur:segs.append([segs[-1][1],dur,0.0])
    return segs
def main():
    work=Path(sys.argv[1]);st=json.loads((work/'story.json').read_text())
    import torch
    from transformers import Wav2Vec2Processor,Wav2Vec2ForCTC
    name='facebook/wav2vec2-base-960h';proc=Wav2Vec2Processor.from_pretrained(name);model=Wav2Vec2ForCTC.from_pretrained(name).eval()
    vocab=proc.tokenizer.get_vocab();blank=vocab.get('<pad>',0)
    for si,sh in enumerate(st['shots']):
        for li,ln in enumerate(sh['lines']):
            wav=work/f'line_{si:02d}_{li:02d}.wav';out=work/f'align_{si:02d}_{li:02d}.json'
            if not wav.is_file() or out.is_file():continue
            a=read16k(wav);dur=len(a)/16000
            txt=norm_text(ln['text']);chars=[c for c in txt if c in vocab];tokens=[vocab[c] for c in chars]
            if len(tokens)<2:continue
            with torch.no_grad():
                x=proc(a,sampling_rate=16000,return_tensors='pt').input_values;lg=model(x).logits[0]
                em=torch.log_softmax(lg,dim=-1).numpy()
            if em.shape[0]<len(tokens)+2:print('too short',wav.name);continue
            segs=segments(em,tokens,chars,dur);out.write_text(json.dumps({'text':ln['text'],'segs':segs}));print('aligned',wav.name,len(segs),'segments',flush=True)
    print('ALIGN DONE',flush=True)
if __name__=='__main__':main()
