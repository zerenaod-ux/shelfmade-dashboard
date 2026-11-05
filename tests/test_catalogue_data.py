import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import catalogue_data,jobs
class Catalogue(unittest.TestCase):
 def test_valid_additions_reload_without_database_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'books.json';p.write_text(json.dumps([{'id':'1','title':'First','author':'Author'}]))
   with patch.object(jobs,'BASE',root),patch.object(jobs,'DB',root/'decisions.sqlite3'),patch.object(jobs,'BOOKS',[]):
    self.assertEqual(len(jobs.refresh_catalogue()),1);p.write_text(json.dumps([{'id':'1','title':'First','author':'Author'},{'id':'2','title':'Second','author':'Author'}]));self.assertEqual(len(jobs.refresh_catalogue()),2);self.assertFalse(jobs.DB.exists())
 def test_duplicate_or_missing_identity_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'books.json';row={'id':'1','title':'First','author':'Author'}
   for rows in ([row,row],[{'id':'1','title':'First'}],[]):
    p.write_text(json.dumps(rows))
    with self.assertRaises(ValueError):catalogue_data.load(p)
if __name__=='__main__':unittest.main()
