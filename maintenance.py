"""Owner maintenance CLI. Check is read-only; backup protects state/code, not media.
Never sends a provider request, starts a worker, publishes or prints credential values.
Run with the app's configured Python runtime. See README.md before restoring.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil,sqlite3,stat,sys,urllib.request
BASE=Path(__file__).resolve().parent
DATABASES=['decisions.sqlite3','footage-history.sqlite3','private-buffer/request-budget.sqlite3']
CONFIGS=['books.json','cinematic-settings.json','cinematic-assets.json','remote.json','dependency-baseline.json','operations-receipts.json','reliability-history.json']

def tables(c):return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
def state():
 report={}
 for rel in DATABASES:
  p=BASE/rel
  if not p.is_file():report[rel]={'present':False};continue
  try:
   with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=10) as c:
    entry={'present':True,'integrity':c.execute('PRAGMA quick_check').fetchone()[0],'private_mode':not bool(p.stat().st_mode&0o077)}
    for table in ['jobs','full_jobs','publications','platform_posts']:
     if table in tables(c):entry[table]={r[0]:r[1] for r in c.execute('SELECT state,count(*) FROM '+table+' GROUP BY state')}
    if 'audience_observations' in tables(c):entry['audience_observations']=c.execute('SELECT count(*) FROM audience_observations').fetchone()[0]
    report[rel]=entry
  except sqlite3.Error:report[rel]={'present':True,'integrity':'Unable to read; inspect locally without sharing database contents.'}
 return report

def check(live=False):
 import app_version
 runtime=BASE.parent.parent/'work/kokoro-runtime/bin/python'
 config=json.loads((BASE/'cinematic-settings.json').read_text())
 credentials={}
 for rel in ['private-buffer/credentials.json','private-cloudinary/credentials.json','private-google/tokens.json']:
  p=BASE/rel;credentials[rel]={'present':p.is_file(),'private_mode':not bool(p.stat().st_mode&0o077) if p.exists() else None}
 import footage_director
 report={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_build':app_version.BUILD,'databases':state(),'disk_free_gib':round(shutil.disk_usage(BASE).free/1024**3,1),'ffmpeg':bool(shutil.which('ffmpeg')),'ffprobe':bool(shutil.which('ffprobe')),'kokoro_runtime':runtime.is_file(),'kokoro_models':(BASE.parent.parent/'work/kokoro-models').is_dir(),'approved_music':Path(config['music_path']).is_file(),'source_summary':Path.home()/'Documents'/'ContentEmpire-Studio'/'PRODUCTS'/'ebook_content.json'.is_file(),'credentials':credentials,'free_footage_key_present':bool(footage_director.key()),'provider_authentication_tested':False}
 # Discover the Google token filename without exposing content if it differs.
 report['google_config_files_present']=bool(list((BASE/'private-google').glob('*.json')))
 if live:
  try:
   with urllib.request.urlopen('http://127.0.0.1:8765/api/auth/status',timeout=5) as r:build=json.load(r).get('build')
   report['running_build']=build;report['restart_required']=build!=app_version.BUILD
  except Exception:report['running_build']='unreachable';report['restart_required']=True
 report['healthy']=all(d.get('integrity')=='ok' and d.get('private_mode') for d in report['databases'].values()) and all(report[k] for k in ['ffmpeg','ffprobe','kokoro_runtime','kokoro_models','approved_music','source_summary','free_footage_key_present']) and report['disk_free_gib']>=2
 return report

def backup(destination=None):
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 parent=Path(destination).expanduser().resolve() if destination else BASE/'backups'
 parent.mkdir(parents=True,exist_ok=True,mode=0o700);parent.chmod(0o700)
 out=parent/stamp;out.mkdir(mode=0o700)
 def target(rel):
  p=out/rel;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.parent.chmod(0o700);return p
 for rel in DATABASES:
  source=BASE/rel
  if not source.exists():continue
  p=target(rel)
  with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(p) as dst:src.backup(dst)
  p.chmod(0o600)
 for source in [*BASE.glob('*.py'),*BASE.glob('*.html'),*BASE.glob('*.command'),*BASE.glob('*.md'),*(BASE/name for name in CONFIGS),BASE/'.gitignore',*(BASE/'cinematic-scripts').glob('*.json')]:
  if source.is_file():p=target(source.relative_to(BASE));shutil.copyfile(source,p);p.chmod(0o600)
 # Tests are part of the maintained source, not disposable media intermediates.
 for source in [*(BASE/'tests').glob('*.py'),*(BASE/'generator').glob('*.py'),*(BASE/'docs').rglob('*.md')]:
  p=target(source.relative_to(BASE));shutil.copyfile(source,p);p.chmod(0o600)
 files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
 receipt={'created_at_utc':stamp,'scope':'state and source snapshot, NOT a complete media or credential backup','excluded':['private credential files','generated and original media','footage-cache','voice runtimes/models','original studio','historical provider JSON snapshots'],'consistency':'Each SQLite database is a valid online snapshot. Stop the app for a coordinated filesystem-and-all-databases recovery point.','sha256':files}
 p=out/'manifest.json';p.write_text(json.dumps(receipt,indent=2));p.chmod(0o600)
 return {'snapshot':str(out),'files':len(files),'scope':receipt['scope']}

def verify_snapshot(path):
 root=Path(path).resolve();manifest=json.loads((root/'manifest.json').read_text());bad=[]
 for rel,digest in manifest['sha256'].items():
  p=(root/rel).resolve()
  if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:bad.append(rel)
 return {'verified':not bad,'checked_files':len(manifest['sha256']),'mismatches':bad}

def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 c=sub.add_parser('check');c.add_argument('--live',action='store_true')
 b=sub.add_parser('backup');b.add_argument('--destination')
 v=sub.add_parser('verify-backup');v.add_argument('path')
 args=parser.parse_args();result=check(args.live) if args.command=='check' else backup(args.destination) if args.command=='backup' else verify_snapshot(args.path)
 print(json.dumps(result,indent=2));return 1 if result.get('verified') is False or result.get('healthy') is False else 0
if __name__=='__main__':raise SystemExit(main())
