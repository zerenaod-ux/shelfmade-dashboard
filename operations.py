"""Local-only owner operations snapshot. No provider calls, deletion or secret values."""
import datetime,json,os,sqlite3,shutil,threading,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
LOCK=threading.Lock();CACHE=None;CACHED_AT=0
CATEGORIES={'generated':'Short drafts','full-generated':'Full-video drafts','replacements':'Replacement drafts','footage-cache':'Footage library','backups':'State/source backups','quality-cache':'Rebuildable previews','generator':'Generator assets'}
def measure(path):
 count=size=0
 if path.is_symlink():return {'bytes':0,'files':0,'complete':True}
 for root,dirs,files in os.walk(path,followlinks=False):
  dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink()]
  for name in files:
   p=Path(root)/name
   try:
    if p.is_symlink():continue
    size+=p.stat().st_size;count+=1
   except OSError:continue
   if count>=100000:return {'bytes':size,'files':count,'complete':False}
 return {'bytes':size,'files':count,'complete':True}
def read_db(path,query,args=()):
 if not path.is_file():return []
 try:
  with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5) as c:c.row_factory=sqlite3.Row;return [dict(r) for r in c.execute(query,args)]
 except sqlite3.Error:return []
def snapshot(force=False):
 global CACHE,CACHED_AT
 with LOCK:
  if not force and CACHE is not None and time.time()-CACHED_AT<60:return CACHE
  now=datetime.datetime.now(datetime.timezone.utc);day=now.date().isoformat()
  storage=[{'label':label,**measure(BASE/name)} for name,label in CATEGORIES.items()]
  space=shutil.disk_usage(BASE);usage=read_db(BASE/'private-buffer/request-budget.sqlite3','SELECT COALESCE(SUM(requests),0) AS requests FROM usage WHERE day=?',(day,));holds=read_db(BASE/'private-buffer/request-budget.sqlite3','SELECT COALESCE(SUM(remaining),0) AS count FROM budget_holds WHERE day=? AND expires>?',(day,time.time()))
  used=usage[0]['requests'] if usage else None;reserved=holds[0]['count'] if holds else 0
  searches=read_db(BASE/'footage-history.sqlite3','SELECT count(*) AS count FROM requests WHERE at>?',(time.time()-3600,))
  try:receipt=json.loads((BASE/'operations-receipts.json').read_text())
  except (OSError,ValueError):receipt={}
  snapshots=sorted(p for p in (BASE/'backups').glob('*/manifest.json') if not p.is_symlink())
  last=None
  if snapshots:
   try:
    manifest=json.loads(snapshots[-1].read_text());last={'name':snapshots[-1].parent.name,'created_at':manifest['created_at_utc'],'files':len(manifest['sha256']),'scope':manifest['scope']}
   except (OSError,ValueError,KeyError):pass
  services=[{'name':'Kokoro narration / local rendering','status':'Local; no paid voice API','billing':'No metered provider calls for local narration/rendering. Laptop electricity and hardware are not measured.'},
   {'name':'Buffer','status':f'{used} / 90 local calls used today; {reserved} reserved' if used is not None else 'Local usage unavailable','billing':'Local guard: 90 calls per UTC day, analytics pause at 65. This is an app safeguard, not the provider plan limit. Account plan and invoice not connected.','url':'https://publish.buffer.com/settings'},
   {'name':'Pexels','status':str(searches[0]['count'])+' / 150 local search calls in the last hour' if searches else 'Local usage unavailable','billing':'App search guard only. Provider account allowance is not queried.','url':'https://www.pexels.com/api/'},
   {'name':'Cloudinary video hosting','status':'Credential file present' if (BASE/'private-cloudinary/credentials.json').is_file() else 'Not configured','billing':'Storage, bandwidth, plan and invoices are not connected here. Check the provider console.','url':'https://console.cloudinary.com/'},
   {'name':'Google / YouTube','status':'Credential file present' if (BASE/'private-google/tokens.json').is_file() else 'Not configured','billing':'Provider quota and invoices are not connected here.','url':'https://console.cloud.google.com/apis/dashboard'},
   {'name':'Tailscale / iCloud / other subscriptions','status':'Not tracked by this app','billing':'No total monthly expense can be verified from local publishing records.'}]
  CACHE={'available':True,'checked_at':now.isoformat(),'free_bytes':space.free,'low_storage':space.free<10*1024**3,'storage':storage,'last_snapshot':last,'restore_test':receipt.get('restore_test'),'encrypted_backup':receipt.get('encrypted_backup'),'services':services,'automatic_deletion':False,'billing_verified':False,'monthly_total_usd':None,'backup_note':'State/source snapshots stay on this laptop and exclude media/credentials. Encrypted export is opt-in; an off-device copy is not assumed.','retention':'Keep originals, approved media, source/provenance, claims and credentials. Review temporary render folders only after a verified recovery copy. No files are automatically removed.'}
  CACHED_AT=time.time();return CACHE
