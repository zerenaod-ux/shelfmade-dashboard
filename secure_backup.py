"""Opt-in authenticated encrypted recovery export. No cloud upload or password storage.
CLI asks privately for a backup passphrase. Never pass it as a command argument.
"""
import argparse,datetime,getpass,hashlib,io,json,os,secrets,shutil,sqlite3,struct,tarfile,tempfile
from pathlib import Path,PurePosixPath
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import maintenance
BASE=Path(__file__).resolve().parent
MAGIC=b'SHELFMADE-RECOVERY-1\n';CHUNK=1024*1024
MEDIA=('generated','full-generated','replacements','footage-cache','generator')
PRIVATE=('private-buffer','private-cloudinary','private-google','private-footage')
def derive(password,salt):return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())
class EncryptWriter:
 def __init__(self,out,password):
  self.out=out;self.header=MAGIC+secrets.token_bytes(16)+secrets.token_bytes(8);out.write(self.header);self.aes=AESGCM(derive(password,self.header[len(MAGIC):len(MAGIC)+16]));self.counter=0;self.buffer=bytearray()
 def record(self,plain):
  counter=self.counter.to_bytes(4,'big');cipher=self.aes.encrypt(self.header[-8:]+counter,plain,self.header+counter);self.out.write(struct.pack('>I',len(cipher))+cipher);self.counter+=1
 def write(self,data):
  self.buffer.extend(data)
  while len(self.buffer)>=CHUNK:self.record(bytes(self.buffer[:CHUNK]));del self.buffer[:CHUNK]
  return len(data)
 def finish(self):
  if self.buffer:self.record(bytes(self.buffer));self.buffer.clear()
  self.record(b'') # Authenticated terminal record makes truncation detectable.
 def flush(self):self.out.flush()
def decrypt(source,target,password):
 with Path(source).open('rb') as stream,Path(target).open('xb') as out:
  os.chmod(target,0o600);header=stream.read(len(MAGIC)+24)
  if len(header)!=len(MAGIC)+24 or not header.startswith(MAGIC):raise ValueError('Not a ShelfMade recovery archive.')
  aes=AESGCM(derive(password,header[len(MAGIC):len(MAGIC)+16]));counter=0
  while True:
   raw=stream.read(4)
   if len(raw)!=4:raise ValueError('Archive is truncated.')
   size=struct.unpack('>I',raw)[0]
   if not 16<=size<=CHUNK+16:raise ValueError('Invalid encrypted record.')
   data=stream.read(size)
   if len(data)!=size:raise ValueError('Archive is truncated.')
   index=counter.to_bytes(4,'big');plain=aes.decrypt(header[-8:]+index,data,header+index);counter+=1
   if not plain:
    if stream.read(1):raise ValueError('Unexpected data after archive end.')
    break
   out.write(plain)
def files_under(root):
 if root.is_symlink():raise ValueError('Backup roots must not be symbolic links.')
 for folder,dirs,names in os.walk(root,followlinks=False):
  dirs[:]=[d for d in dirs if d!='.render' and not (Path(folder)/d).is_symlink()]
  for name in names:
   path=Path(folder)/name
   if path.is_file() and not path.is_symlink() and not name.endswith(('.part','.tmp')):yield path

def busy():
 path=BASE/'decisions.sqlite3'
 if not path.exists():return False
 with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
  tables=maintenance.tables(c)
  for table,states in [('jobs',('queued','running','retry_wait')),('full_jobs',('queued','running','retry_wait')),('platform_posts',('queued','hosting','submitting')),('publications',('uploading',))]:
   if table in tables and c.execute('SELECT 1 FROM '+table+' WHERE state IN ('+','.join('?' for _ in states)+')',states).fetchone():return True
 return False

def create(destination,password,include_media=False,include_credentials=False):
 if len(password)<16:raise ValueError('Use a backup passphrase of at least 16 characters. Keep it in your password manager.')
 destination=Path(destination).expanduser().resolve()
 if not destination.is_dir():raise ValueError('Choose an existing destination folder.')
 if destination.is_relative_to(BASE.resolve()):raise ValueError('Choose a destination outside the app folder.')
 if busy():raise ValueError('Wait for generation and uploads to finish before exporting a recovery backup.')
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');final=destination/('ShelfMade-'+stamp+'.smbackup');part=destination/(final.name+'.partial')
 # Temporary source snapshot is private and removed after encryption. Large media streams directly.
 with tempfile.TemporaryDirectory(prefix='shelfmade-backup-') as temp:
  root=Path(temp);snapshot=Path(maintenance.backup(root)['snapshot'])
  files={}
  for path in files_under(snapshot):
   if path.name!='manifest.json':files['app/'+path.relative_to(snapshot).as_posix()]=path
  if include_media:
   for name in MEDIA:
    if (BASE/name).exists():
     for path in files_under(BASE/name):files['app/'+path.relative_to(BASE).as_posix()]=path
  if include_credentials:
   for name in PRIVATE:
    if (BASE/name).exists():
     for path in files_under(BASE/name):
      if path.suffix not in ('.sqlite3',) and not path.name.endswith(('-wal','-shm')):files['app/'+path.relative_to(BASE).as_posix()]=path
  for name in ('buffer-history.json','youtube-connection.json'):
   if (BASE/name).is_file() and not (BASE/name).is_symlink():files['app/'+name]=BASE/name
  manifest={'format':1,'created_at':stamp,'includes_media':include_media,'includes_credentials':include_credentials,'excluded':['original ContentEmpire-Studio source/media outside app','Kokoro model files and voice/Python runtimes','approved music outside app','operating system and installed tools','temporary .render folders','symbolic links','earlier backup snapshots'],'consistency':'Per-database online snapshots and files. Stop ShelfMade for a coordinated cold copy.','files':{}}
  total=sum(p.stat().st_size for p in files.values())
  if shutil.disk_usage(destination).free<total+128*1024**2:raise ValueError('Destination does not have enough free space.')
  try:
   with part.open('xb') as out:
    part.chmod(0o600);writer=EncryptWriter(out,password)
    with tarfile.open(fileobj=writer,mode='w|') as archive:
     for name,path in sorted(files.items()):
      # Hash bytes actually streamed into the archive, not an earlier file read.
      info=archive.gettarinfo(str(path),arcname=name);info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o600
      class HashedReader:
       def __init__(self,stream):self.stream=stream;self.digest=hashlib.sha256()
       def read(self,size):data=self.stream.read(size);self.digest.update(data);return data
      with path.open('rb') as stream:
       reader=HashedReader(stream);archive.addfile(info,reader)
      manifest['files'][name]={'sha256':reader.digest.hexdigest(),'bytes':info.size}
     data=json.dumps(manifest).encode();info=tarfile.TarInfo('recovery-manifest.json');info.size=len(data);info.mode=0o600;archive.addfile(info,io.BytesIO(data))
    writer.finish();out.flush();os.fsync(out.fileno())
   part.rename(final)
  except BaseException:part.unlink(missing_ok=True);raise
 return {'archive':str(final),'files':len(files),'includes_media':include_media,'includes_credentials':include_credentials,'different_volume':destination.stat().st_dev!=BASE.stat().st_dev,'off_device_copy_verified':False,'scope_exclusions':manifest['excluded']}

def restore_check(archive,password,destination=None):
 """Decrypt and extract only into a disposable private folder; never replace live files."""
 with tempfile.TemporaryDirectory(prefix='shelfmade-restore-test-') as folder:
  root=Path(folder);plain=root/'archive.tar'
  if shutil.disk_usage(root).free<2*Path(archive).stat().st_size+128*1024**2:raise ValueError('Not enough temporary disk space for a verified restore.')
  try:decrypt(archive,plain,password)
  except Exception:raise ValueError('Cannot authenticate archive: check the passphrase, file integrity and completeness.') from None
  restored=root/'restore';restored.mkdir(mode=0o700)
  with tarfile.open(plain,'r:') as tar:
   members=tar.getmembers();names=set();expected_bytes=0
   for member in members:
    path=PurePosixPath(member.name)
    if member.name in names or path.is_absolute() or '..' in path.parts or not member.isfile() or not (member.name=='recovery-manifest.json' or member.name.startswith('app/')):raise ValueError('Unsafe archive path or member.')
    names.add(member.name);expected_bytes+=member.size
   if expected_bytes>shutil.disk_usage(root).free:raise ValueError('Not enough temporary space for the restore test.')
   for member in members:
    dest=restored/member.name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tar.extractfile(member) as src,dest.open('xb') as out:shutil.copyfileobj(src,out)
    dest.chmod(0o600)
  manifest=json.loads((restored/'recovery-manifest.json').read_text())
  if manifest.get('format')!=1 or set(manifest['files'])!=names-{'recovery-manifest.json'}:raise ValueError('Recovery manifest does not match archive contents.')
  databases=0
  for name,record in manifest['files'].items():
   path=restored/name
   with path.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
   if digest!=record['sha256'] or path.stat().st_size!=record['bytes']:raise ValueError('Restored file failed verification.')
   if path.suffix=='.sqlite3':
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
     if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Restored database failed verification.')
    databases+=1
  result={'verified':True,'files':len(manifest['files']),'databases':databases,'includes_media':manifest['includes_media'],'includes_credentials':manifest['includes_credentials'],'live_files_overwritten':False,'off_device_copy_verified':False,'scope_exclusions':manifest['excluded']}
  if destination is not None:
   destination=Path(destination).expanduser().resolve()
   if destination.exists() or not destination.parent.is_dir() or destination.is_relative_to(BASE.resolve()):raise ValueError('Restore only to a new folder outside the live app, inside an existing parent.')
   if shutil.disk_usage(destination.parent).free<Path(archive).stat().st_size+128*1024**2:raise ValueError('Restore destination does not have enough free space.')
   # The temporary copy has passed all hashes and database checks before any export.
   shutil.copytree(restored,destination)
   for directory,dirs,files in os.walk(destination):
    os.chmod(directory,0o700)
    for name in files:os.chmod(Path(directory)/name,0o600)
   result['restored_folder']=str(destination)
  return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
 create_parser=sub.add_parser('create');create_parser.add_argument('destination');create_parser.add_argument('--include-media',action='store_true');create_parser.add_argument('--include-credentials',action='store_true')
 verify=sub.add_parser('verify');verify.add_argument('archive')
 restore=sub.add_parser('restore');restore.add_argument('archive');restore.add_argument('destination')
 args=parser.parse_args();password=getpass.getpass('Backup passphrase (not stored): ')
 if args.action=='create':
  if password!=getpass.getpass('Confirm backup passphrase: '):raise ValueError('Passphrases do not match.')
  result=create(args.destination,password,args.include_media,args.include_credentials)
  result['restore_test']=restore_check(result['archive'],password)
 else:result=restore_check(args.archive,password,args.destination if args.action=='restore' else None)
 print(json.dumps(result,indent=2))
if __name__=='__main__':
 try:main()
 except (ValueError,OSError) as e:raise SystemExit(str(e))
