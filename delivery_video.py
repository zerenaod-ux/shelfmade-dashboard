"""Create a platform-compatible copy without changing the reviewed original."""
import hashlib,json,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parent
CACHE=BASE/'delivery-cache'
def prepare(path,fingerprint):
 path=Path(path);CACHE.mkdir(mode=0o700,exist_ok=True)
 target=CACHE/(fingerprint+'-30fps.mp4')
 if not target.exists():
  pending=CACHE/(fingerprint+'-pending.mp4')
  try:
   subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-y','-i',str(path),'-map','0:v:0','-map','0:a:0','-vf','fps=30','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(pending)],check=True,capture_output=True,timeout=300)
   pending.replace(target)
  except Exception:raise ValueError('Could not prepare a compatible delivery video; nothing was published.') from None
 result=json.loads(subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=avg_frame_rate','-of','json',str(target)],check=True,capture_output=True,text=True).stdout)
 if result['streams'][0]['avg_frame_rate']!='30/1':raise ValueError('Delivery frame-rate verification failed.')
 return target,hashlib.sha256(target.read_bytes()).hexdigest()
