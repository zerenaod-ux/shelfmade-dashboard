"""Plan B footage source: Pixabay videos (free, commercial use OK, no attribution required). Used by footage_director.search ONLY when Pexels fails.
Maps Pixabay results to the Pexels-shaped dict the rest of the pipeline already understands. Pixabay rules: cache searches 24h (the director does), no mass downloads."""
import json, os, urllib.parse, urllib.request
from pathlib import Path

OFFSET = 9_000_000_000   # keeps Pixabay ids from colliding with Pexels ids in the clip cache


def key():
    k = os.environ.get('PIXABAY_API_KEY', '').strip()
    if k:
        return k
    p = Path(__file__).resolve().parent / 'private-footage' / 'pixabay-key'
    return p.read_text().strip() if p.is_file() else ''


def convert(data, page=1):
    vids = []
    for h in data.get('hits', []):
        files = []
        for q, v in (h.get('videos') or {}).items():
            if isinstance(v, dict) and v.get('url'):
                files.append({'link': v['url'], 'width': int(v.get('width') or 0), 'height': int(v.get('height') or 0), 'file_type': 'video/mp4', 'quality': q})
        if not files:
            continue
        vids.append({'id': OFFSET + int(h['id']), 'url': h.get('pageURL', ''), 'duration': h.get('duration', 0), 'video_files': files,
                     'source': 'pixabay', 'user': {'name': h.get('user', '')}})
    return {'videos': vids, 'source': 'pixabay', 'page': page, 'total_results': data.get('totalHits', 0)}


def search(query, page=1, per_page=80):
    k = key()
    if not k:
        raise ValueError('no Pixabay key')
    url = 'https://pixabay.com/api/videos/?' + urllib.parse.urlencode({'key': k, 'q': query[:100], 'per_page': per_page, 'page': page, 'safesearch': 'true'})
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ShelfMade/1.0'}), timeout=30) as r:
        return convert(json.load(r), page)
