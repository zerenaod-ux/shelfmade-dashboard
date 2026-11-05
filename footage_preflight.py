"""Bounded metadata planning before narration. Metadata is not visual verification."""
import json,math
from pathlib import Path
import footage_director as f,scene_direction,full_checkpoint as checkpoint

def check(script,folder):
 folder=Path(folder);checkpoint.stage(folder,'footage_preflight','Checking fresh footage for every chapter before narration.')
 chapters=[];cursor=0
 for index,section in enumerate(script['sections']):
  duration=len(section['narration'].split())/2.6
  chapter={'index':index,'title':section['title'],'narration':section['narration'],'start':cursor,'duration':duration}
  if section['title']=='cta' and index:chapter['visual_context']=script['sections'][index-1]['narration']
  chapters.append(chapter);cursor+=duration
 groups={}
 mindlore_full=script.get('brand')=='mindlore' and script.get('format')=='full'
 for beat in scene_direction.plan(chapters,long_scene_seconds=12 if mindlore_full else 8):
  b=beat['visual'];key=(b['theme'],b.get('subject','theme'))
  if key not in groups:groups[key]=[dict(b,queries=list(b['queries'])),0]
  else:
   for q in b['queries']:
    if q not in groups[key][0]['queries']:groups[key][0]['queries'].append(q)
  groups[key][1]+=1
 # A tiny per-group pool can create a false shortage when related groups share
 # their first results. Inspect enough candidates to satisfy their combined demand.
 # This changes metadata breadth, never freshness, matching, or request limits.
 grouped=list(groups.values())
 def candidate_target(brief,required):
  queries=set(brief['queries'])
  return required+2+sum(count for other,count in grouped if other is not brief and queries.intersection(other['queries']))
 excluded=f.used_ids(folder.resolve());searches=0;reports=[];pools=[]
 for index,(b,required) in enumerate(groups.values()):
  target=candidate_target(b,required)
  found=[];allowance=f.search_allowance(f.MAX_SEARCHES-searches,[n for _,n in list(groups.values())[index:]]);spent=0
  for page in range(1,f.MAX_SEARCH_PAGES+1):
   for query in b['queries']:
    if len(found)>=target:break
    if f.cached_page_exhausted(query,page,excluded|set(found)):continue
    data=f.cached_search_page(query,page)
    if data is None:
     if searches>=f.MAX_SEARCHES or spent>=allowance:continue
     searches+=1;spent+=1;data=f.search(query,page)
    for video in data.get('videos',[]):
     ident='pexels-'+str(video['id'])
     formats=[x for x in video.get('video_files',[]) if x.get('file_type')=='video/mp4' and x.get('width',0)>=1280 and x.get('height',0)>=720 and x.get('width',0)>x.get('height',0)]
     if ident in excluded|set(found) or video.get('duration',0)<(15 if mindlore_full else 12) or not formats or not f.metadata_match(video,query) or f.invalid_cached_asset(ident):continue
     found.append(ident)
     if len(found)>=target:break
   if len(found)>=target:break
  pools.append((found,required))
  reports.append({'theme':b['theme'],'subject':b.get('subject','theme'),'required':required,'found':len(found),'queries':b['queries']})
  report={'version':'footage-preflight-v2','state':'passed' if len(found)>=required else 'waiting_for_footage','provider_searches':searches,'groups':reports,'estimated_timing':True,'review_required':True}
  checkpoint.write(folder/'footage-preflight.json',report)
  if len(found)<required:
   from generation_recovery import RecoverableGenerationError
   raise RecoverableGenerationError('Footage preflight: '+b['theme']+' has '+str(len(found))+' of '+str(required)+' fresh matching candidates. Narration has not started.','footage_shortage')
 # Validate one distinct candidate for each estimated shot across overlapping themes.
 options=[pool for pool,count in pools for _ in range(count)];owners={}
 def assign(index,visited):
  for ident in options[index]:
   if ident in visited:continue
   visited.add(ident)
   if ident not in owners or assign(owners[ident],visited):owners[ident]=index;return True
  return False
 for index in sorted(range(len(options)),key=lambda i:len(options[i])):
  if not assign(index,set()):
   report['state']='waiting_for_footage';report['distinct_assignment']=False;checkpoint.write(folder/'footage-preflight.json',report)
   from generation_recovery import RecoverableGenerationError
   raise RecoverableGenerationError('Footage preflight: chapters share too few distinct matching candidates. Narration has not started.','footage_shortage')
 report['distinct_assignment']=True;checkpoint.write(folder/'footage-preflight.json',report)
 return report
