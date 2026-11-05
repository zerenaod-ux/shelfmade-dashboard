import sys,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import jobs,content_logic

class PassageEditions(unittest.TestCase):
 def test_old_one_job_per_book_table_migrates_without_losing_job(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'state.db'
   with sqlite3.connect(db) as c:
    c.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,book TEXT UNIQUE NOT NULL,state TEXT NOT NULL,attempts INTEGER DEFAULT 0,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP,worker_pid INTEGER)')
    c.execute("INSERT INTO jobs(id,book,state,attempts) VALUES ('legacy','1497','ready',1)")
    c.execute('CREATE TABLE attempts(job TEXT, started TEXT DEFAULT CURRENT_TIMESTAMP)')
   with patch.object(jobs,'DB',db),patch.object(jobs,'BOOKS',[{'id':'1497','title':'The Republic'}]),patch.object(jobs,'health',return_value={'ready':True,'missing':[]}),patch.object(jobs,'attempt_window',return_value=('2099-01-01','2100-01-01')):
    with jobs.connect() as c:
     old=c.execute("SELECT id,book,state,edition,worker_pid FROM jobs WHERE id='legacy'").fetchone()
     self.assertEqual(tuple(old),('legacy','1497','ready',1,None))
    second=jobs.enqueue('1497')
    again=jobs.enqueue('1497')
    self.assertEqual(second['edition'],2)
    self.assertEqual(second['id'],again['id'])
    with jobs.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM jobs WHERE book=?',('1497',)).fetchone()[0],2)

 def test_completed_editions_reserve_disjoint_source_passages(self):
  passages=[
   'You must learn to examine every belief before repeating it.',
   'Knowledge requires patient attention to the reasons behind each claim.',
   'The wise person learns when to question an easy answer.',
   'If you seek knowledge you must first examine your assumptions.',
   'Never accept a confident explanation without learning its reasons first.',
   'People learn wisdom by giving every question their careful attention.',
   'A careful reader must question every claim before accepting its truth.',
   'Your wisdom grows when you practice patient reflection on new knowledge.',
   'We must examine the evidence before judging the nature of this claim.',
   'A thoughtful person learns from experience by asking better questions.',
   'Knowledge changes when careful readers test their first conclusions.',
   'You should listen patiently before you decide what another person means.',
  ]
  book={'id':'1497','title':'The Republic','author':'Plato'}
  with patch('footage_director.brief',return_value={'keywords':['knowledge'],'theme':'learning','subject':'reader','queries':['reader learning']}):
   first,first_receipt=content_logic.build(book,' '.join(passages),edition=1)
   second,second_receipt=content_logic.build(book,' '.join(passages),edition=2,used_passages=first_receipt['source_sentences'])
  self.assertFalse(set(first_receipt['source_sentences']) & set(second_receipt['source_sentences']))
  self.assertEqual(first_receipt['edition'],1)
  self.assertEqual(second_receipt['edition'],2)
  self.assertGreaterEqual(first_receipt['edition_capacity'],2)
  self.assertGreaterEqual(second_receipt['edition_capacity'],2)

if __name__=='__main__':unittest.main()
