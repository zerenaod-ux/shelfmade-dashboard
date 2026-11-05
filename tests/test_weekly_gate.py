import sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import multiplatform as m, publishing
class GateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
  self.db=patch.object(m,'DB',self.base/'t.sqlite');self.db.start()
 def tearDown(self):self.db.stop();self.temp.cleanup()
 def add(self,id,state,path=None):
  with m.connect() as c:c.execute('INSERT INTO platform_posts(id,item,fingerprint,platform,title,description,state,path) VALUES(?,?,?,?,?,?,?,?)',(id,id,'f'+id,'tiktok','t','d',state,path))
 def test_off_never_holds(self):
  with patch.object(m,'scheduling_cfg',return_value=None):
   for i in range(12):self.add('s%d'%i,'scheduled')
   self.add('q','queued')
   with m.connect() as c:self.assertFalse(m.at_capacity(c,'q'))
 def test_on_holds_at_limit_and_releases(self):
  with patch.object(m,'scheduling_cfg',return_value={'buffer_queue_limit':9}):
   for i in range(9):self.add('s%d'%i,'scheduled')
   self.add('q','queued')
   with m.connect() as c:
    self.assertTrue(m.at_capacity(c,'q'))
    c.execute("UPDATE platform_posts SET state='published' WHERE id='s0'")
    self.assertFalse(m.at_capacity(c,'q'))
 def test_restart_keeps_waiting_only_when_on(self):
  self.add('q','queued',str(self.base/'v.mp4'))
  with patch.object(m,'scheduling_cfg',return_value={'x':1}):m.recover_interrupted()
  self.assertEqual([r['state'] for r in m.rows()],['queued'])
  with patch.object(m,'scheduling_cfg',return_value=None):m.recover_interrupted()
  self.assertEqual([r['state'] for r in m.rows()],['blocked'])
 def test_drain_sends_waiting_in_order(self):
  v=self.base/'v.mp4';v.write_bytes(b'x');self.add('q','queued',str(v))
  with patch.object(m,'scheduling_cfg',return_value={'x':1}),patch.object(m.threading,'Thread') as t:
   m.drain_waiting();self.assertTrue(t.called)
if __name__=='__main__':unittest.main()
