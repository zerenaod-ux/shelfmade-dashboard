#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
"$RUNTIME" - <<'PY'
import subprocess,sys,time,urllib.request
from pathlib import Path
base=Path.cwd()
# Only replace this dashboard, verified by its listening process's working folder.
r=subprocess.run(['/usr/sbin/lsof','-tiTCP:8765','-sTCP:LISTEN'],capture_output=True,text=True)
for raw in r.stdout.split():
 pid=int(raw)
 cwd=subprocess.run(['/usr/sbin/lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True).stdout
 command=subprocess.run(['/bin/ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
 if 'server.py' not in command or not any(line=='n'+str(base) or line=='n'+str(base.parent.parent) for line in cwd.splitlines()):
  print('Another application owns the dashboard port. Nothing was stopped.');sys.exit(1)
 subprocess.run(['/bin/kill','-INT',str(pid)],check=True)
 time.sleep(1)
log=open('dashboard.log','a')
subprocess.Popen([sys.executable,str(base/'server.py')],cwd=base,stdout=log,stderr=log,start_new_session=True)
for _ in range(40):
 try:
  with urllib.request.urlopen('http://127.0.0.1:8765/api/auth/status',timeout=1) as response:
   if response.status==200:break
 except Exception:time.sleep(.25)
else:print('Startup failed. See dashboard.log.');sys.exit(1)
print('ShelfMade is running in your normal laptop session. Open the dashboard and use Rebuild with narration on the caption-only job.')
subprocess.run(['open','https://naods-macbook-pro.tail7f86df.ts.net/'])
PY
read '?Press Enter to close.'
