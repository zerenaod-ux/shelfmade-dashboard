"""Script-first full-video scenes. Local, deterministic, no stock/AI API calls.
Each scene is anchored to its exact narrated words. Generic imagery is never
substituted for a failed match; unmatched text becomes a readable concept card.
"""
import re,json,math,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
VERSION='meaning-first-v1'
RULES=[
 ('cave','Shadows and understanding',['shadow','cave','prisoner','illusion','reality']),
 ('control','What you can influence',['control','reaction','respond','anger','emotion','judgment']),
 ('nature','Life in nature',['nature','woods','forest','pond','lake','simplicity','simplify']),
 ('time','A finite resource',['time','hour','minute','day','mortality','death','impermanence']),
 ('learning','Understanding develops',['learn','knowledge','education','teacher','question','reason','wisdom']),
 ('community','People and responsibility',['community','people','society','friend','duty','justice','mercy','kindness']),
 ('growth','Repeated action builds change',['habit','practice','effort','discipline','work','character','thought','mind']),
 ('choice','Different paths, different outcomes',['choose','choice','decision','path','purpose','virtue','desire']),
]
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
def font(size):
 try:return ImageFont.truetype(FONT,size)
 except OSError:return ImageFont.load_default(size=size)
def chunks(text,limit=30):
 # Break at sentence/clause boundaries first. Keep every narrated word in order.
 groups=[];current=[]
 for sentence in re.split(r'(?<=[.!?;:])\s+',text.strip()):
  words=sentence.split()
  while words:
   take=min(limit-len(current),len(words));current+=words[:take];words=words[take:]
   if len(current)>=limit:groups.append(' '.join(current));current=[]
  if len(current)>=5:groups.append(' '.join(current));current=[]
 if current:groups.append(' '.join(current))
 return groups

def select(text,chapter='',previous=None):
 words=set(re.findall(r'[a-z]+',text.lower()));words.update({'learning':'learn','learned':'learn','shadows':'shadow','choices':'choice','thoughts':'thought','habits':'habit','reactions':'reaction','prisoners':'prisoner','events':'event','decisions':'decision'}.get(w,w) for w in list(words));context=set(re.findall(r'[a-z]+',chapter.lower()))
 scored=[]
 for kind,label,terms in RULES:
  hits=[t for t in terms if t in words]
  # A chapter label alone must not override a sentence about a different idea.
  score=len(hits)*4+sum(t in context for t in terms)*.25 if hits else 0
  scored.append((score,kind,label,hits))
 best=max(scored,key=lambda x:x[0])
 if not best[0]:return {'kind':'concept','label':chapter or 'Consider this idea','keywords':[],'reason':'No reliable concrete match; show the idea itself, without invented stock imagery.'}
 return {'kind':best[1],'label':best[2],'keywords':best[3],'reason':'Narration mentions '+', '.join(best[3])+'.'}

def plan(sections):
 if not isinstance(sections,list) or not sections:raise ValueError('Provide narrated sections.')
 scenes=[]
 for chapter,section in enumerate(sections):
  text=section.get('narration','').strip();title=section.get('title','').strip()
  if not text:raise ValueError('Every chapter needs narration; no chapter is silently skipped.')
  for line in chunks(text):
   choice=select(line,title)
   scenes.append({'index':len(scenes),'chapter':chapter,'chapter_title':title,'narration':line,**choice,'layout':['wide','detail','contrast'][len(scenes)%3],'duration':None,'start':None,'end':None,'review_required':choice['kind']=='concept' or len(choice['keywords'])<2})
 return {'version':VERSION,'timing':'Measured narration per scene; no estimated timings are published.','scenes':scenes,'review_required':True}

def wrap(d,text,f,width):
 lines=[];line=''
 for word in text.split():
  test=(line+' '+word).strip()
  if d.textlength(test,font=f)>width and line:lines.append(line);line=word
  else:line=test
 if line:lines.append(line)
 return lines

def frame(scene,book,step=0,size=(1280,720)):
 w,h=size;im=Image.new('RGB',size,(12,29,29));d=ImageDraw.Draw(im)
 gold=('#8cb4f0' if __import__('os').environ.get('BRAND')=='mindlore' else '#e7bd68');cream='#f4f0df';muted='#a6bab0';green='#466f60';ink='#132e2b'
 # Framing alternates, but the chosen meaning stays tied to the spoken text.
 d.rounded_rectangle((610,110,1220,580),28,fill='#1b3b35')
 cx,cy=910,340;kind=scene['kind'];phase=step/2
 if kind=='cave':
  d.polygon([(635,550),(710,195),(875,140),(1160,180),(1195,550)],fill='#091a1c')
  d.polygon([(1120,200),(1120,510),(790+int(phase*80),410)],fill='#66603b')
  for x in (745,835,925):
   d.ellipse((x,385,x+24,409),fill=cream);d.line((x+12,410,x+12,470),fill=cream,width=10)
  d.ellipse((1080,260,1135,315),fill=gold)
 elif kind=='nature':
  d.ellipse((1040,170,1120,250),fill=gold)
  d.polygon([(640,380),(770,225),(925,390),(1080,280),(1200,400)],fill=green)
  for y in range(420,550,22):d.line((660,y,1180-int(phase*20),y),fill='#517c72',width=3)
  for x in (700,790,1140):d.polygon([(x,280),(x-45,420),(x+45,420)],fill='#0b2523')
 elif kind=='control':
  d.ellipse((765,185,1085,505),outline=green,width=3);d.ellipse((825,245,1025,445),outline=gold,width=5)
  d.text((870,310),'YOUR',font=font(26),fill=cream);d.text((850,347),'RESPONSE',font=font(25),fill=gold)
  d.text((780,525),'Events → pause → response',font=font(24),fill=muted)
 elif kind=='time':
  d.ellipse((790,200,1090,500),outline=gold,width=6)
  for a in range(12):
   r=a*math.pi/6;d.line((940+125*math.sin(r),350-125*math.cos(r),940+138*math.sin(r),350-138*math.cos(r)),fill=cream,width=4)
  d.line((940,350,940,245),fill=cream,width=7);d.line((940,350,1020,390+phase*12),fill=gold,width=6)
 elif kind=='learning':
  for j in range(4):
   x=695+j*120;y=475-j*65;d.rounded_rectangle((x,y,x+100,550),10,fill=gold if j<=step+1 else green)
  d.text((695,195),'Question → examine → understand',font=font(24),fill=cream)
 elif kind=='community':
  points=[(910,240),(780,395),(1050,395),(910,490)]
  for x,y in points:
   for a,b in points:d.line((x,y,a,b),fill=green,width=3)
  for j,(x,y) in enumerate(points):d.ellipse((x-25,y-25,x+25,y+25),fill=gold if j<=step else cream)
 elif kind=='choice':
  d.line([(925,540),(925,390),(770,230)],fill=cream,width=13);d.line([(925,390),(1090,230)],fill=gold,width=13)
  d.ellipse((900,480,950,530),fill=gold);d.text((760,175),'Which path?',font=font(36),fill=cream)
 elif kind=='growth':
  for j in range(6):
   x=680+j*80;y=490-j*47;d.rounded_rectangle((x,y,x+55,550),8,fill=gold if j<=step+2 else green)
  d.text((700,170),'Small actions, repeated',font=font(30),fill=cream)
 else:
  words=scene['narration'].split();f=font(29);y=220
  for line in wrap(d,' '.join(words[:22]),f,490):d.text((670,y),line,font=f,fill=cream);y+=44
  d.line((670,y+30,1000,y+30),fill=gold,width=4)
 d.text((60,38),('MINDLORE  /  ' if __import__('os').environ.get('BRAND')=='mindlore' else 'SHELFMADE  /  ')+book.upper()[:60],font=font(21),fill=gold)
 d.text((60,150),f"{scene['chapter']+1:02d}  /  {scene['chapter_title'][:32]}",font=font(23),fill=muted)
 y=230
 for line in wrap(d,scene['label'],font(46),480):d.text((60,y),line,font=font(46),fill=cream);y+=61
 # One short cue, not a wall of subtitles covering the visual explanation.
 cue=' · '.join(scene['keywords'][:3]).upper() or 'REFLECT • QUESTION • APPLY'
 d.text((60,min(y+35,530)),cue,font=font(21),fill=gold)
 d.line((60,626,1220,626),fill=green,width=2)
 f=font(22);excerpt=scene['narration'];lines=wrap(d,excerpt,f,1150)
 for j,line in enumerate(lines[:2]):d.text((60,646+j*28),line,font=f,fill=cream)
 return im

def render(script,folder,narrate=True,demo_seconds=None):
 """Render to a NEW folder. With narration, all scene timing comes from audio.
 Demo mode is explicitly silent and cannot be registered as an approved draft.
 """
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 if (folder/'final.mp4').exists():raise ValueError('Choose a new folder; an existing video is never overwritten.')
 storyboard=plan(script['sections']);start=0;clips=[]
 import local_voice
 for scene in storyboard['scenes']:
  i=scene['index']
  if narrate:audio,duration=local_voice.segment(scene['narration'],i,folder)
  else:audio=None;duration=demo_seconds or 5
  if not 0<duration<120:raise ValueError('Scene timing invalid; split the narration into shorter ideas.')
  scene['narration_duration']=round(duration,3)
  # Multiple progressive diagrams within a scene, never looping unrelated footage.
  stills=[]
  for k in range(3):
   image=folder/f'scene_{i:03d}_{k}.png';frame(scene,script['title'],k).save(image);stills.append(image)
  listing=folder/f'scene_{i:03d}.txt'
  listing.write_text(''.join(f"file '{p.name}'\nduration {duration/3:.6f}\n" for p in stills)+f"file '{stills[-1].name}'\n")
  clip=folder/f'scene_{i:03d}.mp4'
  cmd=['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing)]
  cmd+=['-i',audio] if audio else ['-f','lavfi','-i','anullsrc=r=24000:cl=mono']
  cmd+=['-t',str(duration),'-vf','fps=30,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','22','-c:a','aac','-ar','24000','-ac','1','-movflags','+faststart',str(clip)]
  subprocess.run(cmd,check=True,timeout=180);clips.append(clip)
  probe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(clip)],check=True,capture_output=True,text=True,timeout=20)
  actual=float(json.loads(probe.stdout)['format']['duration']);scene.update(start=round(start,3),duration=round(actual,3),end=round(start+actual,3));start+=actual
 listing=folder/'concat.txt';listing.write_text(''.join(f"file '{p.name}'\n" for p in clips))
 final=folder/'final.mp4';subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(final)],check=True,timeout=180)
 storyboard.update(duration=round(start,3),silent_demo=not narrate)
 (folder/'storyboard.json').write_text(json.dumps(storyboard,indent=2))
 (folder/'script.json').write_text(json.dumps(script,indent=2))
 frame(storyboard['scenes'][0],script['title']).save(folder/'THUMBNAIL.png')
 return final
