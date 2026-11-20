import unittest,datetime
from zoneinfo import ZoneInfo
from full_release_slots import next_release
TZ=ZoneInfo('America/Chicago')
class SlotsTests(unittest.TestCase):
 def test_twice_weekly_not_daily(self):
  now=datetime.datetime(2026,11,19,21,tzinfo=TZ);taken=set();days=[]
  for _ in range(9):
   d,stamp=next_release(taken,now=now);taken.add(d);days.append(d)
   self.assertIn(d.weekday(),(2,5));self.assertEqual(datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(TZ).hour,18)
  self.assertEqual(str(days[0]),'2026-11-21');self.assertTrue(all((b-a).days in (3,4) for a,b in zip(days,days[1:])))
 def test_reserved_day_is_skipped(self):
  d,_=next_release({datetime.date(2026,11,21)},now=datetime.datetime(2026,11,19,21,tzinfo=TZ));self.assertEqual(str(d),'2026-11-25')
 def test_thirty_minute_lead(self):
  d,_=next_release(set(),now=datetime.datetime(2026,11,21,17,40,tzinfo=TZ));self.assertEqual(str(d),'2026-11-25')
 def test_other_channels_keep_daily_slots(self):
  d,_=next_release(set(),kind='shfull',now=datetime.datetime(2026,11,19,21,tzinfo=TZ));self.assertEqual(str(d),'2026-11-20')
 def test_daylight_saving_uses_chicago_local_hour(self):
  for now in [datetime.datetime(2027,3,13,19,tzinfo=TZ),datetime.datetime(2027,11,6,19,tzinfo=TZ)]:
   _,stamp=next_release(set(),now=now);self.assertEqual(datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(TZ).hour,18)
