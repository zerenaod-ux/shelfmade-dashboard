"""Offline video readiness gates; no downloads, rendering or publishing.
Probe metadata establishes technical readability, not complete decode or relevance.
"""
import json,math,re,shutil
import media_runtime
from pathlib import Path
VERSION='render-readiness-v1'

def number(value,label,positive=False):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (positive and value<=0):raise ValueError('Render readiness: invalid '+label+'. Rebuild narration or scene timing.')
 return value

def media(path,kind,probe):
 p=Path(path)
 if not p.is_file() or p.stat().st_size==0:raise ValueError('Render readiness: missing or empty '+kind+' asset. Restore it before retrying.')
 try:
  data=probe(p);duration=float(data['format']['duration'])
  valid=math.isfinite(duration) and duration>0 and any(s.get('codec_type')==kind for s in data['streams'])
 except media_runtime.MediaRuntimeError:raise
 except Exception:
  media_runtime.require_ready()
  valid=False
 if not valid:raise ValueError('Render readiness: unreadable '+kind+' metadata. Restore the asset before retrying.')
 return duration

def prerequisites(config,voice_ready,font,probe):
 for name in ('ffmpeg','ffprobe'):
  if not shutil.which(name):raise ValueError('Render readiness: '+name+' is unavailable. Restore the media tools.')
 media_runtime.require_ready()
 if not voice_ready:raise ValueError('Render readiness: local Kokoro runtime or model folder is missing.')
 from PIL import ImageFont
 try:ImageFont.truetype(str(font),32)
 except Exception:raise ValueError('Render readiness: subtitle font is unavailable. Restore the approved font.') from None
 music=Path(config['music_path']);music_state='checked'
 if config.get('music_optional') and not music.exists():music_state='optional music absent; existing narration-only mode preserved'
 else:media(music,'audio',probe)
 return {'version':VERSION,'stage':'dependencies_checked','music':music_state,'review_required':True}

def narration(script,chapters,words):
 if not chapters or not words:raise ValueError('Render readiness: narration chapters or subtitles are missing.')
 sections=script.get('sections',[])
 if len(sections)!=len(chapters):raise ValueError('Render readiness: chapter count differs from the script.')
 cursor=0
 norm=lambda text:re.sub('[^a-z0-9]','',str(text).lower())
 for i,(section,c) in enumerate(zip(sections,chapters)):
  start=number(c.get('start'),'chapter start');duration=number(c.get('duration'),'chapter duration',True)
  if c.get('index')!=i or abs(start-cursor)>.08 or norm(c.get('narration'))!=norm(section.get('narration')):raise ValueError('Render readiness: chapter order, coverage or narration differs from the script.')
  cursor=start+duration
 previous=0
 for w in words:
  start=number(w.get('start'),'subtitle start');end=number(w.get('end'),'subtitle end')
  if not isinstance(w.get('text'),str) or not w['text'].strip() or end<=start or start<previous-.02 or end>cursor+.08:raise ValueError('Render readiness: subtitle timing is empty, reversed or outside narration.')
  previous=start
 if norm(' '.join(w['text'] for w in words))!=norm(' '.join(s['narration'] for s in sections)):raise ValueError('Render readiness: subtitle words differ from the exact narration.')
 for c in chapters:
  if not any(c['start']<=w['start']<c['start']+c['duration'] for w in words):raise ValueError('Render readiness: a chapter has no timed subtitles.')
 return {'version':VERSION,'stage':'narration_checked','chapter_count':len(chapters),'word_count':len(words),'duration':round(cursor,4),'review_required':True}

def scene_sources(chapters,shots,probe):
 durations={};cursor=0
 if not shots:raise ValueError('Render readiness: no planned scenes.')
 for shot in shots:
  start=number(shot.get('start'),'scene start');unit=number(shot.get('unit'),'scene coverage',True);hold=number(shot.get('duration'),'scene duration',True);offset=number(shot.get('source_start'),'source offset')
  if abs(start-cursor)>.08 or hold<unit:raise ValueError('Render readiness: scene coverage has a gap or overlap.')
  path=str(Path(shot['source']).resolve())
  if path not in durations:durations[path]=media(path,'video',probe)
  if offset+hold>durations[path]+.08:raise ValueError('Render readiness: a scene exceeds its real source duration. Restore footage or rebuild the plan.')
  cursor=start+unit
 if abs(cursor-sum(c['duration'] for c in chapters))>.08:raise ValueError('Render readiness: scenes do not cover the complete narration.')
 return {'source_count':len(durations),'scene_count':len(shots)}

def footage(script,chapters,words,shots,folder,probe):
 receipt=narration(script,chapters,words);sources=scene_sources(chapters,shots,probe)
 for c in chapters:
  duration=media(Path(folder)/'.render'/f"chapter_{c['index']:02d}.wav",'audio',probe)
  if abs(duration-c['duration'])>.15:raise ValueError('Render readiness: chapter audio duration differs from its timeline. Rebuild narration.')
 return {**receipt,'stage':'ready_for_encoding',**sources,'limits':'Metadata and timing checks only; full decode, source accuracy, voice and visual relevance still require final checks and owner review.'}

def record(folder,stage,check):
 """Persist one bounded result before propagating a failure to normal job handling."""
 path=Path(folder)/'render-readiness.json'
 try:report=check()
 except Exception as error:
  path.write_text(json.dumps({'version':VERSION,'stage':stage,'state':'blocked','message':str(error) if isinstance(error,ValueError) else 'Readiness check failed. Inspect the local job log.','review_required':True},indent=2));raise
 report={**report,'state':'passed'};path.write_text(json.dumps(report,indent=2));return report
