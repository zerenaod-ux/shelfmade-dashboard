"""Bounded pitch-preserving pacing before lip-sync; retains original voice assets."""
import json,shutil,subprocess,wave
from pathlib import Path

def duration(path):
 with wave.open(str(path),'rb') as audio:return audio.getnframes()/audio.getframerate()

def prepare(work):
 from render import dialogue_timeline
 from dialogue_quality import require_duration
 work=Path(work);story,timeline,total=dialogue_timeline(work)
 if 40<=total<=70:return {'changed':False,'before':total,'after':total}
 # Natural pacing is allowed; silence padding, trimming spoken words and extreme
 # time compression are not. Larger failures go back to script/voice repair.
 target=65. if total>70 else 44.
 speech=sum(line['end']-line['start'] for shot in timeline for line in shot['lines'])
 overhead=total-speech;factor=speech/(target-overhead)
 if not .88<=factor<=1.20:raise ValueError('Dialogue needs script/voice repair beyond bounded natural pacing')
 if any(work.glob('ls_out/*.mp4')) or any(work.glob('lip_*.npz')):raise ValueError('Pacing must finish before lip-sync assets exist')
 originals=work/'voice-originals';originals.mkdir(exist_ok=True)
 changes=[]
 for si,shot in enumerate(story['shots']):
  for li,_ in enumerate(shot['lines']):
   path=work/f'line_{si:02d}_{li:02d}.wav';backup=originals/path.name
   if not backup.exists():shutil.copyfile(path,backup)
   old=duration(path);temp=path.with_suffix('.paced.wav')
   subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-af',f'atempo={factor:.8f}','-ar','24000','-ac','1','-c:a','pcm_s16le',str(temp)],check=True,timeout=30)
   new=duration(temp)
   if not .5<new<60:raise ValueError('Paced voice length is invalid')
   temp.replace(path)
   alignment=work/f'align_{si:02d}_{li:02d}.json'
   if alignment.exists():
    saved=originals/alignment.name
    if not saved.exists():shutil.copyfile(alignment,saved)
    data=json.loads(alignment.read_text());ratio=new/old
    data['segs']=[[a*ratio,b*ratio,level] for a,b,level in data['segs']]
    alignment.write_text(json.dumps(data))
   changes.append({'file':path.name,'original_seconds':old,'paced_seconds':new})
 _,new_timeline,actual=dialogue_timeline(work);require_duration(actual,new_timeline[-1]['lines'][-1]['end'])
 report={'changed':True,'before':total,'after':actual,'speed_factor':factor,'method':'pitch-preserving atempo before lip-sync','originals_retained':True,'spoken_words_removed':False,'lines':changes}
 (work/'pacing-report.json').write_text(json.dumps(report,indent=2));return report
