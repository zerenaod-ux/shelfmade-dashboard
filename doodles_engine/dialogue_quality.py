"""Short-only dialogue and measured-media gates; no model or media generation."""
import json,math,re,subprocess
from pathlib import Path
POLICY='complete-conversation-v1'
MIN_SECONDS=40.0
MAX_SECONDS=70.0
REACTION_SECONDS=0.9
def story_errors(story,require_review=False):
    errors=[];shots=story.get('shots',[])
    if len(shots)!=6:return ['Short needs six story beats']
    lines=[line for shot in shots for line in shot.get('lines',[])]
    if not lines:return ['Dialogue is empty']
    if any(not 1<=len(shot.get('lines',[]))<=3 for shot in shots):errors.append('Each shot needs one to three conversational turns')
    if any(not 1<=len(str(line.get('text','')).split())<=16 for line in lines):errors.append('Each turn needs one to sixteen words')
    words=sum(len(str(line.get('text','')).split()) for line in lines)
    if not 125<=words<=165:errors.append('Short dialogue needs 125–165 spoken words; measured duration remains authoritative')
    final=str(lines[-1].get('text','')).strip().rstrip('"\'')
    if not final or re.search(r'(?:\.\.\.|…|—|-)$',final) or not final.endswith(('.','!')):errors.append('Final reply must be a complete sentence, not a dangling loop')
    if re.search(r'\b(to be continued|part two tomorrow|find out next time)\b',final,re.I):errors.append('Resolve this short instead of postponing its ending')
    if require_review:
        if story.get('dialogue_policy')!=POLICY:errors.append('Story predates the complete-conversation policy')
        review=story.get('dialogue_review') or {}
        if review.get('complete') is not True or review.get('natural') is not True:errors.append('Dialogue needs a completed naturalness and resolution review')
        try:
            scores=[float(review.get(k,0)) for k in ('spoken','ending')]
            if any(not math.isfinite(v) or v<7 for v in scores):errors.append('Spoken delivery and ending must score at least seven')
        except (TypeError,ValueError):errors.append('Dialogue review scores are invalid')
    return errors
def require_story(story):
    errors=story_errors(story,True)
    if errors:raise ValueError('; '.join(errors))
def require_duration(seconds,last_line_end=None):
    if not math.isfinite(seconds) or not MIN_SECONDS<=seconds<=MAX_SECONDS:
        raise ValueError('Animation Doodles short must measure 40–70 seconds; repair dialogue, never pad silence or cut speech')
    if last_line_end is not None and seconds-last_line_end<0.7:
        raise ValueError('Final spoken reply needs a brief reaction before the video ends')
def verify_encoded(work,total,last_line_end):
    work=Path(work)
    raw=subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(work/'short.mp4')])
    media=json.loads(raw);streams=media.get('streams',[])
    video=next((s for s in streams if s.get('codec_type')=='video'),None)
    audio=next((s for s in streams if s.get('codec_type')=='audio'),None)
    if not video or not audio:raise ValueError('Finished short must contain both audio and video')
    seconds=float(media['format']['duration']);require_duration(seconds,last_line_end)
    for track in (audio,video):
        end=float(track.get('duration',seconds))
        if end<last_line_end+0.65:raise ValueError('Encoded track ends before the final reply and reaction finish')
    if abs(seconds-total)>.12:raise ValueError('Encoded duration differs from the complete dialogue timeline')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(work/'short.mp4'),'-f','null','-'],check=True,timeout=180)
    report={'policy':POLICY,'duration':seconds,'last_line_end':last_line_end,'reaction_seconds':seconds-last_line_end,'complete_media_decode':True,'human_listening_completed':False}
    (work/'dialogue-quality.json').write_text(json.dumps(report,indent=2))
    return report
