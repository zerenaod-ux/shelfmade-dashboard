#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$RUNTIME" ]]; then
  print 'The dashboard runtime is unavailable. See README.md and docs/Maintenance.md to restore its configured Python path.'
  read '?Press Enter to close.'
  exit 1
fi
"$RUNTIME" - <<'PY'
import urllib.request,subprocess,sys,time
url='http://127.0.0.1:8765'
def ready():
 try:
  with urllib.request.urlopen(url+'/api/auth/status',timeout=1) as r:return r.status==200
 except Exception:return False
if not ready():
 log=open('dashboard.log','a')
 subprocess.Popen([sys.executable,'server.py'],stdout=log,stderr=log,start_new_session=True)
 for _ in range(30):
  if ready():break
  time.sleep(.1)
if ready():subprocess.run(['open',url])
else:print('Could not start ShelfMade. See dashboard.log.');sys.exit(1)
PY
