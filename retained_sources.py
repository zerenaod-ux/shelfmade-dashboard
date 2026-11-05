"""Pinned original texts for explicitly validated ShelfMade catalogue additions."""
from pathlib import Path
import json,hashlib,re
import os
ROOT=Path(__file__).resolve().parent/('sources/mindlore' if os.environ.get('BRAND')=='mindlore' else 'sources/shelfmade')
def read(ident):
 if not re.fullmatch('[1-9][0-9]*',str(ident)):raise ValueError('Invalid source ID')
 catalog=ROOT/'catalogue.json'
 if not catalog.exists():return None
 if ROOT.is_symlink() or catalog.is_symlink():raise ValueError('Unsafe retained source catalogue')
 entries=[e for e in json.loads(catalog.read_text()) if e.get('id')==str(ident)]
 if not entries:return None
 if len(entries)!=1:raise ValueError('Duplicate retained source identity')
 entry=entries[0];file=ROOT/(str(ident)+'.txt')
 if entry.get('file')!=file.name or entry.get('canonical_url')!='https://www.gutenberg.org/ebooks/'+str(ident) or entry.get('source_url')!='https://www.gutenberg.org/cache/epub/'+str(ident)+'/pg'+str(ident)+'.txt':raise ValueError('Retained source identity changed')
 if file.is_symlink() or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=entry.get('sha256'):raise ValueError('Retained original text changed or is missing. Restore the verified source before generation.')
 return file.read_text(encoding='utf-8-sig')
