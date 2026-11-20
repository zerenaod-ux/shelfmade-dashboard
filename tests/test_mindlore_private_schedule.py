import unittest,datetime
from unittest.mock import patch
import mindlore_private_schedule as S
from full_release_slots import TZ
class PrivateScheduleTests(unittest.TestCase):
 def rows(self):
  return {vid:{'id':vid,'snippet':{'title':'Video '+vid,'channelId':S.Y.CHANNEL},'contentDetails':{'duration':'PT8M'},'status':{'privacyStatus':'private','uploadStatus':'processed'}} for vid in S.TARGETS}
 def test_nine_future_wednesday_saturday_slots(self):
  rows=self.rows();now=datetime.datetime(2026,11,19,21,tzinfo=TZ);result=S.plan(rows,now)
  self.assertEqual(len(result),9);self.assertTrue(all(x['state']=='planned' for x in result))
  times=[datetime.datetime.fromisoformat(x['local']) for x in result]
  self.assertEqual(str(times[0].date()),'2026-11-21');self.assertEqual(str(times[-1].date()),'2026-12-19')
  self.assertTrue(all(t.weekday() in (2,5) and t.hour==18 and t>now for t in times));self.assertEqual(len(set(times)),9)
 def test_existing_schedule_is_retained_and_blocks_its_day(self):
  rows=self.rows();rows[S.TARGETS[0]]['status']['publishAt']='2026-11-22T00:00:00Z'
  result=S.plan(rows,datetime.datetime(2026,11,19,21,tzinfo=TZ));self.assertEqual(result[0]['state'],'already_scheduled');self.assertIn('2026-11-26',result[1]['publishAt'])
 def test_wrong_channel_or_short_cannot_be_scheduled(self):
  for change in ('channel','duration'):
   rows=self.rows()
   if change=='channel':rows[S.TARGETS[0]]['snippet']['channelId']='other'
   else:rows[S.TARGETS[0]]['contentDetails']['duration']='PT48S'
   with self.assertRaises(ValueError):S.plan(rows,datetime.datetime.now(TZ))
 def test_public_or_unprocessed_upload_is_not_changed(self):
  rows=self.rows();rows[S.TARGETS[0]]['status']['privacyStatus']='public';rows[S.TARGETS[1]]['status']['uploadStatus']='failed'
  result=S.plan(rows,datetime.datetime.now(TZ));self.assertEqual([x['state'] for x in result[:2]],['held','held'])
