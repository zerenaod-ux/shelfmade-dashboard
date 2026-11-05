"""Cached media checks and explicit editorial review requirements."""
import json,hashlib,subprocess
import creative_quality,media_runtime
from pathlib import Path
CACHE=Path(__file__).resolve().parent/'quality-cache'
def inspect(folder, video_name="final.mp4", full_video=False):
 folder=Path(folder);video=folder/video_name;caption=folder/'POST_THIS.txt'
 if not video.is_file() or not caption.is_file():return {'can_approve':False,'warnings':['Video or caption missing.'],'duration':None,'fingerprint':'missing'}
 stamp=str(full_video)+str(video.resolve())+str(video.stat().st_size)+str(video.stat().st_mtime_ns)+str(caption.stat().st_mtime_ns)
 policy=None
 try:policy=json.loads((folder/'package.json').read_text())
 except (OSError,ValueError):pass
 if full_video and policy and policy.get('style')=='cinematic-default-v1':
  thumb=folder/'THUMBNAIL.jpg'
  stamp+=str(thumb.stat().st_mtime_ns)+str(thumb.stat().st_size) if thumb.exists() else 'missing-thumbnail'
  stamp+=(folder/'package.json').read_text()
 creative_file=folder/'creative-review.json';creative=None
 if creative_file.exists():
  stamp+=creative_file.read_text(errors='replace')
  try:creative=json.loads(creative_file.read_text())
  except (OSError,ValueError):creative={}
  # Include the current inputs, not just the receipt, so changes invalidate approval/cache.
  for name in ('script.json','content-review.json','storyboard.json','THUMBNAIL.jpg' if full_video else 'cover.jpg'):
   p=folder/name;stamp+=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'missing-'+name
 else:
  try:
   if json.loads((folder/'script.json').read_text()).get('creative_policy')==creative_quality.VERSION:creative={};stamp+='creative-report-required'
  except (OSError,ValueError):pass
 warning=folder/'warning.txt';stamp+=warning.read_text() if warning.exists() else ''
 fingerprint=hashlib.sha256(stamp.encode()).hexdigest();CACHE.mkdir(exist_ok=True);cached=CACHE/(fingerprint+'.json')
 if cached.exists():
  try:
   previous=json.loads(cached.read_text())
   # Tool startup failures can be repaired without changing the approved media.
   if 'Media validation failed.' not in previous.get('warnings',[]):return previous
  except (OSError,ValueError):pass # Regenerate an unreadable optional cache; never lose inventory.
 warnings=[];duration=None;can_approve=True
 creative_valid=creative is None or creative_quality.verified(folder)
 if not creative_valid:warnings.append('Creative checks are incomplete or their inputs changed. Rebuild and review this draft.');can_approve=False
 try:
  r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(video)],capture_output=True,text=True,timeout=15,check=True,env=media_runtime.environment())
  data=json.loads(r.stdout);duration=round(float(data['format']['duration']),2);streams=data['streams']
  if not any(s['codec_type']=='video' for s in streams) or not any(s['codec_type']=='audio' for s in streams):warnings.append('Missing video or audio stream.');can_approve=False
  if not full_video and not any(s.get('width')==1080 and s.get('height')==1920 for s in streams):warnings.append('This video is not the expected 1080 × 1920 format.')
  if full_video and policy and policy.get('style')=='cinematic-default-v1':
   if not 300<=duration<=480:warnings.append('New full videos must be 5–8 minutes. Edit the script and rebuild.');can_approve=False
   if not (folder/'THUMBNAIL.jpg').is_file():warnings.append('A matching thumbnail is required.');can_approve=False
  if not full_video and duration>60:warnings.append('Longer than the current 60-second draft target.')
 except Exception:warnings.append('Media validation failed.');can_approve=False
 if warning.exists():warnings.append(warning.read_text().strip());can_approve=False
 creative_summary=None
 if creative is not None:
  creative_summary={k:creative.get(k) for k in ('version','state','hook','headline','public_title','payoff','scene_count','distinct_clips','chapter_count','source_checkpoints','notes','limits')}
  if not creative_valid:creative_summary['state']='needs_attention'
 result={'creative':creative_summary,'fingerprint':fingerprint,'duration':duration,'warnings':warnings,'can_approve':can_approve,'checks_required':['facts','narration','visuals']};cached.write_text(json.dumps(result));return result

def validate_decision(quality,checks):
 if not quality['can_approve']:raise ValueError('Resolve the media or narration warning before approval.')
 if not isinstance(checks,dict) or not all(checks.get(k) is True for k in ('facts','narration','visuals')):raise ValueError('Confirm source accuracy, narration, and visual quality before approval.')
