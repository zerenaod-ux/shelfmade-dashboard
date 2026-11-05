"""GitHub builder: makes N Shorts without ever repeating a passage already used on the Mac or on GitHub."""
import json,sys,subprocess,shutil,os,time
from collections import Counter
from pathlib import Path
def load(p,default):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return default
ML=os.environ.get('BRAND')=='mindlore'
BOOKS='mindlore-books.json' if ML else 'books.json'
BUILT='built-mindlore.json' if ML else 'built-books.json'
USED='used-mindlore.json' if ML else 'used-gh.json'
def main(count):
 books=load(BOOKS,[]);state=Path('gh-state');state.mkdir(exist_ok=True)
 built=load(state/BUILT,[]);used=load(state/USED,{'books':{}})
 counts=Counter(built)
 order=sorted(range(len(books)),key=lambda i:(counts[books[i]['id']],i))  # least-used books first
 out=Path('out');out.mkdir(exist_ok=True);made=0;tried=0
 for i in order:
  if made>=count or tried>=count*8:break
  b=books[i];tried+=1;bid=b['id'];folder=out/bid
  if folder.exists():shutil.rmtree(folder)
  print('=== Trying book',bid,b['title'],flush=True)
  try:r=subprocess.run([sys.executable,'worker.py',json.dumps(b),'1',str(folder)],capture_output=True,text=True,timeout=1800)
  except subprocess.TimeoutExpired:print('timeout',bid);continue
  print((r.stdout+r.stderr)[-600:],flush=True)
  if r.returncode or not (folder/'final.mp4').is_file():print('skipped',bid,'(no unused passages or failed)');continue
  review=load(folder/'content-review.json',{})
  used['books'].setdefault(bid,[]).extend(x for x in review.get('source_sentences',[]) if isinstance(x,str))
  if isinstance(review.get('hook'),str):used['hooks']=(used.get('hooks',[])+[review['hook']])[-80:]   # variety guard memory
  built.append(bid)
  (state/BUILT).write_text(json.dumps(built));(state/USED).write_text(json.dumps(used))
  shutil.copy(folder/'final.mp4',out/f'{bid}-final.mp4');shutil.copy(folder/'POST_THIS.txt',out/f'{bid}-POST_THIS.txt')
  subprocess.run(f"cd out/{bid} && zip -q -r ../{bid}.zip . -x 'f_*.png' 'local-motion*' 'kokoro_*.wav' 'source.txt' '*.tmp'",shell=True)
  if ML:os.replace(out/f'{bid}.zip',out/f'ml-{bid}-{int(time.time())}.zip')
  made+=1;print('BUILT',bid,flush=True)
 print('made',made,'of',count);sys.exit(0 if made else 1)
if __name__=='__main__':main(int(sys.argv[1]) if len(sys.argv)>1 else 3)
