"""Local cinematic captions: model-timed words, short phrases, stable safe placement.
Transparent rendered layer works without optional ffmpeg/libass font filters.
"""
from pathlib import Path
import json,subprocess,math
from functools import lru_cache
from PIL import Image,ImageDraw,ImageFont
PRESET={'font':'Arial Bold','max_words':4,'position':'lower safe area','active_color':'#f3cd78','motion':'small eased phrase entrance; stable word positions','fps':30}
FONT='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
@lru_cache(maxsize=32)
def subtitle_font(size):return ImageFont.truetype(FONT,size)

def phrases(words):
 normalized=[]
 for word in words:
  if normalized and not any(ch.isalnum() for ch in word['text']):
   normalized[-1]['text']+=word['text'];normalized[-1]['end']=max(normalized[-1]['end'],word['end'])
  else:normalized.append(dict(word))
 words=normalized
 groups=[];group=[]
 for word in words:
  if word['end']<=word['start']:continue
  if group and (len(group)>=4 or word['start']-group[-1]['end']>.4):groups.append(group);group=[]
  group.append(word)
  if word['text'].endswith(('.','?','!',';')):groups.append(group);group=[]
 if group:groups.append(group)
 return groups

def frame(group,t,width=1280,height=180):
 im=Image.new('RGBA',(width,height));d=ImageDraw.Draw(im)
 start=group[0]['start'];end=group[-1]['end']+.12
 opacity=min(1,max(0,(t-start)/.12),max(0,(end-t)/.10));opacity=opacity*opacity*(3-2*opacity)
 for size in range(44,27,-1):
  f=subtitle_font(size);space=d.textlength(' ',font=f);lengths=[d.textlength(w['text'],font=f) for w in group];total=sum(lengths)+space*(len(group)-1)
  if total<width-160:break
 x=(width-total)/2;y=65+8*(1-opacity)
 d.rounded_rectangle((x-22,y-13,x+total+22,y+size+18),radius=17,fill=(7,16,16,int(140*opacity)))
 for word,length in zip(group,lengths):
  active=word['start']<=t<word['end'];color=(243,205,120) if active else (250,249,240)
  d.text((x,y),word['text'],font=f,fill=(*color,int(255*opacity)),stroke_width=1,stroke_fill=(0,0,0,int(160*opacity)))
  if active:
   progress=min(1,max(0,(t-word['start'])/max(.05,word['end']-word['start'])))
   d.rounded_rectangle((x,y+size+10,x+max(2,length*progress),y+size+13),radius=2,fill=(243,205,120,int(215*opacity)))
  x+=length+space
 return im

def srt_stamp(seconds):
 ms=round(seconds*1000);return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'

def render(video,timing,output,folder,intro=None):
 video,output,folder=Path(video),Path(output),Path(folder);folder.mkdir(parents=True,exist_ok=True)
 if output.exists():raise ValueError('Choose a new captioned output; source video is preserved.')
 data=json.loads(Path(timing).read_text());words=data['words'];groups=phrases(words)
 probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=width,height,codec_type','-of','json',str(video)],check=True,capture_output=True,text=True).stdout)
 duration=float(probe['format']['duration']);stream=next(s for s in probe['streams'] if s['codec_type']=='video');width=stream['width'];height=stream['height']
 if width!=1280 or height!=720:raise ValueError('Current cinematic caption preset expects a 1280 × 720 preview.')
 if not words or any(w['start']<0 or w['end']>duration+.1 for w in words):raise ValueError('Caption timing does not fit the video.')
 overlay=folder/'animated-captions.mov'
 cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgba','-video_size','1280x180','-framerate','30','-i','pipe:0','-an','-c:v','qtrle',str(overlay)]
 process=subprocess.Popen(cmd,stdin=subprocess.PIPE);index=0
 try:
  blank=Image.new('RGBA',(1280,180)).tobytes()
  for n in range(math.ceil(duration*30)):
   t=n/30
   while index<len(groups) and t>groups[index][-1]['end']+.12:index+=1
   group=groups[index] if index<len(groups) else None
   pixels=frame(group,t).tobytes() if group and group[0]['start']<=t<=group[-1]['end']+.12 else blank
   process.stdin.write(pixels)
 finally:process.stdin.close()
 if process.wait()!=0:raise RuntimeError('Subtitle layer rendering failed.')
 cmd=['ffmpeg','-v','error','-y','-filter_complex_threads','1','-i',str(video),'-i',str(overlay)]
 filters='[0:v][1:v]overlay=0:510:format=auto[captioned]'
 if intro:
  cmd+=['-i',str(intro)];filters+=";[captioned][2:v]overlay=0:0:enable='lt(t,4)':format=auto,format=yuv420p[v]"
 else:filters+=';[captioned]format=yuv420p[v]'
 cmd+=['-filter_complex',filters,'-map','[v]','-map','0:a','-c:v','libx264','-preset','fast','-crf','19','-threads','2','-c:a','copy','-movflags','+faststart',str(output)]
 subprocess.run(cmd,check=True,timeout=max(240,int(duration*3)))
 (folder/'subtitles.srt').write_text('\n\n'.join(f"{i+1}\n{srt_stamp(g[0]['start'])} --> {srt_stamp(g[-1]['end']+.1)}\n"+' '.join(w['text'] for w in g) for i,g in enumerate(groups))+'\n')
 (folder/'subtitle-style.json').write_text(json.dumps({**PRESET,'source_timing':data.get('method'),'video':str(output.name)},indent=2))
 return output
