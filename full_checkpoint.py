"""Verified generation checkpoints. Never restores approvals or publication receipts."""
import hashlib,json,re,shutil,time
from pathlib import Path
VERSION='full-checkpoints-v1'

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_hash(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
def write(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
def stage(folder,name,message):write(Path(folder)/'production-progress.json',{'version':VERSION,'stage':name,'message':message,'updated':time.time(),'review_required':True})
def records(folder):
 try:
  data=json.loads((Path(folder)/'.render/checkpoints.json').read_text())
  return data if isinstance(data,dict) else {}
 except (OSError,ValueError):return {}
def allowed(name):return bool(re.fullmatch(r'\.render/(chapter_[0-9]+(?:\.(wav|mp4)|-timing\.json)|chapters\.json|word-timing\.json|audio\.txt)',name))
def checked_file(folder,name,sha):
 p=Path(folder)/name
 return allowed(name) and not p.is_symlink() and p.is_file() and p.resolve().is_relative_to(Path(folder).resolve()) and file_hash(p)==sha

def seal(folder,name,identity,paths):
 folder=Path(folder);files={str(Path(p).relative_to(folder)):file_hash(p) for p in paths}
 if not files or not all(allowed(p) for p in files):raise ValueError('Unsupported generation checkpoint file')
 data=records(folder);data[name]={'identity':identity,'files':files};write(folder/'.render/checkpoints.json',data)
def valid(folder,name,identity):
 record=records(folder).get(name,{})
 return bool(isinstance(record,dict) and isinstance(record.get('files'),dict) and record.get('identity')==identity and record.get('files') and all(checked_file(folder,p,sha) for p,sha in record['files'].items()))
def restore(source,target,voice_identity):
 """Only exact, hash-checked intermediate media; originals remain unchanged."""
 source=Path(source);target=Path(target)
 if source.is_symlink() or not source.is_dir():return []
 data=records(source);restored=[]
 # A changed script/voice invalidates the whole continuation, including chapter encodes.
 if not valid(source,'voice',voice_identity) and not any(name.startswith('narration-') and valid(source,name,voice_identity) for name in data):return restored
 for name,record in data.items():
  if not isinstance(record,dict) or not isinstance(record.get('files'),dict):continue
  if name!='voice' and not re.fullmatch('(chapter|narration)-[0-9]+',name):continue
  if name.startswith('narration-') and record.get('identity')!=voice_identity:continue
  if not record.get('files') or not all(checked_file(source,p,sha) for p,sha in record['files'].items()):continue
  for relative in record['files']:
   out=target/relative;out.parent.mkdir(parents=True,exist_ok=True)
   if out.exists():
    if out.is_symlink() or file_hash(out)!=record['files'][relative]:raise ValueError('Recovery target already contains different media; original preserved')
   else:shutil.copy2(source/relative,out)
  current=records(target);current[name]=record;write(target/'.render/checkpoints.json',current);restored.append(name)
 return restored
