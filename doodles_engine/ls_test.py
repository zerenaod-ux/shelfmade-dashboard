"""Try cloud lip-sync on a COPY of an existing video (original stays untouched, posting schedule untouched).
Usage: python ls_test.py <source video folder>  -> new folder '<name>-ls' that shows up in the review page."""
import json,shutil,subprocess,sys,datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
src=Path(sys.argv[1]).resolve();dst=src.parent/(src.name+'-ls')
if dst.exists():shutil.rmtree(dst)
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('package.json','short.mp4','silent.mp4','ls_*','ls_in','ls_out','ls_kernel'))
subprocess.run([sys.executable,str(HERE/'ls_cloud.py'),str(dst)],check=True)
subprocess.run([sys.executable,str(HERE/'render.py'),str(dst)],check=True)
pk=json.loads((src/'package.json').read_text());pk['id']=dst.name;pk['status']='ready';pk['created']=datetime.datetime.now().isoformat()
for k in ('approved_at','posting'):pk.pop(k,None)
(dst/'package.json').write_text(json.dumps(pk,indent=1));print('READY FOR REVIEW:',dst.name)
