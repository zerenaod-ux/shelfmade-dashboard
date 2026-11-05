"""Mood-matched background music for finished drafts (original synthesized tracks in music/, see music_synth.py).
remix(folder) replaces final.mp4 with a version that has the music bed ducked under the narration, keeps the
unmixed original as final.nomusic.mp4, and refreshes validation.json's output hash. Only for UNREVIEWED drafts."""
import hashlib,json,re,subprocess,shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent
MOODS={
 'dramatic':r'\b(war|death|died|fear|danger|revolution|crowd|mob|panic|anger|rage|violence|tragedy|crisis|lost|abandon\w*)\b',
 'mysterious':r'\b(dream\w*|sleep|unconscious|hidden|secret|mystery|strange|shadow|unknown|hypnosis|suggestion|illusion)\b',
 'warm':r'\b(love|friend\w*|kindness|hope|joy|laugh\w*|happy|happiness|care|together|home|grateful|gratitude)\b',
 'curious':r'\b(why|how|what|if|question\w*|wonder|puzzle|discover\w*|think\w*|mind|attention|habit\w*|learn\w*)\b',
 'reflective':r'\b(memory|remember\w*|time|history|past|life|meaning|reflect\w*|habit|essay|age|old)\b',
}
def mood_for(text):
 text=(text or '').lower();best=('calm',0)
 for m,p in MOODS.items():
  n=len(re.findall(p,text))
  if n>best[1]:best=(m,n)
 return best[0]
def track(mood):
 lib=json.loads((BASE/'music-library.json').read_text());p=BASE/lib.get(mood,lib['calm'])
 if not p.is_file():raise ValueError('Music track missing: '+str(p))
 return p
def _sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def remix(folder,text=None,mood=None,gain=1.0,intro_boost=True):
 folder=Path(folder);video=folder/'final.mp4';orig=folder/'final.nomusic.mp4';val=folder/'validation.json'
 if not video.is_file() or not val.is_file():raise ValueError('Not a finished draft folder.')
 for flag in ('approved','published'):
  st=folder/'rebuild-status.json'
  if st.is_file() and json.loads(st.read_text()).get(flag) is True:raise ValueError('Reviewed/published drafts are never changed.')
 if text is None:
  for n in ('editorial-script.json','script.json'):
   if (folder/n).is_file():text=(folder/n).read_text();break
 mood=mood or mood_for(text);music=track(mood)
 base=orig if orig.exists() else video
 narr=folder/'.render'/'narration.wav';src=str(narr if narr.is_file() else base)
 dur=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(base)],capture_output=True,text=True,check=True).stdout)
 fade=1.8
 flt=(f'[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,loudnorm=I=-17:TP=-2:LRA=9,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[vo][sc];'
      f'[2:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={gain},afade=t=in:st=0:d=1.2,afade=t=out:st={dur-fade:.2f}:d={fade}[mu];'
      '[mu][sc]sidechaincompress=threshold=0.03:ratio=3:attack=40:release=500[du];'
      '[vo][du]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[a]')
 tmp=folder/'final.music.tmp.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(base),'-i',src,'-stream_loop','-1','-i',str(music),'-filter_complex',flt,'-map','0:v','-map','[a]','-t',f'{dur:.3f}','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(tmp)],check=True)
 if not orig.exists():shutil.copy2(video,orig)
 shutil.copyfile(tmp,video)
 v=json.loads(val.read_text());v['output_sha256']=_sha(video);v['music']={'mood':mood,'track':music.name,'original':'final.nomusic.mp4'}
 val.write_text(json.dumps(v,indent=2))
 try:tmp.unlink()
 except OSError:tmp.rename(folder/'final.music.tmp.done')
 return mood
def undo(folder):
 folder=Path(folder);orig=folder/'final.nomusic.mp4'
 if not orig.is_file():raise ValueError('No original to restore.')
 shutil.copyfile(orig,folder/'final.mp4');val=folder/'validation.json';v=json.loads(val.read_text())
 v['output_sha256']=_sha(folder/'final.mp4');v.pop('music',None);val.write_text(json.dumps(v,indent=2));return True

def auto(folder):
 """Called after a draft is rendered. Never blocks a draft: any problem leaves the original video untouched."""
 import os
 if os.environ.get('CE_DISABLE_MUSIC'):return None
 try:
  cfg=json.loads((BASE/'music-settings.json').read_text())
  if cfg.get('enabled') is not True:return None
  folder=Path(folder);text=None
  for n in ('editorial-script.json','script.json','POST_THIS.txt','source.txt'):
   if (folder/n).is_file():text=(folder/n).read_text();break
  return remix(folder,text=text,gain=float(cfg.get("gain",1.0)))
 except Exception:
  return None
