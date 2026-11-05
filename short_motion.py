"""Fresh matched Shorts scenes with smooth dissolves and a cover from the real opener."""
import json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent

def prerequisites(folder,music):
 import render_readiness as r,local_voice,opening_design,cinematic_pipeline as cinema
 return r.record(folder,'short_dependencies',lambda:r.prerequisites({'music_path':str(music),'music_optional':False},local_voice.available(),opening_design.FONT,cinema.probe))

def music_asset():
 """Use the same owner-configured bed as full videos; fail clearly if it is absent."""
 import cinematic_pipeline as cinema,os
 key=os.environ.get('SHELFMADE_MUSIC_KEY','')
 tracks=sorted(p for p in (BASE/'music').glob('*.mp3') if p.is_file() and not p.is_symlink())
 if key and tracks:return tracks[int(hashlib.sha256(key.encode()).hexdigest(),16)%len(tracks)]  # a different mood per video
 configured=Path(cinema.settings().get('music_path','')).expanduser()
 if configured.is_file():return configured
 legacy=BASE/'generator'/'assets'/'music.mp3'
 if legacy.is_file():return legacy
 return configured

def segment_signature(segments):
 return hashlib.sha256(json.dumps([[s[0],s[1],s[3]] for s in segments],ensure_ascii=False).encode()).hexdigest()

def caption_interval(duration,count):
 import render_readiness as r
 r.number(duration,'Short segment duration',True)
 if not isinstance(count,int) or isinstance(count,bool) or count<1:raise ValueError('Render readiness: Short segment words are missing.')
 return duration/count

def narration(script,segments,folder,probe):
 """Validate actual segment audio and uniform estimates; never claim word alignment."""
 import render_readiness as r
 expected=[('hook',script['hook']),*[(f'point{i}',text) for i,text in enumerate(script['points'],1)],('cta',script['cta'])]
 if len(segments)!=len(expected):raise ValueError('Render readiness: Short narration segments are missing.')
 chapters=[];words=[];cursor=0
 for i,((kind,text,path,duration),(wanted_kind,wanted_text)) in enumerate(zip(segments,expected)):
  r.number(duration,'Short segment duration',True)
  if kind!=wanted_kind or text!=wanted_text:raise ValueError('Render readiness: Short segment order or text differs from the script.')
  if abs(r.media(path,'audio',probe)-duration)>.15:raise ValueError('Render readiness: Short audio duration differs from its segment. Rebuild narration.')
  tokens=text.split();interval=caption_interval(duration,len(tokens))
  chapters.append({'index':i,'title':kind,'narration':text,'start':cursor,'duration':duration})
  words.extend({'text':word,'start':cursor+j*interval,'end':cursor+(j+1)*interval} for j,word in enumerate(tokens));cursor+=duration
 receipt=r.narration({'sections':[{'narration':c['narration']} for c in chapters]},chapters,words)
 return {**receipt,'segment_signature':segment_signature(segments),'format':'short','stage':'short_audio_checked','timing_basis':'uniform estimates within each actual voice segment; not model word alignment'}


def montage(script,segments,folder):
 import cinematic_pipeline as cinema,opening_design,footage_director,creative_quality as cq
 folder=Path(folder);sections=[];chapters=[];cursor=0
 import render_readiness as r
 for index,(kind,text,duration,query) in enumerate(segments):
  sections.append({'title':kind,'narration':text})
  chapters.append({'index':index,'title':kind,'narration':text,'start':cursor,'duration':duration,'visual_context':chapters[-1]['narration'] if kind=='cta' and chapters else text});cursor+=duration
 def checked_audio():
  try:receipt=json.loads((folder/'render-readiness.json').read_text())
  except (OSError,ValueError):raise ValueError('Render readiness: Short audio checks are missing. Rebuild narration.') from None
  if receipt.get('stage')!='short_audio_checked' or receipt.get('state')!='passed' or receipt.get('segment_signature')!=segment_signature([(kind,text,None,duration) for kind,text,duration,query in segments]):raise ValueError('Render readiness: Short audio checks differ from the scene plan. Rebuild narration.')
  return receipt
 audio_receipt=r.record(folder,'short_audio_receipt',checked_audio)
 assets=footage_director.acquire({**script,'sections':sections,'content_type':'short'},folder,needed=12,chapters=chapters)
 shots=cinema.plan_shots(chapters,assets,short_mode=True)
 report=cq.require(cq.scene_review(cq.script_review(script,script.get('source_evidence',[])),shots,chapters,assets))
 def check_sources():
  return {**audio_receipt,**r.scene_sources(chapters,shots,cinema.probe),'stage':'ready_for_encoding'}
 report['render_readiness']=r.record(folder,'short_before_encoding',check_sources);cq.save(folder,report)
 clips=[]
 for index,s in enumerate(shots):
  clip=folder/f'local-motion-{index:03d}.mp4';clips.append(clip)
  cinema.run(['ffmpeg','-v','error','-y','-ss',str(s['source_start']),'-i',s['source'],'-t',str(s['duration']),'-an','-vf','scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','21','-threads','2',str(clip)])
 output=folder/'local-motion.mp4';command=['ffmpeg','-v','error','-y','-filter_complex_threads','1']
 for clip in clips:command+=['-i',str(clip)]
 filters=[f'[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]' for i in range(len(clips))];previous='v0'
 for i in range(1,len(clips)):
  name=f'x{i}';filters.append(f'[{previous}][v{i}]xfade=transition=fade:duration=0.35:offset={shots[i]["start"]:.5f}[{name}]');previous=name
 cinema.run(command+['-filter_complex',';'.join(filters),'-map',f'[{previous}]','-t',str(cursor),'-an','-c:v','libx264','-preset','veryfast','-crf','21','-threads','2',str(output)])
 first=shots[0]
 opening_design.graphic(script,(1080,1920),opening_design.footage_frame(first['source'],(1080,1920),first['source_start'])).convert('RGB').save(folder/'cover.jpg',quality=94)
 opening_design.graphic(script,(1080,1920)).save(folder/'opening.png')
 (folder/'storyboard.json').write_text(json.dumps({'version':cq.VERSION,'duration':cursor,'scenes':shots},indent=2))
 return str(output)
