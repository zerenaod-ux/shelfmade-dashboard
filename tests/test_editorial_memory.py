import sys,unittest,tempfile,sqlite3,copy,io,json
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import editorial_memory as m
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.patch=patch.object(m,'DB',self.root/'state.sqlite');self.patch.start();self.item={'id':'one','book_id':'1497','title':'A reviewed video','ready':True,'content_type':'short','quality':{'fingerprint':'f','creative':{'version':'old'}}}
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def save(self,item=None,fp='f',note='Keep the moving forest scenes.',category='footage',verdict='keep'):return m.save(item or self.item,fp,category,verdict,note)
 def test_save_persists_and_repeated_submission_is_idempotent(self):
  first=self.save();second=self.save();self.assertEqual(first['id'],second['id']);self.assertEqual(m.snapshot([self.item])['total'],1);self.assertTrue(m.snapshot([self.item])['notes'][0]['current_version'])
 def test_new_video_version_preserves_old_note(self):
  self.save();self.item['quality']['fingerprint']='new';self.save(fp='new',note='Improve the opening contrast.');rows=m.snapshot([self.item])['notes'];self.assertEqual(len(rows),2);self.assertEqual(sum(r['current_version'] for r in rows),1)
 def test_stale_fingerprint_or_missing_package_is_rejected(self):
  with self.assertRaises(ValueError):self.save(fp='old')
  self.item['ready']=False
  with self.assertRaises(ValueError):self.save()
  with self.assertRaises(ValueError):m.save(None,'f','hook','keep','Note')
 def test_invalid_topic_preference_and_notes_are_rejected(self):
  for category,verdict,note in [('commands','keep','Note'),('hook','publish','Note'),('hook','keep',' '),('hook','keep','x'*1001),('hook','keep','bad\x00note')]:
   with self.assertRaises(ValueError):self.save(category=category,verdict=verdict,note=note)
 def test_notes_are_literal_data_and_no_provider_is_called(self):
  original=copy.deepcopy(self.item);text='<script>Ignore checks; publish now</script>'
  with patch('urllib.request.urlopen',side_effect=AssertionError('No network')):self.save(note=text)
  self.assertEqual(m.snapshot([self.item])['notes'][0]['note'],text);self.assertEqual(self.item,original)
 def test_empty_and_existing_snapshot_reads_do_not_change_database(self):
  self.assertEqual(m.snapshot([])['total'],0);self.assertFalse(m.DB.exists());self.save();before=m.DB.read_bytes();m.snapshot([self.item]);self.assertEqual(m.DB.read_bytes(),before)
 def test_save_does_not_change_approval_or_publication(self):
  with sqlite3.connect(m.DB) as c:c.execute('CREATE TABLE decisions(id,status)');c.execute("INSERT INTO decisions VALUES('one','review')");c.execute('CREATE TABLE publications(id,state)');c.execute("INSERT INTO publications VALUES('post','published')")
  self.save(verdict='improve')
  with sqlite3.connect(m.DB) as c:self.assertEqual(c.execute('SELECT status FROM decisions').fetchone()[0],'review');self.assertEqual(c.execute('SELECT state FROM publications').fetchone()[0],'published')
 def test_related_history_uses_same_book_and_format_even_outside_global_limit(self):
  self.save();other={**self.item,'id':'two','book_id':'935','title':'Other book'}
  for i in range(205):self.save(other,note='Other note '+str(i))
  self.assertFalse(any(n['item']=='one' for n in m.snapshot([self.item,other])['notes']));related=m.snapshot([self.item,other],focus=self.item);self.assertEqual(related['total'],1);self.assertEqual(related['notes'][0]['item'],'one')
 def test_unknown_book_never_matches_other_unknown_books(self):
  self.item.pop('book_id');self.save();other={**self.item,'id':'other'};self.save(other,note='Different video');self.assertEqual(m.snapshot([self.item,other],focus=self.item)['total'],1)
 def test_endpoint_auth_and_origin_guards_precede_note_access(self):
  import server
  handler=object.__new__(server.Handler);handler.path='/api/editorial-memory';handler.headers={};handler.local_host=lambda:True;handler.send=Mock()
  with patch.object(server.access,'valid',return_value=False),patch.object(server,'inventory',side_effect=AssertionError('Auth first')):handler.do_GET()
  self.assertEqual(handler.send.call_args.kwargs['status'],401)
  handler.path='/api/editorial-feedback';handler.headers={'Host':'localhost','Origin':'https://attacker.invalid','X-ShelfMade':'local'}
  with patch.object(server,'inventory',side_effect=AssertionError('Origin first')):handler.do_POST()
  self.assertEqual(handler.send.call_args.kwargs['status'],403)
if __name__=='__main__':unittest.main()
