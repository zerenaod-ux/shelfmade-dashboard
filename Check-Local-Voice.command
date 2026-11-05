#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
"$RUNTIME" - <<'PY'
from pathlib import Path
import subprocess,json
folder=Path('voice-check');folder.mkdir(exist_ok=True)
voice=folder/'sample.aiff'
r=subprocess.run(['say','-v','Samantha','-o',str(voice),'Welcome to ShelfMade. A new classic, a new idea.'],capture_output=True)
p=subprocess.run(['/opt/homebrew/bin/ffprobe','-v','error','-show_entries','format=duration','-of','json',str(voice)],capture_output=True,text=True)
try:duration=float(json.loads(p.stdout)['format']['duration'])
except Exception:duration=0
result={'voice':'Samantha','duration_seconds':duration,'working':r.returncode==0 and duration>0}
(folder/'result.json').write_text(json.dumps(result,indent=2))
print('Local narration works.' if result['working'] else 'Local narration returned no usable audio. Codex can read voice-check/result.json.')
if result['working']:subprocess.run(['open',str(voice)])
PY
read '?Press Enter to close.'
