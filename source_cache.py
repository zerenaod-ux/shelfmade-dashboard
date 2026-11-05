"""Reuse original text already verified by a completed local ShelfMade draft."""
import json,sqlite3
from pathlib import Path

def read(book_id, database, generated_root):
 """Return a prior successful package's Gutenberg text, if its provenance fits."""
 database=Path(database);root=Path(generated_root)
 if not database.is_file():return None
 uri=database.resolve().as_uri()+'?mode=ro'
 try:
  with sqlite3.connect(uri,uri=True,timeout=5) as c:
   c.row_factory=sqlite3.Row
   rows=c.execute("SELECT id,attempts FROM jobs WHERE book=? AND state='ready' ORDER BY edition DESC,created DESC",(str(book_id),)).fetchall()
 except sqlite3.Error:return None
 expected='https://www.gutenberg.org/ebooks/'+str(book_id)
 for row in rows:
  folder=root/row['id']/str(max(1,int(row['attempts'] or 1)))
  source=folder/'source.txt';review=folder/'content-review.json'
  if source.is_symlink() or not source.is_file():continue
  if review.is_file():
   try:
    if json.loads(review.read_text()).get('source_url')!=expected:continue
   except (OSError,ValueError):continue
  text=source.read_text(encoding='utf-8-sig')
  if len(text)>2000:return text
 return None
