"""Emotion-aware delivery for the Kokoro voice: per-sentence speed, emphasis and pauses from the meaning of each line.
plan() is pure Python (testable anywhere). render() runs inside the Kokoro runtime. Any failure falls back to the
original flat delivery, so narration is never blocked by this layer."""
import re
DRAMA=r"\b(never|nothing|died|death|lost|fear|afraid|alone|abandon\w*|refused|begged|wasted?|failed|broken|silence|tragic\w*|danger\w*|terrible|cruel|only|too late)\b"
WARM=r"\b(love|loved|friend\w*|kind\w*|hope\w*|together|gentle|gently|care\w*|grateful|joy\w*|laugh\w*|home|warm\w*|forgive\w*|smile\w*)\b"
WONDER=r"\b(imagine|discover\w*|secret|surprising\w*|remarkable|extraordinary|astonishing|suddenly|wonder\w*|amazing)\b"
STRESS=r"\b(never|only|always|nothing|everything|must|truth|why|how|love|fear|alone|free|because|really|actually|exactly|every|none|before|after)\b"
def _split(text):
 parts=re.split(r'(?<=[.!?…])\s+(?=[A-Z“"\'(])',text.strip());return [p.strip() for p in parts if p.strip()]
def _emphasis(s,limit=2):
 done=[0]
 def mark(m):
  if done[0]>=limit:return m.group(0)
  done[0]+=1;return '['+m.group(0)+'](+1)'
 return re.sub(STRESS,mark,s,flags=re.I)
def plan(text,base=0.95):
 """-> [{'text','markup','speed','pause_before','pause_after','feel'}]"""
 sents=_split(text);out=[]
 for i,s in enumerate(sents):
  first=i==0;last=i==len(sents)-1;feel='neutral';speed=base;pb=0.0;pa=0.28
  if s.rstrip().endswith('?'):feel='curious';speed=base+.02;pa=0.48;pb=0.12
  elif re.search(DRAMA,s,re.I):feel='dramatic';speed=base-.07;pb=0.32;pa=0.5
  elif re.search(WARM,s,re.I):feel='warm';speed=base-.03;pa=0.4
  elif s.rstrip().endswith('!'):feel='dramatic';speed=base-.05;pb=0.25;pa=0.45
  elif re.search(WONDER,s,re.I):feel='wonder';speed=base-.01;pb=0.15;pa=0.36
  if first:speed=min(speed,base-.02);pa=max(pa,0.4)
  if last:speed=min(speed,base-.04);pa=max(pa,0.55)
  if len(s.split())>26:pa=max(pa,0.42)
  out.append({'text':s,'markup':_emphasis(s) if feel in ('dramatic','curious','warm','wonder') or first else s,'speed':round(max(.8,min(1.05,speed)),3),'pause_before':pb,'pause_after':pa,'feel':feel})
 return out
def render(pipeline,text,voice='af_heart',base=0.95,sr=24000):
 import numpy as np
 chunks=[]
 try:
  for p in plan(text,base):
   if p['pause_before']>0 and chunks:chunks.append(np.zeros(int(sr*p['pause_before']),dtype='float32'))
   parts=[a.numpy() if hasattr(a,'numpy') else a for _,_,a in pipeline(p['markup'],voice=voice,speed=p['speed'])]
   if not parts:raise ValueError('empty')
   chunks.append(np.concatenate(parts).astype('float32'));chunks.append(np.zeros(int(sr*p['pause_after']),dtype='float32'))
  return np.concatenate(chunks)
 except Exception:
  parts=[a.numpy() if hasattr(a,'numpy') else a for _,_,a in pipeline(text,voice=voice,speed=base)]
  if not parts:raise RuntimeError('No narration generated')
  return np.concatenate(parts)
