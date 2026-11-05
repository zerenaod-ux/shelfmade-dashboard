"""Append-only owner assessments with server-captured audience aggregate evidence.
No generation, publication, provider calls or experiment activation.
"""
import datetime,hashlib,json,sqlite3
from pathlib import Path
DB=Path(__file__).resolve().parent/'decisions.sqlite3'
PLATFORMS=('all','youtube','instagram','tiktok');FORMATS=('all','short','full','unknown')
VERSION='evidence-journal-v1'
POLICY='Saved aggregate observations, not a controlled experiment or causal winner. Provider, format and production style remain separate. No creative rule changes.'

def capture(audience,platform,fmt):
 if platform not in PLATFORMS or fmt not in FORMATS:raise ValueError('Choose a valid platform and video type.')
 if not isinstance(audience,dict) or not audience.get('available'):raise ValueError('Saved audience evidence is unavailable. Try again after checking local history.')
 # Copy the actual server cohort report; client-supplied measurements are never accepted.
 cohorts=[c for c in audience.get('cohorts',[]) if (platform=='all' or c.get('platform')==platform) and (fmt=='all' or c.get('format')==fmt)]
 return json.loads(json.dumps({'version':VERSION,'platform':platform,'format':fmt,'global_saved_observations':audience.get('saved_observations',0),'global_distinct_posts':audience.get('post_count',0),'cohorts':cohorts,'policy':POLICY},allow_nan=False))

def save(audience,platform,fmt,note):
 if not isinstance(note,str) or not 1<=len(note.strip())<=1000 or any(ord(c)<32 and c not in '\n\t' for c in note):raise ValueError('Write an assessment of 1–1000 characters without control characters.')
 evidence=capture(audience,platform,fmt);note=note.strip();payload=json.dumps(evidence,sort_keys=True,ensure_ascii=False,allow_nan=False)
 ident=hashlib.sha256(json.dumps([payload,note],ensure_ascii=False).encode()).hexdigest();created=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with sqlite3.connect(DB,timeout=20) as c:
  c.execute('CREATE TABLE IF NOT EXISTS evidence_journal(id TEXT PRIMARY KEY,created TEXT NOT NULL,note TEXT NOT NULL,evidence TEXT NOT NULL)')
  c.execute('INSERT OR IGNORE INTO evidence_journal VALUES(?,?,?,?)',(ident,created,note,payload))
 return ident

def snapshot():
 result={'available':True,'entries':[],'total':0,'limit':100,'policy':POLICY,'experiment_status':'The cover experiment is prepared, not activated. Review the October 16–22 reliability baseline first; saving evidence does not activate it.'}
 if not DB.is_file():return result
 with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True,timeout=20) as c:
  c.row_factory=sqlite3.Row
  if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence_journal'").fetchone():return result
  result['total']=c.execute('SELECT count(*) FROM evidence_journal').fetchone()[0]
  for row in c.execute('SELECT * FROM evidence_journal ORDER BY created DESC,id DESC LIMIT 100'):
   entry=dict(row);entry['evidence']=json.loads(entry['evidence']);result['entries'].append(entry)
 return result
