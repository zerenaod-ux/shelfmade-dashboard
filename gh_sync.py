"""Pull shorts built by GitHub Actions into the local review list. Read-only toward GitHub; never posts anything.
Each release asset <bookid>.zip is unpacked as a normal ready job (generated/<job>/1/), so review/approve works as usual."""
import json,subprocess,uuid,zipfile,tempfile,shutil,os
from pathlib import Path
import jobs
BASE=Path(__file__).resolve().parent
REPO='zerenaod-ux/shelfmade-dashboard'
STATE=BASE/'github-synced.json'
GH=next((p for p in ('/opt/homebrew/bin/gh','/usr/local/bin/gh') if Path(p).is_file()),'gh')
def _gh(*a,timeout=300):
 r=subprocess.run([GH,*a],capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
 return r.stdout
def _state():
 try:return json.loads(STATE.read_text())
 except (OSError,ValueError):return {'releases':[]}
def _import_full(z,tag,books):
 import full_jobs
 book=z.stem[5:]
 if book not in books:return 0
 jid=uuid.uuid4().hex;folder=full_jobs.ROOT/jid;folder.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(z) as f:
  for n in f.namelist():
   if n.startswith('/') or '..' in Path(n).parts:raise RuntimeError('Unsafe file name in '+z.name)
  f.extractall(folder)
 if not list(folder.glob('*_LONGFORM.mp4')):shutil.rmtree(folder,ignore_errors=True);return 0
 (folder/'built-on-github.txt').write_text('Built by GitHub Actions release '+tag+'\n')
 with full_jobs.connect() as c:c.execute("INSERT INTO full_jobs(id,book,state,version,attempts) VALUES (?,?,'ready','cinematic-default-v1',1)",(jid,book))
 return 1

def sync():
 st=_state();new=0;skipped=[]
 tags=[r['tagName'] for r in json.loads(_gh('release','list','--repo',REPO,'--limit','30','--json','tagName'))]
 books={b['id'] for b in jobs.BOOKS}
 for tag in reversed(tags):
  if not tag.startswith(('shorts-','full-')) or tag in st['releases']:continue
  with tempfile.TemporaryDirectory() as tmp:
   try:_gh('release','download',tag,'--repo',REPO,'--pattern','*.zip','--dir',tmp,timeout=900)
   except RuntimeError as e:
    if 'no assets' not in str(e).lower():raise
   for z in sorted(Path(tmp).glob('*.zip')):
    if z.stem.startswith('full-'):
     new+=_import_full(z,tag,books);continue
    book=z.stem
    if book not in books:skipped.append(book);continue
    jid=uuid.uuid4().hex;folder=jobs.ROOT/jid/'1';folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(z) as f:
     for n in f.namelist():
      if n.startswith('/') or '..' in Path(n).parts:raise RuntimeError('Unsafe file name in '+z.name)
     f.extractall(folder)
    if not (folder/'final.mp4').is_file() or not (folder/'POST_THIS.txt').is_file():shutil.rmtree(folder.parent,ignore_errors=True);skipped.append(book);continue
    (folder/'built-on-github.txt').write_text('Built by GitHub Actions release '+tag+'\n')
    with jobs.connect() as c:
     ed=(c.execute('SELECT max(edition) FROM jobs WHERE book=?',(book,)).fetchone()[0] or 0)+1
     c.execute("INSERT INTO jobs(id,book,state,attempts,edition) VALUES (?,?,'ready',1,?)",(jid,book,ed))
    new+=1
  st['releases'].append(tag)
  tmpf=STATE.with_suffix('.tmp');tmpf.write_text(json.dumps(st));os.replace(tmpf,STATE)
 return {'new':new,'skipped':skipped}

def build(n):
 """Ask GitHub's free server to build N more Shorts now (about 4 minutes each plus 4 minutes setup)."""
 n=max(1,min(int(n),9))
 _gh('workflow','run','daily-shorts.yml','--repo',REPO,'-f','count='+str(n))
 return {'started':n,'note':'GitHub is building '+str(n)+' short(s). Ready in about '+str(6+4*n)+' minutes. Then press Get new videos.'}


def build_full():
 """Ask GitHub's free server to build one full video (can take 1-4 hours)."""
 _gh('workflow','run','full-video.yml','--repo',REPO)
 return {'started':1,'note':'GitHub is building 1 full video. This can take 1 to 4 hours. Then press Get new videos.'}
