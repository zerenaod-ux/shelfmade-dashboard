import unittest,tempfile,sys,subprocess,time,json
from pathlib import Path
from unittest.mock import patch
import render_capacity as capacity,jobs,full_jobs
class RenderCapacityTests(unittest.TestCase):
 def test_busy_slot_prevents_either_brand_consuming_attempts(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory);database=path/'state.db'
   with patch.object(jobs,'DB',database),patch.object(full_jobs,'DB',database),capacity.claim(path/'shared-render.lock') as acquired:
    self.assertTrue(acquired)
    with patch.object(jobs,'connect') as short,patch.object(full_jobs,'connect') as full:
     self.assertFalse(jobs.work_once());self.assertFalse(full_jobs.work_once());short.assert_not_called();full.assert_not_called()
 def test_separate_process_obeys_held_slot(self):
  with tempfile.TemporaryDirectory() as directory:
   lock=Path(directory)/'shared.lock';code='import render_capacity as r;from pathlib import Path\nwith r.claim(Path('+repr(str(lock))+')) as acquired:print(acquired)'
   with capacity.claim(lock):
    result=subprocess.run([sys.executable,'-c',code],cwd=capacity.BASE,capture_output=True,text=True,check=True);self.assertEqual(result.stdout.strip(),'False')
 def test_worker_keeps_slot_if_parent_exits(self):
  with tempfile.TemporaryDirectory() as directory:
   lock=Path(directory)/'shared.lock'
   code='import render_capacity as r,subprocess,sys,os\nfrom pathlib import Path\nwith r.claim(Path('+repr(str(lock))+')):\n p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(1)"],pass_fds=r.inherited_fds(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n print(p.pid,flush=True)\n os._exit(0)'
   subprocess.run([sys.executable,'-c',code],cwd=capacity.BASE,capture_output=True,text=True,check=True)
   with capacity.claim(lock) as acquired:self.assertFalse(acquired)
   deadline=time.monotonic()+3;released=False
   while time.monotonic()<deadline:
    with capacity.claim(lock) as acquired:
     if acquired:released=True;break
    time.sleep(.05)
   self.assertTrue(released)
