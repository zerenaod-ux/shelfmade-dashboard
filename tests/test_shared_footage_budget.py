import unittest,tempfile,sqlite3,time
from pathlib import Path
from unittest.mock import patch
import footage_budget as budget
class SharedFootageTests(unittest.TestCase):
 def test_existing_brand_records_count_toward_combined_allowance(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);first=root/'shelf.db';second=root/'mind.db';shared=root/'shared.db'
   for path in (first,second):
    with sqlite3.connect(path) as c:c.execute('create table requests(at REAL)');c.executemany('insert into requests values (?)',[(time.time(),)]*75)
   with patch.object(budget,'SHELF',first),patch.object(budget,'MINDLORE',second),patch.object(budget,'SHARED',shared),sqlite3.connect(first) as c:
    with self.assertRaisesRegex(ValueError,'Shared free'):budget.reserve(c,first)
    self.assertEqual(c.execute('select count(*) from requests').fetchone()[0],75)
   with sqlite3.connect(second) as c:self.assertEqual(c.execute('select count(*) from requests').fetchone()[0],75)
 def test_new_attempt_is_persisted_once_without_resetting_old_rows(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'brand.db'
   with sqlite3.connect(path) as c:
    c.execute('create table requests(at REAL)');c.execute('insert into requests values (?)',(time.time()-4000,));c.commit();budget.reserve(c,path);self.assertEqual(c.execute('select count(*) from requests').fetchone()[0],2)
   with sqlite3.connect(path.parent/'shared-footage-budget.sqlite3') as c:self.assertEqual(c.execute('select count(*) from observed').fetchone()[0],1)
 def test_shelfmade_excludes_completed_mindlore_clips(self):
  import footage_director as f,json
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);shelf=root/'shelfmade-dashboard';shelf.mkdir();folder=root/'content-empire-studio/daily-generated/job';folder.mkdir(parents=True);(folder/'POST_THIS.txt').write_text('Complete');(folder/'footage-selection.json').write_text(json.dumps({'assets':[{'id':'pexels-901'}]}))
   with patch.object(f,'BASE',shelf),patch.object(f,'DB',shelf/'state.db'),patch.object(f,'CACHE',shelf/'cache'):self.assertIn('pexels-901',f.used_ids())
 def test_admission_waits_before_launching_when_allowance_is_low(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);first=root/'first.db';second=root/'second.db'
   for p,count in ((first,80),(second,50)):
    with sqlite3.connect(p) as c:c.execute('create table requests(at REAL)');c.executemany('insert into requests values (?)',[(time.time(),)]*count)
   with patch.object(budget,'SHELF',first),patch.object(budget,'MINDLORE',second),patch.object(budget,'SHARED',root/'shared.db'):
    self.assertFalse(budget.available());self.assertTrue(budget.available(20))
