"""Owner editorial notes: append-only local memory, separate from review approval.
Notes are display data, never executable instructions or automatic generation rules.
"""
import sqlite3,datetime,hashlib,json
from pathlib import Path
DB=Path(__file__).resolve().parent/'decisions.sqlite3'
CATEGORIES=('hook','cover','voice','footage','subtitles','source')
VERDICTS=('keep','improve')

def connect():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row
 c.execute('''CREATE TABLE IF NOT EXISTS editorial_feedback(
 id TEXT PRIMARY KEY,item TEXT NOT NULL,fingerprint TEXT NOT NULL,book_id TEXT,
 format TEXT NOT NULL,title TEXT NOT NULL,creative_version TEXT NOT NULL,
 category TEXT NOT NULL,verdict TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL)''')
 c.execute('CREATE INDEX IF NOT EXISTS feedback_book_format ON editorial_feedback(book_id,format,created)')
 return c

def save(item,fingerprint,category,verdict,note):
 if not isinstance(item,dict) or not item.get('ready') or item.get('content_type') not in ('short','full'):raise ValueError('Open an available video before saving feedback.')
 current=(item.get('quality') or {}).get('fingerprint')
 if not current or current in ('missing','unknown') or fingerprint!=current:raise ValueError('The video version changed. Reopen it before saving feedback.')
 if category not in CATEGORIES or verdict not in VERDICTS:raise ValueError('Choose a feedback topic and Keep / Improve.')
 if not isinstance(note,str) or not 1<=len(note.strip())<=1000:raise ValueError('Write a note of 1–1000 characters.')
 if any(ord(c)<32 and c not in '\n\t' for c in note):raise ValueError('Remove control characters from the note.')
 note=note.strip();creative=(item.get('quality') or {}).get('creative') or {}
 version='+'.join(filter(None,[(creative.get('director') or {}).get('version') or creative.get('version'),creative.get('scene_direction_version')])) or 'unrecorded'
 ident=hashlib.sha256(json.dumps([item['id'],fingerprint,category,verdict,note],ensure_ascii=False).encode()).hexdigest()
 row=(ident,item['id'],fingerprint,str(item.get('book_id') or ''),item['content_type'],item['title'],version,category,verdict,note,datetime.datetime.now(datetime.timezone.utc).isoformat())
 with connect() as c:
  c.execute('INSERT OR IGNORE INTO editorial_feedback VALUES(?,?,?,?,?,?,?,?,?,?,?)',row)
  return dict(c.execute('SELECT * FROM editorial_feedback WHERE id=?',(ident,)).fetchone())

def snapshot(items,limit=200,focus=None):
 result={'available':True,'notes':[],'total':0,'categories':{},'shown_limit':limit,'policy':'Owner feedback only. Notes do not approve, rewrite, generate or publish videos and are not measured performance results.'}
 if not DB.exists():return result
 current={i['id']:i for i in items}
 with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=20) as c:
  c.row_factory=sqlite3.Row
  if 'editorial_feedback' not in {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}:return result
  where='';params=[]
  if focus:
   where=' WHERE item=?';params=[focus['id']]
   if focus.get('book_id'):where+=' OR (book_id=? AND format=?)';params.extend([str(focus['book_id']),focus['content_type']])
  result['total']=c.execute('SELECT count(*) FROM editorial_feedback'+where,params).fetchone()[0]
  for row in c.execute('SELECT category,verdict,count(*) AS n FROM editorial_feedback'+where+' GROUP BY category,verdict',params):result['categories'].setdefault(row['category'],{})[row['verdict']]=row['n']
  for row in c.execute('SELECT * FROM editorial_feedback'+where+' ORDER BY created DESC,id DESC LIMIT ?',[*params,limit]):
   entry=dict(row);item=current.get(entry['item']);entry['item_available']=bool(item);entry['current_version']=bool(item and (item.get('quality') or {}).get('fingerprint')==entry['fingerprint']);result['notes'].append(entry)
 return result
