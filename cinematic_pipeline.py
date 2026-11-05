"""Default full-video production: moving footage, 5–8 minutes, exact voice captions.
No illustration/slides fallback. Every output is a new, unapproved draft.
"""
import json,math,subprocess,sys,re,os
import full_checkpoint as checkpoint
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import local_voice,cinematic_content,cinematic_subtitles,full_visuals,render_readiness,media_runtime
BASE=Path(__file__).resolve().parent
VERSION='cinematic-default-v1'
def settings():return json.loads((BASE/'cinematic-settings.json').read_text())
def run(cmd,timeout=1800):
 p=subprocess.run(cmd,env=media_runtime.environment(),capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise ValueError('Media operation failed: '+p.stderr[-700:])
def probe(path):return json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height,r_frame_rate','-of','json',str(path)],env=media_runtime.environment(),capture_output=True,text=True,check=True,timeout=30).stdout)
def validate_duration(value):
 config=dict(settings())
 if os.environ.get('BRAND')=='mindlore':config.update(full_video_min_seconds=420,full_video_max_seconds=540)
 if not config['full_video_min_seconds']<=value<=config['full_video_max_seconds']:raise ValueError(f'Narration is {value/60:.1f} minutes; edit the script for the allowed length. No padding, looping or voice-speed change was used.')
def choose_assets(text,chapter,assets):
 words=set(re.findall('[a-z]+',(text+' '+chapter).lower()))
 choice=full_visuals.select(text,chapter);words.update(choice['keywords']);words.add(choice['kind'])
 scored=[(sum(t in words for t in a['tags']),a) for a in assets]
 best=max(score for score,a in scored)
 if best:return [a for score,a in scored if score>=max(1,best-1)],False
 # Clearly flagged reflective footage for an abstract passage; never random stock.
 return [a for a in assets if 'reflect' in a['tags'] or 'reflection' in a['tags']],True

def assign_fresh_scenes(beats,assets):
 """Find a unique matching clip for every beat before editing consumes any.
 Augmenting paths reserve scarce concrete subjects without weakening relevance.
 """
 import footage_director as f
 options=[]
 for beat in beats:
  visual=beat['visual'];subject=visual.get('subject','theme')
  candidates=[a for a in assets if visual['theme'] in a.get('themes',[]) and a['duration']>beat['unit']+3 and ('visual_subject' not in a or a['visual_subject']==subject)]
  if subject!='theme':candidates=[a for a in candidates if a.get('query') in visual['queries'] or any(f.metadata_match({'url':a.get('source_url','')},q) for q in visual['queries'])]
  spoken=set(re.findall('[a-z]+',beat['narration_anchor'].lower()))
  candidates.sort(key=lambda a:(len(spoken & set(re.findall('[a-z]+',a.get('query','').lower()))),a.get('shot_intent')==beat['preferred_shot_role'],a['duration']),reverse=True)
  options.append(candidates)
 owners={};assigned={}
 def place(index,visited):
  for asset in options[index]:
   ident=asset['id']
   if ident in visited:continue
   visited.add(ident)
   if ident not in owners or place(owners[ident],visited):
    owners[ident]=index;assigned[index]=asset;return True
  return False
 for index in sorted(range(len(beats)),key=lambda i:len(options[i])):
  if not place(index,set()):raise ValueError('Fresh matching footage exhausted for '+beats[index]['chapter_title']+'. Add chapter-specific footage; no repeated or unrelated fallback was used.')
 return {(b['chapter'],b['start']):assigned[i] for i,b in enumerate(beats)}

def plan_shots(chapters,assets,words=None,short_mode=False,long_scene_seconds=8):
 cursors={};previous=[];shots=[];fresh=bool(assets) and all(a.get('provider')=='Pexels' for a in assets)
 if fresh:
  import scene_direction
  assignments=assign_fresh_scenes(scene_direction.plan(chapters,words,short_mode,long_scene_seconds),assets)
 for c in chapters:
  interval=(2.5 if short_mode else 3) if c['index']==0 else (5 if short_mode else long_scene_seconds)
  count=math.ceil(c['duration']/interval);unit=c['duration']/count
  if fresh:
   import scene_direction
   directed=scene_direction.plan([c],words,short_mode,long_scene_seconds)
  else:directed=[]
  sentences=re.split(r'(?<=[.!?])\s+',c['narration'])
  for j in range(count):
   beat=directed[j] if fresh else None
   text=beat['narration_anchor'] if beat else ' '.join(w['text'] for w in (words or []) if c['start']+j*unit<=w['start']<c['start']+(j+1)*unit)
   if not text:text=sentences[min(len(sentences)-1,int(j*len(sentences)/count))]
   if fresh:
    import footage_director
    visual=beat['visual']
    candidates=[a for a in assets if visual['theme'] in a.get('themes',[]) and a['id'] not in previous and ('visual_subject' not in a or a['visual_subject']==visual.get('subject','theme'))]
    if visual.get('subject','theme')!='theme':
     candidates=[a for a in candidates if a.get('query') in visual['queries'] or any(footage_director.metadata_match({'url':a.get('source_url','')},query) for query in visual['queries'])]
    uncertain=True
   else:candidates,uncertain=choose_assets(text,c['title'],assets)
   viable=[a for a in candidates if a['duration']>unit+3 and a['id'] not in previous[-2:]]
   if not viable:viable=[a for a in candidates if a['duration']>unit+3 and (not previous or a['id']!=previous[-1])]
   if not viable and fresh:raise ValueError('Fresh matching footage exhausted for '+c['title']+'. Add chapter-specific footage; no repeated or unrelated fallback was used.')
   if not viable:
    viable=[a for a in assets if ('reflect' in a['tags'] or 'reflection' in a['tags']) and a['duration']>unit+3 and (not previous or a['id']!=previous[-1])];uncertain=True
   if not viable:raise ValueError('Not enough matching footage variety. Add appropriate footage instead of repeating the same clip.')
   if fresh:
    spoken=set(re.findall('[a-z]+',text.lower()))-{'the','and','your','you','a','of','to','in','is','it','with','for','this','that'}
    last_query=shots[-1].get('search_query') if shots else None
    def rank(a):
     query=set(re.findall('[a-z]+',a.get('query','').lower()))
     desired=beat['preferred_shot_role']
     return (len(spoken & query)*3+(5 if a.get('query')==visual['queries'][0] else 0)+(4 if visual.get('subject','theme')!='theme' and footage_director.metadata_match({'url':a.get('source_url','')},visual['queries'][0]) else 0)+ (3 if a.get('shot_intent')==desired else 0)-(2 if a.get('query')==last_query else 0),a['duration'])
    a=assignments[(beat['chapter'],beat['start'])]
   else:a=min(viable,key=lambda a:cursors.get(a['id'],1)/a['duration'])
   offset=cursors.get(a['id'],1);hold=unit+(.35 if short_mode else .65)
   if offset+hold>a['duration']-1:offset=1
   cursors[a['id']]=offset+hold+.5;previous.append(a['id'])
   shots.append({'chapter':c['index'],'chapter_title':c['title'],'start':round(c['start']+j*unit,5),'duration':hold,'unit':unit,'source_start':offset,'source':a['path'],'asset_id':a['id'],'kind':'footage','narration_anchor':text,'reason':a['description'],'review_required':uncertain,'search_query':a.get('query'),'source_url':a.get('source_url'),'creator':a.get('creator'),'visual_theme':visual['theme'] if fresh else None,'visual_subject':visual.get('subject') if fresh else None,'visual_keywords':visual['keywords'] if fresh else [],'match_basis':'passage keywords or explicit chapter continuity; illustrative metadata match' if fresh else 'legacy catalog tags','shot_intent':a.get('shot_intent','illustrative'),'direction_version':beat['direction_version'] if beat else None,'planned_intent':beat['planned_intent'] if beat else None,'preferred_shot_role':beat['preferred_shot_role'] if beat else None,'sentence_context':beat['sentence_context'] if beat else None,'context_basis':beat['context_basis'] if beat else None,'role_matched':a.get('shot_intent')==beat['preferred_shot_role'] if beat else None})
 return shots

def art(script,source,folder,offset=1):
 import opening_design
 bg=opening_design.footage_frame(source,(1280,720),offset=offset)
 cover=opening_design.graphic(script,background=bg).convert('RGB')
 cover.save(folder/'THUMBNAIL.jpg',quality=93);cover.save(folder/'THUMBNAIL.png')
 opening_design.graphic(script).save(folder/'.render/opening.png')
 (folder/'hook-design.json').write_text(json.dumps({'version':'image-led-hook-v2','headline':opening_design.headline(script),'source':str(source),'review_required':True,'promise':'Opening footage and headline must be supported by the narration.'},indent=2))

def render(script,folder,chapters,assets):
 folder=Path(folder);work=folder/'.render';work.mkdir(parents=True,exist_ok=True);config=settings();total=sum(c['duration'] for c in chapters);validate_duration(total)
 timed_words=json.loads((work/'word-timing.json').read_text())['words'];shots=plan_shots(chapters,assets,timed_words);outputs=[]
 import creative_quality as cq
 report=cq.require(cq.scene_review(cq.script_review(script,script.get('source_evidence',[]),full=True),shots,chapters,assets))
 report['render_readiness']=render_readiness.record(folder,'before_encoding',lambda:render_readiness.footage(script,chapters,timed_words,shots,folder,probe));cq.save(folder,report)
 for c in chapters:
  group=[s for s in shots if s['chapter']==c['index']];clips=[]
  out=work/f"chapter_{c['index']:02d}.mp4"
  chapter_identity=checkpoint.digest({'chapter':c,'shots':group,'settings':config,'audio_sha256':checkpoint.file_hash(work/f"chapter_{c['index']:02d}.wav"),'renderer_sha256':checkpoint.file_hash(Path(__file__))})
  if checkpoint.valid(folder,'chapter-'+str(c['index']),chapter_identity):
   outputs.append(out);print('Resumed verified chapter',c['index']+1,flush=True);continue
  checkpoint.stage(folder,'rendering','Rendering chapter '+str(c['index']+1)+' of '+str(len(chapters))+'. Completed chapters are saved.')
  for j,s in enumerate(group):
   clip=work/f"c{c['index']:02d}-{j:02d}.mp4";clips.append(clip)
   run(['ffmpeg','-v','error','-y','-ss',str(s['source_start']),'-i',s['source'],'-t',str(s['duration']),'-an','-vf','scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps=30,eq=contrast=1.025:saturation=0.96:brightness=-0.006,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','20','-threads','2',str(clip)])
  out=work/f"chapter_{c['index']:02d}.mp4";outputs.append(out);cmd=['ffmpeg','-v','error','-y','-filter_complex_threads','1']
  for clip in clips:cmd+=['-i',str(clip)]
  cmd+=['-i',str(work/f"chapter_{c['index']:02d}.wav")];filters=[f'[{j}:v]settb=AVTB,setpts=PTS-STARTPTS[v{j}]' for j in range(len(clips))];prev='v0'
  for j in range(1,len(clips)):
   name=f'x{j}';filters.append(f'[{prev}][v{j}]xfade=transition=fade:duration=0.65:offset={group[j]["start"]-c["start"]:.5f}[{name}]');prev=name
  cmd+=['-filter_complex',';'.join(filters),'-map',f'[{prev}]','-map',f'{len(clips)}:a','-t',str(c['duration']),'-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-c:a','aac','-ar','24000','-ac','1',str(out)];run(cmd);run(['ffmpeg','-v','error','-i',str(out),'-f','null','-'],timeout=300);checkpoint.seal(folder,'chapter-'+str(c['index']),chapter_identity,[out]);print('Rendered chapter',c['index']+1,flush=True)
 (work/'video.txt').write_text(''.join(f"file '{p.name}'\n" for p in outputs));run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(work/'video.txt'),'-c','copy',str(work/'joined.mp4')]);run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(work/'audio.txt'),str(work/'narration.wav')])
 import music_lab
 music=None
 try:
  import music_director
  _b=music_director.make_bed(os.environ.get('BRAND') or 'shelfmade','full' if total>75 else 'short',json.dumps(script,default=str)[:6000],total,work/'bed.wav',words=len(timed_words),key=str(script.get('book_id',''))+'|'+str(script.get('title','')))
  if _b:music=Path(_b['path'])
 except Exception as _e:print('music director skipped:',_e,flush=True)
 if music is None:
  try:music=music_lab.track(music_lab.mood_for(json.dumps(script,default=str)))
  except Exception:music=Path(__file__).resolve().parent/'music'/'calm.mp3'
 if not music.is_file():raise ValueError('Background music file is missing: '+str(music))
 base=work/'base.mp4';run(['ffmpeg','-v','error','-y','-i',str(work/'joined.mp4'),'-i',str(work/'narration.wav'),'-stream_loop','-1','-i',str(music),'-filter_complex',f'[1:a]loudnorm=I=-17:TP=-2:LRA=9,asplit=2[v][sc];[2:a]aresample=48000,volume=0.5[m0];[m0][sc]sidechaincompress=threshold=0.03:ratio=3:attack=40:release=500[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95,afade=t=out:st={total-1.5}:d=1.5[a]','-map','0:v','-map','[a]','-t',str(total),'-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(base)])
 art(script,shots[0]['source'],folder,shots[0]['source_start'])
 final=folder/'cinematic_LONGFORM.mp4';checkpoint.stage(folder,'subtitles','Adding exact animated subtitles and the content-specific opening.');cinematic_subtitles.render(base,work/'word-timing.json',final,work,intro=work/'opening.png')
 checkpoint.stage(folder,'validating','Checking complete video decoding, duration and source receipts before review.');run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'],timeout=300);actual=float(probe(final)['format']['duration']);validate_duration(actual)
 (folder/'storyboard.json').write_text(json.dumps({'version':VERSION,'duration':actual,'scenes':shots,'review_required':True},indent=2));return final

def build(book,folder):
 folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
 if (folder/'cinematic_LONGFORM.mp4').exists():raise ValueError('Existing output preserved; use a new draft folder.')
 render_readiness.record(folder,'dependencies',lambda:render_readiness.prerequisites(settings(),local_voice.available(),cinematic_subtitles.FONT,probe))
 script=cinematic_content.build(book);script.setdefault('public_title',script['title']);script.setdefault('book_title',next((b['title'] for b in json.loads((BASE/'books.json').read_text()) if b['id']==book),script['title']))
 work=folder/'.render';work.mkdir(exist_ok=True);(folder/'script.json').write_text(json.dumps(script,indent=2))
 import creative_quality as cq
 cq.save(folder,cq.require(cq.script_review(script,script.get('source_evidence',[]),full=True)))
 voice_identity=checkpoint.digest({'script':script,'voice':'af_heart','speed':.95,'voice_source':checkpoint.file_hash(BASE/'cinematic_voice.py'),'frontend_source':checkpoint.file_hash(BASE/'voice_frontend.py')})
 source_value=os.environ.get('SHELFMADE_FULL_RESUME_FROM','')
 if source_value:
  source=Path(source_value)
  base_name=folder.name.split('-attempt-')[0]
  if source.is_symlink() or source.parent.resolve()!=folder.parent or source.name.split('-attempt-')[0]!=base_name or (source/'POST_THIS.txt').exists():raise ValueError('Recovery source is not an unfinished attempt of this job.')
  restored=checkpoint.restore(source,folder,voice_identity)
  import footage_director
  footage_director.restore_progress(source,folder,script)
  checkpoint.write(folder/'recovery-restored.json',{'source':source.name,'verified_stages':restored,'original_preserved':True})
 if not checkpoint.valid(folder,'voice',voice_identity):
  import footage_preflight
  footage_preflight.check(script,folder)
  checkpoint.stage(folder,'narration','Preparing narration and exact subtitles; footage metadata checks passed.')
  run([str(local_voice.RUNTIME),str(BASE/'cinematic_voice.py'),str(folder/'script.json'),str(work)],timeout=1800)
 else:checkpoint.stage(folder,'narration_restored','Verified narration and subtitle timing restored; searching only for missing footage.')
 chapters=json.loads((work/'chapters.json').read_text());validate_duration(sum(c['duration'] for c in chapters))
 words=json.loads((work/'word-timing.json').read_text())['words']
 render_readiness.record(folder,'before_footage_search',lambda:render_readiness.narration(script,chapters,words))
 for c in chapters:
  actual=render_readiness.media(work/f"chapter_{c['index']:02d}.wav",'audio',probe)
  if abs(actual-c['duration'])>.15:raise ValueError('Saved chapter audio differs from narration timing.')
 checkpoint.seal(folder,'voice',voice_identity,[work/'chapters.json',work/'word-timing.json',work/'audio.txt']+[work/f"chapter_{c['index']:02d}.wav" for c in chapters])
 import footage_director
 checkpoint.stage(folder,'footage','Finding and validating missing chapter footage; completed clips are saved.')
 assets=footage_director.acquire(script,folder,chapters=chapters)
 if any(not Path(a['path']).is_file() for a in assets):raise ValueError('Restore the local cinematic footage catalog; no slide fallback is used.')
 words=json.loads((work/'word-timing.json').read_text())['words'];norm=lambda t:re.sub('[^a-z0-9]','',t.lower())
 if norm(' '.join(w['text'] for w in words))!=norm(' '.join(s['narration'] for s in script['sections'])):raise ValueError('Subtitle coverage does not match narration.')
 render(script,folder,chapters,assets)
 description=script['hook']+'\n\nLessons and original commentary inspired by '+script['book_title']+' by '+script['author']+'. Modern exercises are our interpretations, not author quotations. Footage is illustrative, not historical or location evidence.\n\nChapters:\n'+'\n'.join(f"{int(c['start'])//60}:{int(c['start'])%60:02d} {c['title']}" for c in chapters)+'\n\nSource: '+script['source_url']+'\n\nSubscribe to '+('MindLore for psychology from the original texts.\n#psychology #mindlore' if os.environ.get('BRAND')=='mindlore' else 'ShelfMade for thoughtful lessons from classic books.\n#books #philosophy #ShelfMade')
 (folder/'voice-settings.json').write_text(json.dumps({'engine':'Kokoro-82M','voice':'af_heart','speed':.95,'local':True,'provider_cost_usd':0}))
 (folder/'content-review.json').write_text(json.dumps({'version':VERSION,'source_kind':script['source_kind'],'review_required':True,'duration_range':([420,540] if os.environ.get('BRAND')=='mindlore' else [300,480]),'opening':script['hook'],'thumbnail_headline':script['thumbnail_headline'],'source_checkpoints':script['source_evidence'],'opening_payoff':script['opening_payoff'],'creative_director':script.get('creative_director'),'notes':'Owner must verify source accuracy, word timing and visual relevance.'},indent=2))
 (folder/'package.json').write_text(json.dumps({'title':script['book_title']+' · Cinematic draft','publish_title':script['public_title'],'book':book,'style':VERSION,'duration_range':([420,540] if os.environ.get('BRAND')=='mindlore' else [300,480])}))
 cq.seal(folder,json.loads((folder/'creative-review.json').read_text()),'THUMBNAIL.jpg')
 # Caption is the completion marker: incomplete renders never enter the review library.
 description+='\n\n'+(__import__('hashtags').mindlore if os.environ.get('BRAND')=='mindlore' else __import__('hashtags').shelfmade)(script['hook']+' '+script.get('book_title',''),'full')
 description+='\n\n'+footage_director.credit_block(assets,max(0,4800-len(description)-2))
 (folder/'POST_THIS.txt').write_text('--- TITLE ---\n'+script['public_title']+'\n\n--- DESCRIPTION ---\n'+description)
 footage_director.commit(folder,assets)
 checkpoint.stage(folder,'ready','Draft complete. Owner review is required before publishing.')
 return folder
