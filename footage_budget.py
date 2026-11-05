"""One conservative 150-attempt/hour allowance for the shared free footage connection.
Imports existing recent records, never resets brand ledgers or stores credentials.
"""
from pathlib import Path
import sqlite3,time
BASE=Path(__file__).resolve().parent
SHELF=BASE/'footage-history.sqlite3';MINDLORE=BASE.parent/'content-empire-studio/state/mindlore/rebuild-footage.sqlite3'
SHARED=BASE.parent/'content-empire-studio/state/shared-footage-budget.sqlite3'
def reserve(connection,database):
 database=Path(database).resolve();production=database in (SHELF.resolve(),MINDLORE.resolve());path=SHARED if production else database.parent/'shared-footage-budget.sqlite3';ledgers=(SHELF,MINDLORE) if production else (database,)
 if path.is_symlink():raise ValueError('Unsafe shared footage allowance path')
 path.parent.mkdir(parents=True,exist_ok=True);stamp=time.time();cutoff=stamp-3600
 with sqlite3.connect(path,timeout=20) as shared:
  shared.execute('create table if not exists observed(source TEXT,row_number INTEGER,at REAL,PRIMARY KEY(source,row_number,at))');shared.execute('create index if not exists observed_time on observed(at)');shared.execute('BEGIN IMMEDIATE')
  for ledger in ledgers:
   resolved=ledger.resolve()
   if resolved==database:rows=list(connection.execute('select rowid,at from requests where at>?',(cutoff,)))
   elif ledger.is_file():
    with sqlite3.connect(resolved.as_uri()+'?mode=ro',uri=True,timeout=2) as other:rows=list(other.execute('select rowid,at from requests where at>?',(cutoff,)))
   else:continue
   shared.executemany('insert or ignore into observed values(?,?,?)',[(str(resolved),r[0],r[1]) for r in rows])
  if shared.execute('select count(*) from observed where at>?',(cutoff,)).fetchone()[0]>=150:raise ValueError('Shared free footage hourly allowance reached; wait for capacity. Existing request records were preserved.')
  row=connection.execute('insert into requests values (?)',(stamp,));shared.execute('insert or ignore into observed values(?,?,?)',(str(database),row.lastrowid,stamp))
 path.chmod(0o600)

def available(required=30):
 """Read-only admission estimate; request-time reserve() remains authoritative."""
 cutoff=time.time()-3600;observed=set()
 try:
  if SHARED.is_file():
   with sqlite3.connect(SHARED.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as c:observed.update(tuple(r) for r in c.execute('select source,row_number,at from observed where at>?',(cutoff,)))
  for path in (SHELF,MINDLORE):
   if path.is_file():
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as c:observed.update((str(path.resolve()),r[0],r[1]) for r in c.execute('select rowid,at from requests where at>?',(cutoff,)))
 except sqlite3.Error:return False
 return 150-len(observed)>=required
