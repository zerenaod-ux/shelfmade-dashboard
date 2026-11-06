"""Image-led local cover graphics; footage stays visible beneath opening captions."""
from pathlib import Path
import json,re,subprocess
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent
FONT='/System/Library/Fonts/Supplemental/Arial Bold.ttf'

def headline(script):
 text=' '.join(str(script.get('thumbnail_headline') or script.get('hook','')).split()).strip()
 if 2<=len(text.split())<=6 and not text.endswith((':',',',' in',' your',' the',' of')):return text.upper()
 context=(text+' '+script.get('title','')).lower()
 for keys,line in [(('control','power','enchiridion'),'WHO CONTROLS YOUR DAY?'),(('time','busy','walden'),'BUSY ISN’T LIVING'),(('truth','reality','republic','knowledge','belief'),'IS THIS REALLY TRUE?'),(('habit','thought'),'WHAT SHAPES YOUR LIFE?'),(('effort','discipline','work','perseverance'),'PUT EFFORT INTO PRACTICE'),(('fear','courage'),'WHAT HOLDS YOU BACK?'),(('wealth','diamond','opportunity'),'HIDDEN IN PLAIN SIGHT'),(('nature','woods','forest','simple'),'NOTICE WHAT YOU MISS'),(('virtue','kindness','character'),'CHOICES SHAPE YOUR CHARACTER'),(('life','living'),'HOW WILL YOU LIVE?')]:
  if any(k in context for k in keys):return line
 return 'TEST THIS IDEA'

def asset(script):
 import cinematic_pipeline
 assets=json.loads((BASE/'cinematic-assets.json').read_text())
 candidates,uncertain=cinematic_pipeline.choose_assets(script.get('hook',''),script.get('title',''),assets)
 # Relevance is required before preferring a concrete, human-scale scene.
 preferred=[a for a in candidates if any(k in a['description'].lower() for k in ('person','hands','people','passage','waterfall'))]
 return (preferred or candidates)[0]

def footage_frame(source,size,offset=2):
 p=subprocess.run(['ffmpeg','-v','error','-ss',str(offset),'-i',str(source),'-frames:v','1','-vf',f'scale={size[0]}:{size[1]}:force_original_aspect_ratio=increase,crop={size[0]}:{size[1]}','-f','image2pipe','-vcodec','png','-'],capture_output=True,check=True,timeout=30)
 import io
 return Image.open(io.BytesIO(p.stdout)).convert('RGBA')

def graphic(script,size=(1280,720),background=None):
 w,h=size;im=background.copy().resize(size).convert('RGBA') if background else Image.new('RGBA',size)
 layer=Image.new('RGBA',size);d=ImageDraw.Draw(layer);portrait=h>w
 # Small headline block with most of the scene unobscured. No title-page furniture.
 x=int(w*.065);y=int(h*((.61 if portrait else .56) if background else .13));maxwidth=int(w*.84)
 text=headline(script)
 for sizefont in range(int(w*.09),int(w*.045),-2):
  f=ImageFont.truetype(FONT,sizefont);lines=[];line=''
  for word in text.split():
   test=(line+' '+word).strip()
   if d.textlength(test,font=f)>maxwidth and line:lines.append(line);line=word
   else:line=test
  lines.append(line)
  if len(lines)<=2:break
 for yy in range(max(0,y-80),h):
  alpha=int(195*min(1,max(0,(yy-(y-80))/220))) if background else 0
  if alpha:d.line((0,yy,w,yy),fill=(4,12,15,alpha))
 for n,line in enumerate(lines):
  d.text((x,y+n*(sizefont+12)),line,font=f,fill='#f7d36d' if n==len(lines)-1 else '#ffffff',stroke_width=3,stroke_fill=(0,0,0,210))
 if background:
  f=ImageFont.truetype(FONT,int(w*.021));d.text((x,int(h*.93)),'SHELFMADE',font=f,fill='#ffffff')
 return Image.alpha_composite(im,layer)

def _rule_headline(hook):
 """A compact editorial question drawn from the spoken hook, never the book name alone."""
 words=set(re.findall('[a-z]+',hook.lower()))
 rules=[(('death','mortality'),'WHAT DOES DEATH TEACH US?'),(('shadow','shadows','reality'),'LOOK BEYOND THE SHADOWS'),(('indirect','direct','method','methods'),'CHOOSE YOUR METHOD'),(('enemy','battle','victory','fight'),'KNOW YOUR ENEMY'),(('concentration','attention','mind'),'WHERE IS YOUR ATTENTION?'),(('disappointment','determined','perseverance'),'LEARN THROUGH THE SETBACK'),(('knowledge','learn','learned','understanding','reason','wise','wisdom'),'QUESTION WHAT YOU KNOW'),(('simple','simpler','simplicity'),'IS SIMPLER REALLY BETTER?'),(('time','hour','hours','day'),'WHERE DOES YOUR TIME GO?'),(('anger','control','response','calm'),'CHOOSE YOUR RESPONSE'),(('habit','thought','character','practice'),'WHAT SHAPES YOUR HABITS?'),(('life','living'),'HOW WILL YOU LIVE?'),(('work','effort'),'PUT EFFORT INTO PRACTICE'),(('nature','forest','woods'),'NOTICE WHAT YOU MISS')]
 for keys,line in rules:
  if words.intersection(keys):return line
 return headline({'hook':hook})


def short_headline(hook):
 """Always returns a 2-6 word cover line that shares real words with the spoken hook (permanent fix for 'Cover headline does not connect')."""
 line=_rule_headline(hook)
 try:
  import creative_quality as cq
  if 2<=len(line.split())<=6 and cq.related(line,hook):return line
  words=[w for w in re.findall(r"[A-Za-z']+",str(hook)) if len(w)>2 and w.lower() not in cq.STOP]
 except Exception:
  return line
 if len(words)<2:words=str(hook).split()
 return ' '.join(words[:4]).upper()
