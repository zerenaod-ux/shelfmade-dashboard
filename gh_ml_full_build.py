"""MindLore GitHub builder (BRAND=mindlore, 7-9 min, curated scripts only): makes N full videos one after another (never the same book twice, never a book already made on this Mac)."""
import json,sys,subprocess,shutil,os
os.environ['BRAND']='mindlore'
from pathlib import Path
sys.path.insert(0,'.')
def load(p,d):
 try:return json.loads(Path(p).read_text())
 except (OSError,ValueError):return d
def main(n):
 state=Path('gh-state/built-full-mindlore.json');state.parent.mkdir(exist_ok=True)
 built=load(state,[]);books=[{'id':p.stem} for p in sorted(Path('cinematic-scripts-mindlore').glob('*.json'),key=lambda p:(p.stem.count('-'),p.stem))];skip=set();made=0
 import full_jobs
 Path('out').mkdir(exist_ok=True)
 for i in range(n*5):
  if made>=n:break
  done=set(built)|skip
  book=None
  for b in books:
   if b['id'] in done:continue
   bid,_,var=b['id'].partition('-');os.environ['ML_VARIANT']=var
   try:full_jobs.script_for(bid)
   except Exception:skip.add(b['id']);continue
   book=b['id'];break
  if not book:print('No eligible unused book left');break
  bid,_,var=book.partition('-');os.environ['ML_VARIANT']=var
  folder=Path('out/f_'+book)
  if folder.exists():shutil.rmtree(folder)
  print('=== Building FULL video',i+1,'of',n,'book',book,flush=True)
  r=subprocess.run([sys.executable,'full_jobs.py',bid,str(folder)],capture_output=True,text=True)
  print((r.stdout+r.stderr)[-1500:],flush=True)
  if r.returncode or not list(folder.glob('*_LONGFORM.mp4')):print('FAILED',book);skip.add(book);continue
  z=Path('out/mlfull-'+book+'.zip')
  subprocess.run(f"cd {folder} && (zip -q ../mlfull-{book}.zip *_LONGFORM.mp4 *.json *.txt *.jpg 2>/dev/null || zip -q ../mlfull-{book}.zip *_LONGFORM.mp4 POST_THIS.txt)",shell=True)
  if not z.is_file():print('ZIP FAILED',book);continue
  built.append(book);state.write_text(json.dumps(built));made+=1;print('BUILT',book,flush=True)
  # free runner disk before the next build (keeps the zip)
  shutil.rmtree(folder,ignore_errors=True)
  for d in ('footage-cache','local-video-cache','work'):shutil.rmtree(d,ignore_errors=True)
  os.makedirs('footage-cache',exist_ok=True);os.makedirs('local-video-cache',exist_ok=True)
 print('made',made,'of',n);sys.exit(0 if made else 1)
if __name__=='__main__':main(max(1,min(int(sys.argv[1]) if len(sys.argv)>1 else 1,8)))
