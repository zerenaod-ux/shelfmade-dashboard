import unittest,tempfile,json,hashlib,subprocess
from pathlib import Path
from unittest.mock import patch,Mock
import media_runtime as m
class MediaRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.lib=self.root/'lib';self.lib.mkdir();self.receipt=self.root/'repair-receipt.json'
  for p in (patch.object(m,'LIB',self.lib),patch.object(m,'RECEIPT',self.receipt),patch.object(m,'CACHE',None),patch.object(m,'CHECKED',0)):p.start();self.addCleanup(p.stop)
 def install(self):
  (self.lib/'libx265.216.dylib').write_bytes(b'library');self.receipt.write_text(json.dumps({'sha256':hashlib.sha256(b'library').hexdigest()}))
 def test_environment_uses_exact_verified_library_without_duplicate_path(self):
  self.install()
  with patch.dict(m.os.environ,{'DYLD_LIBRARY_PATH':str(self.lib)}):self.assertEqual(m.environment()['DYLD_LIBRARY_PATH'],str(self.lib))
 def test_changed_library_blocks_health(self):
  self.install();(self.lib/'libx265.216.dylib').write_bytes(b'changed');self.assertFalse(m.health(force=True)['ready'])
 def test_broken_tool_stops_preflight(self):
  with patch.object(m.subprocess,'run',return_value=Mock(returncode=-6)):
   self.assertFalse(m.health(force=True)['ready'])
   with self.assertRaises(m.MediaRuntimeError):m.require_ready()
 def test_health_is_cached_to_avoid_running_tools_for_every_card(self):
  with patch.object(m.subprocess,'run',return_value=Mock(returncode=0)) as run:
   self.assertTrue(m.health()['ready']);self.assertTrue(m.health()['ready']);self.assertEqual(run.call_count,2)
 def test_footage_preflight_stops_before_creating_a_folder_or_contacting_provider(self):
  import footage_director as f
  with patch.object(m,'require_ready',side_effect=m.MediaRuntimeError('Video tools need repair')),patch.object(f.urllib.request,'urlopen') as network:
   with self.assertRaises(m.MediaRuntimeError):f.acquire({},self.root/'draft')
   network.assert_not_called();self.assertFalse((self.root/'draft').exists())
if __name__=='__main__':unittest.main()
