"""One local Kokoro process per full video; exact narration token timings."""
import os,json,sys
from pathlib import Path
import local_voice
import full_checkpoint as checkpoint
os.environ['HF_HOME']=str(local_voice.WORK/'kokoro-models');os.environ['XDG_CACHE_HOME']=str(local_voice.WORK/'kokoro-cache');os.environ['HF_HUB_OFFLINE']='1'
from kokoro import KPipeline
import voice_frontend
voice_frontend.configure()
import numpy as np,soundfile as sf

def generate_qwen(script,folder):
 """Same outputs as the Kokoro path (chapter wavs, per-chapter timing, word-timing.json); words are syllable-weighted estimates anchored to the real sentence audio."""
 identity=checkpoint.digest({'script':script,'voice':('edge-jenny-v1' if local_voice.engine()=='edge' else 'qwen3-tts-vivian-v1'),'voice_source':checkpoint.file_hash(Path(__file__).with_name('qwen_voice.py')),'director':checkpoint.file_hash(Path(__file__).with_name('voice_director.py'))})
 pending=[]
 for i,section in enumerate(script['sections']):
  if not checkpoint.valid(folder.parent,'narration-'+str(i),identity):pending.append(i)
 if pending:
  (local_voice.edge_run if local_voice.engine()=='edge' else local_voice.qwen_run)([{'text':script['sections'][i]['narration'],'wav':str(folder/f'chapter_{i:02d}.wav'),'timing':str(folder/f'chapter_{i:02d}-timing.json')} for i in pending])
  for i in pending:
   file=folder/f'chapter_{i:02d}.wav';timing=folder/f'chapter_{i:02d}-timing.json'
   audio,rate=sf.read(file,dtype='float32');audio=np.concatenate([audio,np.zeros(24000,dtype=np.float32)]);sf.write(file,audio,24000,subtype='PCM_16')
   saved=json.loads(timing.read_text());saved['duration']=len(audio)/24000;timing.write_text(json.dumps(saved))
   checkpoint.seal(folder.parent,'narration-'+str(i),identity,[file,timing])
 words=[];chapters=[];offset=0;files=[]
 for i,section in enumerate(script['sections']):
  file=folder/f'chapter_{i:02d}.wav';saved=json.loads((folder/f'chapter_{i:02d}-timing.json').read_text());duration=saved['duration'];local=duration-1
  files.append(file);chapters.append({'index':i,'title':section['title'],'narration':section['narration'],'start':offset,'duration':duration})
  for t in saved['tokens']:words.append({'text':t['text'],'start':round(offset+t['start'],4),'end':round(offset+min(local,t['end']),4)})
  offset+=duration;print('Narration chapter',i+1,round(offset,1),flush=True)
 (folder/'word-timing.json').write_text(json.dumps({'method':('Edge neural narration; exact word boundaries' if local_voice.engine()=='edge' else 'Expressive Qwen3-TTS narration; word times estimated by syllable weight inside each real sentence'),'words':words},indent=2));(folder/'chapters.json').write_text(json.dumps(chapters,indent=2));(folder/'audio.txt').write_text(''.join(f"file '{p.name}'\n" for p in files))

def generate(script,folder):
 if local_voice.engine() in ('qwen','edge'):return generate_qwen(script,folder)
 pipeline=None;words=[];chapters=[];offset=0;files=[]
 identity=checkpoint.digest({'script':script,'voice':'af_heart','speed':.95,'voice_source':checkpoint.file_hash(Path(__file__)),'frontend_source':checkpoint.file_hash(Path(__file__).with_name('voice_frontend.py'))})
 for i,section in enumerate(script['sections']):
  file=folder/f'chapter_{i:02d}.wav';timing=folder/f'chapter_{i:02d}-timing.json'
  if checkpoint.valid(folder.parent,'narration-'+str(i),identity):
   saved=json.loads(timing.read_text());tokens=saved['tokens'];duration=saved['duration'];local=duration-1
   print('Resumed narration chapter',i+1,flush=True)
  else:
   if pipeline is None:pipeline=KPipeline(lang_code='a',repo_id='hexgrad/Kokoro-82M',device='cpu')
   voice_frontend.check(pipeline,section['narration'])
   parts=[];local=0;tokens=[]
   for r in pipeline(section['narration'],voice='af_heart',speed=.95):
    for t in r.tokens or []:
     if t.start_ts is not None and t.end_ts is not None:tokens.append({'text':t.text,'start':local+t.start_ts,'end':local+t.end_ts})
     elif tokens and t.text.strip():tokens[-1]['text']+=t.text
    a=r.audio.numpy() if hasattr(r.audio,'numpy') else r.audio;parts.append(a);local+=len(a)/24000
   if not parts:raise ValueError('Narration returned no audio. No fallback voice is permitted.')
   audio=np.concatenate([*parts,np.zeros(24000,dtype=np.float32)]);sf.write(file,audio,24000,subtype='PCM_16');duration=len(audio)/24000
   timing.write_text(json.dumps({'tokens':tokens,'duration':duration}))
   checkpoint.seal(folder.parent,'narration-'+str(i),identity,[file,timing])
  files.append(file)
  chapters.append({'index':i,'title':section['title'],'narration':section['narration'],'start':offset,'duration':duration})
  for t in tokens:words.append({'text':t['text'],'start':round(offset+t['start'],4),'end':round(offset+min(local,t['end']),4)})
  offset+=duration;print('Narration chapter',i+1,round(offset,1),flush=True)
 (folder/'word-timing.json').write_text(json.dumps({'method':'Kokoro timings from the exact generated narration','words':words},indent=2));(folder/'chapters.json').write_text(json.dumps(chapters,indent=2));(folder/'audio.txt').write_text(''.join(f"file '{p.name}'\n" for p in files))
if __name__=='__main__':generate(json.loads(Path(sys.argv[1]).read_text()),Path(sys.argv[2]))
