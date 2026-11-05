import sys,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import multiplatform as m,buffer_api as b,publishing
class HealthTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
  self.patches=[patch.object(m,'BASE',self.base),patch.object(m,'DB',self.base/'db.sqlite'),patch.object(b,'PRIVATE',self.base),patch.object(publishing,'DB',self.base/'old.sqlite'),patch.object(m.cloudinary_host,'credentials',return_value={})]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def test_disconnected_account_is_not_green(self):
  channels=[{'id':id,'service':network,'name':'ShelfMade','isDisconnected':network=='instagram'} for network,id in m.EXPECTED.items()]
  (self.base/'channels.json').write_text(json.dumps({'channels':channels}))
  status=m.status();self.assertFalse(status['all_connected']);self.assertFalse(status['networks']['instagram']['connected']);self.assertTrue(status['networks']['youtube']['connected'])
 def add(self,id,error,state='needs_reconciliation'):
  with m.connect() as c:c.execute('INSERT INTO platform_posts(id,item,fingerprint,platform,title,description,state,error) VALUES(?,?,?,?,?,?,?,?)',(id,id,'fingerprint','tiktok','Walden','Caption',state,error))
 def test_only_proven_local_rejection_is_retryable(self):
  self.add('quota','Check Buffer before retrying: Daily Buffer request allowance reached. Try again tomorrow; existing posts remain safe.')
  self.add('unknown','Network timeout after sending.')
  m.reconcile_local();states={r['id']:r['state'] for r in m.rows()};self.assertEqual(states['quota'],'blocked');self.assertEqual(states['unknown'],'needs_reconciliation')
 def test_restart_does_not_misclassify_unsent_work(self):
  self.add('queued',None,'queued');self.add('submitting',None,'submitting');m.recover_interrupted()
  states={r['id']:r['state'] for r in m.rows()};self.assertEqual(states['queued'],'blocked');self.assertEqual(states['submitting'],'needs_reconciliation')
if __name__=='__main__':unittest.main()
