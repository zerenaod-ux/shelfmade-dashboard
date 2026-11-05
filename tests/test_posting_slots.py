import datetime,json,tempfile,unittest
from pathlib import Path
import posting_slots as ps
class T(unittest.TestCase):
 def cfg(self,d,enabled=True):
  p=Path(d)/'posting-slots.json';p.write_text(json.dumps({'enabled':enabled,'timezone':'America/Chicago','min_lead_minutes':10,'slots':{'tiktok':['20:00','21:30']}}));return p
 def test_off_by_default(self):
  with tempfile.TemporaryDirectory() as d:self.assertIsNone(ps.next_due(self.cfg(d,False),'tiktok'))
 def test_missing_file_is_none(self):self.assertIsNone(ps.next_due('/nonexistent/x.json','tiktok'))
 def test_next_slot_and_no_sharing(self):
  utc=datetime.timezone.utc
  now=datetime.datetime(2026,10,28,17,0,tzinfo=utc) # 12:00 Chicago (CDT)
  with tempfile.TemporaryDirectory() as d:
   p=self.cfg(d)
   a=ps.next_due(p,'tiktok',now,reserve=True);b=ps.next_due(p,'tiktok',now,reserve=True);c=ps.next_due(p,'tiktok',now,reserve=True)
   self.assertEqual(a,'2026-10-29T01:00:00.000Z') # 20:00 CDT
   self.assertEqual(b,'2026-10-29T02:30:00.000Z') # 21:30 CDT
   self.assertEqual(c,'2026-10-30T01:00:00.000Z') # next day 20:00
 def test_unknown_platform_none(self):
  with tempfile.TemporaryDirectory() as d:self.assertIsNone(ps.next_due(self.cfg(d),'youtube'))
if __name__=='__main__':unittest.main()
