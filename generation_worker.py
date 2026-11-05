"""Run a media worker and persist only a safe, typed failure marker."""
import sys, runpy, json, faulthandler, signal
from pathlib import Path
import generation_recovery,render_capacity
script=sys.argv.pop(1)
faulthandler.register(signal.SIGUSR1,all_threads=True)
render_capacity.worker_deadline(7200 if Path(script).name=='full_jobs.py' else 1200)
folder=Path(sys.argv[-1]);folder.mkdir(parents=True,exist_ok=True)
try:runpy.run_path(script,run_name='__main__')
except Exception as error:
 temporary=generation_recovery.transient(error)
 (folder/'failure.json').write_text(json.dumps({'temporary':temporary,'code':getattr(error,'code',None)}))
 if Path(script).name=='full_jobs.py':
  import full_checkpoint
  full_checkpoint.stage(folder,'waiting' if temporary else 'blocked',str(error) if isinstance(error,ValueError) else 'Generation stopped; inspect the saved worker log.')
 raise
