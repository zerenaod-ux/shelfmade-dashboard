"""One deterministic narration-to-shot plan shared by search and editing.
No media/network operations. Sentence context is explicit, never called visual proof.
"""
import math,re,hashlib,json
VERSION='scene-direction-v1'

def norm(text):return re.sub('[^a-z0-9]','',text.lower())

def sentence_context(chapter,spoken,words,start,end):
 sentences=[s.strip() for s in re.split(r'(?<=[.!?])\s+',chapter['narration']) if s.strip()]
 if not sentences:return chapter['narration'],'chapter_continuity'
 timed=[w for w in words if chapter['start']<=w['start']<chapter['start']+chapter['duration'] and norm(w['text'])]
 reference=[norm(w) for s in sentences for w in s.split() if norm(w)]
 # Match complete normalized streams before attributing a timestamp to a sentence.
 if timed and ''.join(norm(w['text']) for w in timed)==''.join(reference):
  center=(start+end)/2;position=min(range(len(timed)),key=lambda i:abs(timed[i]['start']-center))
  # Character counts tolerate punctuation being split into standalone voice tokens.
  target=sum(len(norm(w['text'])) for w in timed[:position]);cursor=0
  for sentence in sentences:
   cursor+=len(norm(sentence))
   if target<cursor:return sentence,'timed_sentence'
 # Shorts lack word timing here: proportional sentence position is labelled honestly.
 index=min(len(sentences)-1,int(max(0,(start-chapter['start']))/chapter['duration']*len(sentences)))
 return sentences[index],'estimated_sentence'

def plan(chapters,words=None,short_mode=False,long_scene_seconds=8):
 import footage_director as f
 if not isinstance(long_scene_seconds,(int,float)) or not math.isfinite(long_scene_seconds) or long_scene_seconds<8:raise ValueError('Long-form scene interval must be at least eight seconds.')
 words=words or [];beats=[]
 for chapter in chapters:
  if chapter['duration']<=0:raise ValueError('Scene direction requires positive measured chapter duration.')
  interval=(2.5 if short_mode else 3) if chapter['index']==0 else (5 if short_mode else long_scene_seconds)
  count=math.ceil(chapter['duration']/interval);unit=chapter['duration']/count
  for index in range(count):
   start=chapter['start']+index*unit;end=start+unit
   spoken=' '.join(w['text'] for w in words if start<=w['start']<end).strip()
   sentence,context_basis=sentence_context(chapter,spoken,words,start,end)
   anchor=spoken or sentence
   try:visual=f.brief(sentence if context_basis=='timed_sentence' else anchor,chapter['title']);basis=context_basis if context_basis=='timed_sentence' or not spoken else 'spoken_words'
   except ValueError:
    try:visual=f.brief(sentence,chapter['title']);basis=context_basis
    except ValueError:
     visual=f.brief(chapter.get('visual_context',chapter['narration']),chapter['title']);basis='chapter_continuity'
   phase='establish' if index==0 else 'resolve' if index==count-1 else ('detail','action','contrast')[(index-1)%3]
   role={'resolve':'detail','contrast':'establish'}.get(phase,phase)
   beats.append({'direction_version':VERSION,'chapter':chapter['index'],'chapter_title':chapter['title'],'start':round(start,5),'unit':unit,'narration_anchor':anchor,'sentence_context':sentence,'context_basis':basis,'planned_intent':phase,'preferred_shot_role':role,'visual':visual,'review_required':True})
 return beats

def receipt(chapters,words,beats):
 return {'version':VERSION,'input_sha256':hashlib.sha256(json.dumps({'chapters':chapters,'words':words},sort_keys=True).encode()).hexdigest(),'beats':beats,'limits':'Measured shot intervals; sentence placement is labelled timed or estimated. Filmable themes and shot roles use metadata, not vision. Review actual footage and metaphor accuracy.'}
