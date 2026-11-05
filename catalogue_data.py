"""Validated local book catalogue data. No network or state writes."""
from pathlib import Path
import json,re
def load(path):
 path=Path(path)
 if path.is_symlink():raise ValueError('Unsafe book catalogue path')
 rows=json.loads(path.read_text());seen=set()
 if not isinstance(rows,list) or not rows:raise ValueError('Book catalogue is empty or invalid')
 for row in rows:
  if not isinstance(row,dict) or not re.fullmatch('[1-9][0-9]*',str(row.get('id',''))) or row['id'] in seen or not isinstance(row.get('title'),str) or not row['title'].strip() or not isinstance(row.get('author'),str) or not row['author'].strip():raise ValueError('Invalid or duplicate book catalogue entry')
  seen.add(row['id'])
 return rows
