"""Offline editorial and scene checks. Matching metadata is not source verification or vision."""
import hashlib,json,re
from pathlib import Path
VERSION='creative-review-v1'
STOP=set('a an the and or but if of for to in on at is are be it its this that your you we our what how why when one with from as by do does not'.split())
def tokens(text):
 return {re.sub(r'(ing|ed|s)$','',w) for w in re.findall('[a-z]+',str(text).lower()) if w not in STOP and len(w)>2}
def norm(text):return ' '.join(re.findall('[a-z0-9]+',str(text).lower()))
def related(a,b):
 if tokens(a)&tokens(b):return True
 # Conservative editorial families, not a claim of semantic/visual understanding.
 families=[('busy','time','hour','day','today','living','life'),('calm','anger','insult','response','control'),('truth','true','wrong','right','know','knowledge','learn','wise','wisdom','reason','belief','reality','see'),('effort','habit','thought','practice','choice','becoming'),('war','fight','victory','move','preparation'),('ordinary','opportunity','hidden','missing','overlooking'),('enough','desire','want','suffering'),('freedom','decide','decides','live'),('noticing','notice','look','attention','concentration','mind','nature')]
 return any(tokens(a)&tokens(' '.join(f)) and tokens(b)&tokens(' '.join(f)) for f in families)
def script_review(script,evidence,full=False):
 sections=script.get('sections') or [{'title':'Opening','narration':script.get('hook','')},*[{'title':'Lesson '+str(i+1),'narration':p} for i,p in enumerate(script.get('points',[]))]]
 hook=script.get('hook','').strip();headline=script.get('thumbnail_headline','').strip();public_title=script.get('public_title') or script.get('title','')
 errors=[];notes=[]
 director=script.get('creative_director')
 if director is not None:
  choices=director.get('candidates',[]);selected=[c for c in choices if c.get('id')==director.get('selected_id')]
  if len(choices)!=5 or len({norm(c.get('hook','')) for c in choices})!=5 or len(selected)!=1:errors.append('Creative director requires five distinct choices and one selected opening.')
  elif not selected[0].get('eligible') or selected[0].get('hook')!=hook or selected[0].get('headline')!=headline or selected[0].get('public_title')!=public_title:errors.append('Selected creative-director opening, cover and title must match the actual script.')
 if not 5<=len(hook.split())<=30:errors.append('Opening needs a complete, concise thought (5–30 words).')
 if not 2<=len(headline.split())<=6:errors.append('Cover headline must be a complete 2–6 word idea.')
 if not related(headline,hook):errors.append('Cover headline does not connect to the spoken opening. Rewrite the pair.')
 if not public_title or len(public_title)>100:errors.append('Public title must be present and at most 100 characters.')
 if re.search(r'\b(guaranteed|miracle|cure|instantly rich)\b',headline+' '+public_title,re.I):errors.append('Remove an unsupported outcome promise from the title or cover.')
 if not sections or not norm(sections[0].get('narration','')).startswith(norm(hook)):errors.append('Spoken opening and saved hook must agree.')
 if not evidence or any(not e.get('excerpt') or not e.get('source_url') for e in evidence):errors.append('Source checkpoints are missing. Restore evidence before rendering.')
 if not full and evidence and all(e.get('kind')=='source passage' for e in evidence) and not any(norm(hook) in norm(e.get('excerpt','')) for e in evidence):errors.append('Quoted opening is not present in its recorded source passage.')
 bodies=[s.get('narration','') for s in sections[1:]]
 for i,a in enumerate(bodies):
  for b in bodies[i+1:]:
   ta,tb=tokens(a),tokens(b)
   if ta and tb and len(ta&tb)/len(ta|tb)>.90:errors.append('Two lessons repeat the same content. Give each a distinct purpose.')
 payoff=script.get('opening_payoff',{})
 if full:
  index=payoff.get('section')
  if not isinstance(index,int) or not 1<=index<len(sections):errors.append('Opening promise needs a named lesson that pays it off.')
  elif not related(hook,sections[index]['narration']):errors.append('The promised opening topic is missing from its payoff lesson.')
 if any(e.get('kind')!='source passage' for e in evidence):notes.append('Summary/editorial checkpoints require comparison with the original book; they are not verified quotations.')
 return {'version':VERSION,'state':'blocked' if errors else 'script_checked','hook':hook,'headline':headline,'public_title':public_title,'payoff':payoff,'director':script.get('creative_director'),'source_checkpoints':evidence,'errors':list(dict.fromkeys(errors)),'notes':notes,'review_required':True,'limits':'Language and metadata checks only. Owner must check facts, voice, scene meaning and cover accuracy.'}
def require(report):
 if report['errors']:raise ValueError('Creative review: '+' '.join(report['errors']))
 return report
def save(folder,report):
 (Path(folder)/'creative-review.json').write_text(json.dumps(report,indent=2))
def scene_review(report,shots,chapters,assets):
 report=json.loads(json.dumps(report));errors=report['errors'];notes=report['notes'];ids=[];by_id={a['id']:a for a in assets}
 for chapter in chapters:
  group=[s for s in shots if s['chapter']==chapter['index']];cursor=chapter['start']
  if not group:errors.append('A chapter has no footage coverage.');continue
  for s in group:
   a=by_id.get(s.get('asset_id'));ids.append(s.get('asset_id'))
   if abs(s['start']-cursor)>.08 or s['unit']<=0:errors.append('Scene timeline has a gap or overlap.')
   cursor=s['start']+s['unit']
   if not s.get('narration_anchor') or not s.get('source_url') or not a:errors.append('A scene is missing narration or source provenance.')
   if a and (s['source_start']<0 or s['source_start']+s['duration']>a['duration']):errors.append('A scene extends beyond its source footage.')
   if a and a.get('provider')=='Pexels' and s.get('visual_theme') not in a.get('themes',[]):errors.append('A scene does not match its planned chapter theme.')
  if abs(cursor-(chapter['start']+chapter['duration']))>.08:errors.append('Footage does not cover the complete chapter.')
 if len(ids)!=len(set(ids)):errors.append('A source clip repeats inside this video. Choose fresh distinct footage.')
 runs=1;longest=1
 for a,b in zip(shots,shots[1:]):
  runs=runs+1 if a.get('search_query')==b.get('search_query') else 1;longest=max(longest,runs)
 if longest>=4:notes.append('Several consecutive scenes share a search. Watch for similar framing and add variety if needed.')
 versions={s.get('direction_version') for s in shots if s.get('direction_version')}
 report['scene_direction_version']=next(iter(versions)) if len(versions)==1 else None
 report.update(state='blocked' if errors else 'checked',errors=list(dict.fromkeys(errors)),scene_count=len(shots),distinct_clips=len(set(ids)),chapter_count=len(chapters),scenes=[{k:s.get(k) for k in ('chapter_title','start','unit','narration_anchor','visual_theme','visual_subject','visual_keywords','shot_intent','source_url','match_basis','direction_version','planned_intent','preferred_shot_role','role_matched','sentence_context','context_basis')} for s in shots])
 return report
def seal(folder,report,cover):
 folder=Path(folder);report['files']={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('script.json','content-review.json','storyboard.json',cover)}
 save(folder,require(report));return report
def verified(folder):
 folder=Path(folder)
 try:
  report=json.loads((folder/'creative-review.json').read_text())
  if report.get('version')!=VERSION or report.get('state')!='checked' or report.get('errors'):return False
  expected={'script.json','content-review.json','storyboard.json','THUMBNAIL.jpg' if (folder/'cinematic_LONGFORM.mp4').exists() else 'cover.jpg'}
  if set(report.get('files',{}))!=expected:return False
  return all(hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest for name,digest in report['files'].items())
 except (OSError,ValueError,KeyError,TypeError):return False
