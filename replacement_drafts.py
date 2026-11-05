"""Separately saved replacement drafts; previously published files stay intact."""
import sqlite3
from pathlib import Path
BASE=Path(__file__).resolve().parent
DB=BASE/'decisions.sqlite3'
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS replacement_drafts(id TEXT PRIMARY KEY,book TEXT NOT NULL,folder TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP)')
 return c
def register(id,book,folder):
 folder=Path(folder).resolve()
 if not folder.is_relative_to(BASE/'replacements') or not (folder/'final.mp4').is_file():raise ValueError('Replacement draft is unavailable.')
 with connect() as c:c.execute('INSERT OR IGNORE INTO replacement_drafts(id,book,folder) VALUES(?,?,?)',(id,book,str(folder)))
def list_drafts():
 with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM replacement_drafts ORDER BY created DESC')]
