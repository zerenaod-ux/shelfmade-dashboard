"""Expressive narration with Qwen3-TTS (free, local, MLX). Runs in the tts-lab venv, one process per batch.
stdin: {"jobs":[{"text":..,"wav":path,"timing":path|null}]}  ->  writes 24 kHz mono wav per job
and, when "timing" is set, {"tokens":[{text,start,end}],"duration":s} with syllable-weighted word times
(an estimate inside each sentence, anchored to the real sentence audio)."""
import json,re,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import voice_director
MODEL="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16";SPEAKER='Vivian';SR=24000
INSTRUCT={
 'curious':"Speak with bright, engaging curiosity and rising intonation, like a storyteller drawing the listener in.",
 'dramatic':"Speak with intensity and emotional weight, slower, with feeling and gravity, as if sharing something that truly matters.",
 'warm':"Speak warmly and gently, like a caring friend who loves the subject, with a smile in the voice.",
 'wonder':"Speak with awe and wonder, expressive and alive.",
 'neutral':"Speak naturally and passionately, like a storyteller who loves this subject, with lively expressive intonation."}
def weight(w):return max(1,len(re.findall(r'[aeiouy]+',w.lower())))+(0.6 if re.search(r'[,;:]$',w) else 0)+(0.9 if re.search(r'[.!?…]$',w) else 0)
def synth(model,text):
 chunks=[];tokens=[];t=0.0
 for p in voice_director.plan(text):
  rs=list(model.generate_custom_voice(text=p['text'],speaker=SPEAKER,language='English',instruct=INSTRUCT[p['feel']]))
  parts=[]
  for r in rs:
   a=np.array(getattr(r,'audio',r),dtype='float32').reshape(-1);sr=int(getattr(r,'sample_rate',SR) or SR)
   if sr!=SR:a=np.interp(np.linspace(0,len(a)-1,int(len(a)*SR/sr)),np.arange(len(a)),a).astype('float32')
   parts.append(a)
  if not parts:raise RuntimeError('Qwen returned no audio for: '+p['text'][:60])
  a=np.concatenate(parts);d=len(a)/SR
  # trim silence at the sentence edges so word times stay honest
  words=p['text'].split();ws=[weight(w) for w in words];total=sum(ws);cur=t
  for w,wt in zip(words,ws):
   step=d*wt/total;tokens.append({'text':w,'start':round(cur,4),'end':round(cur+step,4)});cur+=step
  chunks.append(a);t+=d
  gap=np.zeros(int(SR*p['pause_after']*.7),dtype='float32');chunks.append(gap);t+=len(gap)/SR
 audio=np.concatenate(chunks);return audio,tokens,len(audio)/SR
def main():
 job=json.loads(sys.stdin.read())
 from mlx_audio.tts.utils import load_model
 import soundfile as sf
 model=load_model(MODEL)
 for j in job['jobs']:
  audio,tokens,dur=synth(model,j['text'])
  peak=float(np.max(np.abs(audio)))or 1.0
  if peak>0.98:audio=audio*(0.98/peak)
  sf.write(j['wav'],audio,SR,subtype='PCM_16')
  if j.get('timing'):Path(j['timing']).write_text(json.dumps({'tokens':tokens,'duration':dur}))
  print('made',j['wav'],round(dur,1),flush=True)
if __name__=='__main__':main()
