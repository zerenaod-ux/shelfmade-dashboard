import sys,tempfile,unittest,datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import buffer_api as b,multiplatform as m
class BudgetTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(b,'PRIVATE',Path(self.temp.name));self.patch.start()
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def fill(self,n):
  for _ in range(n):b.reserve_request()
 def test_analytics_leaves_capacity_for_publishing(self):
  self.fill(65)
  with self.assertRaises(b.BudgetError):b.reserve_request()
  ticket=b.reserve_publish(19)
  with b.allocated(ticket):
   for _ in range(19):b.reserve_request()
  status=b.budget_status();self.assertEqual(status['used'],84);self.assertEqual(status['reserved'],0)
 def test_whole_batch_rejected_before_start(self):
  self.fill(65);ticket=b.reserve_publish(19)
  with self.assertRaises(b.BudgetError):b.reserve_publish(19)
  b.release_publish(ticket);self.assertEqual(b.budget_status()['reserved'],0)
 def test_reservations_survive_other_connections(self):
  ticket=b.reserve_publish(19)
  with b.budget_db() as c:self.assertEqual(c.execute('SELECT remaining FROM budget_holds WHERE id=?',(ticket,)).fetchone()[0],19)
  with b.allocated(ticket):b.reserve_request();self.assertEqual(b.budget_status()['reserved'],18)
 def test_expired_reservation_releases_capacity(self):
  ticket=b.reserve_publish(19)
  with b.budget_db() as c:c.execute('UPDATE budget_holds SET expires=0 WHERE id=?',(ticket,))
  self.assertEqual(b.budget_status()['reserved'],0)
 def test_local_rejection_is_distinct_from_unknown_network_outcome(self):
  self.assertTrue(issubclass(b.BudgetError,b.NotSubmittedError))
if __name__=='__main__':unittest.main()
