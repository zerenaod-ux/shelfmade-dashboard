"""Offline owner operations, authenticated encryption and disposable restore checks."""
import sys,tempfile,unittest,json,sqlite3,io,tarfile,secrets
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import operations as o,secure_backup as s,maintenance as m
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.app=self.root/'app';self.app.mkdir();self.out=self.root/'exports';self.out.mkdir();self.password=secrets.token_urlsafe(24)
  self.patches=[patch.object(s,'BASE',self.app),patch.object(m,'BASE',self.app),patch.object(o,'BASE',self.app),patch.object(o,'CACHE',None)]
  for p in self.patches:p.start()
  with sqlite3.connect(self.app/'decisions.sqlite3') as c:c.execute('CREATE TABLE jobs(id,state)');c.execute("INSERT INTO jobs VALUES('safe','ready')")
  (self.app/'server.py').write_text('print("test source")')
  (self.app/'private-google').mkdir();(self.app/'private-google/tokens.json').write_text('{"secret":"never-print-this"}')
  (self.app/'generated/example/.render').mkdir(parents=True);(self.app/'generated/example/final.mp4').write_bytes(b'finished media');(self.app/'generated/example/.render/work.mp4').write_bytes(b'rebuildable')
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def create(self,**kwargs):return s.create(self.out,self.password,**kwargs)
 def test_authenticated_roundtrip_with_media_and_credentials(self):
  result=self.create(include_media=True,include_credentials=True);archive=Path(result['archive']);self.assertEqual(archive.stat().st_mode&0o777,0o600)
  self.assertNotIn(b'never-print-this',archive.read_bytes());report=s.restore_check(archive,self.password)
  self.assertTrue(report['verified']);self.assertTrue(report['includes_media']);self.assertTrue(report['includes_credentials']);self.assertEqual(report['databases'],1);self.assertFalse(report['live_files_overwritten'])
 def test_explicit_restore_requires_new_folder_and_never_overwrites_live_app(self):
  result=self.create();destination=self.root/'restored'
  report=s.restore_check(result['archive'],self.password,destination)
  self.assertTrue((destination/'app/decisions.sqlite3').exists());self.assertEqual(destination.stat().st_mode&0o777,0o700)
  with self.assertRaises(ValueError):s.restore_check(result['archive'],self.password,destination)
  with self.assertRaises(ValueError):s.restore_check(result['archive'],self.password,self.app/'nested')
 def test_default_export_omits_media_and_credentials(self):
  result=self.create();plain=self.root/'plain.tar';s.decrypt(result['archive'],plain,self.password)
  with tarfile.open(plain) as tar:names=tar.getnames()
  self.assertNotIn('app/private-google/tokens.json',names);self.assertNotIn('app/generated/example/final.mp4',names)
 def test_render_scratch_and_links_are_excluded(self):
  (self.app/'generated/example/external').symlink_to(self.root/'outside');(self.root/'outside').write_text('must not export')
  result=self.create(include_media=True);plain=self.root/'plain.tar';s.decrypt(result['archive'],plain,self.password)
  with tarfile.open(plain) as tar:names=tar.getnames()
  self.assertFalse(any('.render' in n or n.endswith('/external') for n in names))
 def test_wrong_password_fails_without_live_changes(self):
  result=self.create()
  with self.assertRaises(ValueError):s.restore_check(result['archive'],'a different sufficiently long password')
  with sqlite3.connect(self.app/'decisions.sqlite3') as c:self.assertEqual(c.execute('SELECT state FROM jobs').fetchone()[0],'ready')
 def test_ciphertext_tampering_rejected(self):
  result=self.create();path=Path(result['archive']);data=bytearray(path.read_bytes());data[len(s.MAGIC)+30]^=1;path.write_bytes(data)
  with self.assertRaises(ValueError):s.restore_check(path,self.password)
 def test_authenticated_terminal_detects_truncation(self):
  result=self.create();path=Path(result['archive']);path.write_bytes(path.read_bytes()[:-20])
  with self.assertRaises(ValueError):s.restore_check(path,self.password)
 def test_extra_bytes_rejected(self):
  result=self.create();path=Path(result['archive']);path.write_bytes(path.read_bytes()+b'extra')
  with self.assertRaises(ValueError):s.restore_check(path,self.password)
 def test_stream_handles_multiple_encrypted_chunks(self):
  (self.app/'large.py').write_bytes(secrets.token_bytes(s.CHUNK*2+37));result=self.create();self.assertTrue(s.restore_check(result['archive'],self.password)['verified'])
 def test_busy_or_weak_password_or_app_destination_blocks_export(self):
  with self.assertRaises(ValueError):s.create(self.out,'short')
  with self.assertRaises(ValueError):s.create(self.app,self.password)
  with sqlite3.connect(self.app/'decisions.sqlite3') as c:c.execute("UPDATE jobs SET state='running'")
  with self.assertRaises(ValueError):self.create()
  self.assertEqual(list(self.out.iterdir()),[])
 def test_unsafe_archive_paths_rejected(self):
  path=self.out/'unsafe.smbackup'
  with path.open('wb') as out:
   writer=s.EncryptWriter(out,self.password)
   with tarfile.open(fileobj=writer,mode='w|') as tar:
    info=tarfile.TarInfo('../escape');info.size=3;tar.addfile(info,io.BytesIO(b'bad'))
   writer.finish()
  with self.assertRaisesRegex(ValueError,'Unsafe'):s.restore_check(path,self.password)
  self.assertFalse((self.root/'escape').exists())
 def test_operations_has_no_verified_billing_total_or_external_backup(self):
  snapshot=o.snapshot(force=True);self.assertFalse(snapshot['billing_verified']);self.assertIsNone(snapshot['monthly_total_usd']);self.assertIsNone(snapshot['encrypted_backup']);self.assertFalse(snapshot['automatic_deletion'])
  self.assertFalse(any('never-print-this' in json.dumps(service) for service in snapshot['services']))
 def test_storage_does_not_follow_symlinks(self):
  (self.app/'generated/external').symlink_to(self.app/'private-google',target_is_directory=True)
  measured=o.measure(self.app/'generated');self.assertEqual(measured['files'],2)
 def test_scope_manifest_mismatch_is_rejected(self):
  path=self.out/'bad-manifest.smbackup'
  with path.open('wb') as out:
   writer=s.EncryptWriter(out,self.password)
   with tarfile.open(fileobj=writer,mode='w|') as tar:
    data=json.dumps({'format':1,'files':{}}).encode();info=tarfile.TarInfo('recovery-manifest.json');info.size=len(data);tar.addfile(info,io.BytesIO(data));info=tarfile.TarInfo('app/extra.py');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
   writer.finish()
  with self.assertRaisesRegex(ValueError,'manifest'):s.restore_check(path,self.password)
if __name__=='__main__':unittest.main()
