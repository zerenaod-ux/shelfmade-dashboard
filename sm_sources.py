"""ShelfMade source supply: for books in books.json (owner's list) that have no retained original text yet, download the Project Gutenberg
plain text (runs on GitHub, which can reach gutenberg.org), sanity-check it, pin its sha256 in sources/shelfmade/catalogue.json.
Never posts or approves anything. Up to SM_SOURCES_PER_RUN books per run (default 10)."""
import json, os, re, hashlib, urllib.request, datetime
from pathlib import Path

B = Path(__file__).resolve().parent
SRC = B / 'sources' / 'shelfmade'
PER = int(os.environ.get('SM_SOURCES_PER_RUN', '10'))


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ShelfMade-source-check/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    books = json.load(open(B / 'books.json'))
    cat_path = SRC / 'catalogue.json'
    cat = json.load(open(cat_path))
    have = {e['id'] for e in cat}
    added = 0
    for b in books:
        bid = str(b['id'])
        if bid in have or added >= PER:
            continue
        url = 'https://www.gutenberg.org/cache/epub/%s/pg%s.txt' % (bid, bid)
        try:
            raw = fetch(url)
            txt = raw.decode('utf-8-sig', errors='replace')
        except Exception as e:
            print('skip', bid, 'download failed', str(e)[:80]); continue
        head = txt[:4000]
        if 'Project Gutenberg' not in head or len(txt) < 40000:
            print('skip', bid, 'not a normal full text'); continue
        lang = re.search(r'^Language:\s*(.+)$', head, re.M)
        if lang and 'English' not in lang.group(1):
            print('skip', bid, 'language', lang.group(1)); continue
        (SRC / ('%s.txt' % bid)).write_bytes(raw)
        cat.append({'id': bid, 'title': b['title'], 'author': b.get('author', ''), 'source_url': url,
                    'canonical_url': 'https://www.gutenberg.org/ebooks/%s' % bid, 'file': '%s.txt' % bid,
                    'sha256': hashlib.sha256(raw).hexdigest(), 'language': 'English', 'copyright': 'Public domain in the USA',
                    'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'candidate_sentences': len(re.findall(r'[.!?]\s', txt)),
                    'requires_owner_review': True})
        added += 1
        print('retained', bid, b['title'])
    cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False))
    print('added', added, 'of', len(books) - len(have), 'missing')


if __name__ == '__main__':
    main()
