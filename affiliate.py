"""Amazon Associates links for the video description (2026-11-05). Disclosure line is required by Amazon."""
import json, re, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parent
TAGS = {'shelfmade': 'shelfmade-20', 'mindlore': 'shelfmade-20'}   # change mindlore to its own tracking ID when created
DISCLOSE = 'As an Amazon Associate I earn from qualifying purchases.'
def _cfg():
    try: TAGS.update(json.loads((ROOT / 'affiliate-config.json').read_text()))
    except Exception: pass
def book_info(book_id):
    """(title, author) for a Gutenberg-style book id, else ('','')."""
    bid = re.sub(r'\D', '', str(book_id))
    try:
        for b in json.loads((ROOT / 'books.json').read_text()):
            if str(b.get('id')) == bid: return b.get('title', ''), b.get('author', '')
    except Exception: pass
    for d in ('cinematic-scripts', 'cinematic-scripts-mindlore'):
        try:
            j = json.loads((ROOT / d / (bid + '.json')).read_text()); return j.get('title', ''), j.get('author', '')
        except Exception: pass
    return '', ''
def link(title, author, brand='shelfmade'):
    _cfg(); tag = TAGS.get(brand, TAGS['shelfmade'])
    q = urllib.parse.quote_plus(('%s %s book' % (title, author)).strip())
    return 'https://www.amazon.com/s?k=%s&tag=%s' % (q, tag)
def block(book_id, brand='shelfmade'):
    t, a = book_info(book_id)
    if not t: return ''
    return '\n\nGet the book (%s%s): %s\n%s' % (t, ', ' + a if a else '', link(t, a, brand), DISCLOSE)
def add(desc, book_id, brand='shelfmade', limit=4900):
    if 'amazon.com/' in desc or 'tag=' in desc: return desc
    b = block(book_id, brand)
    return (desc[:limit - len(b)].rstrip() + b) if b else desc
