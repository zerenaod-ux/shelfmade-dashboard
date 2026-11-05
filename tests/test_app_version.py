import importlib.util,tempfile,unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/'app_version.py'
class LoadedRevision(unittest.TestCase):
 def test_revision_changes_only_for_backend_source(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'app_version.py').write_bytes(SOURCE.read_bytes());(root/'server.py').write_text('first')
   spec=importlib.util.spec_from_file_location('fixture_version',root/'app_version.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   first=module.SOURCE_REVISION
   (root/'decisions.sqlite3').write_text('data');(root/'credentials.json').write_text('excluded');(root/'video.mp4').write_text('media')
   self.assertEqual(module.source_revision(),first)
   (root/'server.py').write_text('second')
   self.assertNotEqual(module.source_revision(),first)
   self.assertEqual(module.SOURCE_REVISION,first,'A running process must retain its loaded revision.')
 def test_generator_update_requires_activation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'app_version.py').write_bytes(SOURCE.read_bytes());(root/'generator').mkdir();p=root/'generator/render.py';p.write_text('first')
   spec=importlib.util.spec_from_file_location('fixture_generator_version',root/'app_version.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   p.write_text('second');self.assertNotEqual(module.SOURCE_REVISION,module.source_revision())
 def test_minddoodles_worker_update_requires_dashboard_activation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)/'outputs'/'shelfmade-dashboard';root.mkdir(parents=True)
   (root/'app_version.py').write_bytes(SOURCE.read_bytes());(root/'server.py').write_text('stable')
   worker=root.parent/'minddoodles-production'/'short_creator';worker.mkdir(parents=True)
   source=worker/'service.py';source.write_text('resume v1')
   spec=importlib.util.spec_from_file_location('fixture_worker_version',root/'app_version.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   first=module.SOURCE_REVISION;source.write_text('resume v2')
   self.assertNotEqual(module.source_revision(),first)
