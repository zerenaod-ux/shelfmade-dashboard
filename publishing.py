"""Durable publishing preparations. Never treats a local queue as a real upload."""
import sqlite3,json,uuid,hashlib
import captions
from pathlib import Path
BASE=Path(__file__).resolve().parent
DB=BASE/'decisions.sqlite3'
def connect():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,item TEXT NOT NULL,fingerprint TEXT NOT NULL,platform TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,state TEXT NOT NULL,url TEXT,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(item,fingerprint,platform))');claim_schema(c);return c

def claim_schema(c):
 c.execute('CREATE TABLE IF NOT EXISTS publishing_claims(platform TEXT,media_sha256 TEXT,owner TEXT,PRIMARY KEY(platform,media_sha256))')
def media_digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def claim(c,platform,digest,owner):
 """Called inside the submission transaction; identical bytes cannot switch route."""
 claim_schema(c)
 c.execute('INSERT OR IGNORE INTO publishing_claims VALUES(?,?,?)',(platform,digest,owner))
 return c.execute('SELECT owner FROM publishing_claims WHERE platform=? AND media_sha256=?',(platform,digest)).fetchone()[0]==owner

def connection_status():
 try:account=json.loads((BASE/'youtube-connection.json').read_text())
 except (OSError,ValueError):account={}
 return {'connected':bool(account.get('verified')),'channel':account.get('channel_name','Not connected'),'platform':'YouTube Shorts','mode':'Codex-assisted','dashboard_can_upload':False,'details':'Channel verified through Metricool. Independent dashboard upload requires a publishing API connection.'}

def public_row(row):
 keys=row.keys();data={k:row[k] for k in keys if k!='upload_session'}
 session=row['upload_session'] if 'upload_session' in keys else None
 error=row['error'] or ''
 # Only a known rejected authorization/setup request with no resumable session
 # can be retried safely. Ambiguous uploads remain locked for reconciliation.
 data['retry_safe']=row['state']=='failed' and not session and 'Google request failed (HTTP 400)' in error
 return data

def list_posts():
 with connect() as c:return [public_row(r) for r in c.execute('SELECT * FROM publications ORDER BY created DESC')]

def prepare(item,title,description,approved):
 if not approved:raise ValueError('Approve this video before preparing a YouTube upload.')
 if not item['quality']['can_approve']:raise ValueError('Resolve the quality warnings first.')
 if not isinstance(title,str) or not 1<=len(title.strip())<=100:raise ValueError('YouTube title must be between 1 and 100 characters.')
 if not isinstance(description,str) or len(description)>5000:raise ValueError('Description must be at most 5,000 characters.')
 description=captions.clean(description)
 if not description:raise ValueError('Write a public caption before preparing the upload.')
 if '<' in title or '>' in title or '<' in description or '>' in description:raise ValueError('Remove angle brackets from the title or description.')
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  fingerprint=item['quality']['fingerprint'];row=c.execute('SELECT * FROM publications WHERE item=? AND fingerprint=? AND platform=?',(item['id'],fingerprint,'youtube')).fetchone()
  if row:
   if not row['url'] and row['state'] in ('awaiting_publisher','awaiting_connection','failed'):
    c.execute('UPDATE publications SET title=?,description=? WHERE id=?',(title.strip(),description,row['id']))
    return public_row(c.execute('SELECT * FROM publications WHERE id=?',(row['id'],)).fetchone())
   return public_row(row)
  id=uuid.uuid4().hex;c.execute('INSERT INTO publications(id,item,fingerprint,platform,title,description,state,error) VALUES (?,?,?,?,?,?,?,?)',(id,item['id'],fingerprint,'youtube',title.strip(),description,'awaiting_publisher','Prepared. Select destinations in the publishing panel, or use the full-video YouTube queue.'))
  return public_row(c.execute('SELECT * FROM publications WHERE id=?',(id,)).fetchone())
