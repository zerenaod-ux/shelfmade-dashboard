"""Doodles viral scan (owner 2026-11-23: copy the PATTERN of what goes viral: wording, opening, ending, situation; never the video).
Searches YouTube for recent Shorts that are going viral in our niche (funny relatable friend skits, awkward everyday moments, famous psychology ideas shown as skits),
asks the free LLM to describe the SHAPE (title wording, hook, ending, situation type), and writes data/doodles/viral_patterns.json.
doodles_engine/story_writer.py reads it as inspiration. Never fails the workflow; costs about 300-500 of the free 10,000 daily API units."""
import json, os, sys, datetime, urllib.request, urllib.parse
from pathlib import Path
import analytics as A
OUT = Path('data/doodles/viral_patterns.json')
QUERIES = ['funny awkward friends skit shorts', 'relatable everyday moment animated skit', 'best friends argue funny animation shorts', 'psychology effect explained funny skit shorts',
           'why do we do this funny animation shorts', 'couple banter animated shorts', 'dramatic petty argument funny shorts', 'cognitive bias funny example shorts']
def main():
    rt = os.environ.get('YT_REFRESH_TOKEN_DOODLES', '')
    if not rt: print('viral_scan: no token'); return
    tok = A.access(rt); day = datetime.date.today(); qs = [QUERIES[(day.toordinal() + k) % len(QUERIES)] for k in range(3)]
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=45)).strftime('%Y-%m-%dT00:00:00Z'); seen = {}
    for q in qs:
        u = 'https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode({'part': 'snippet', 'type': 'video', 'videoDuration': 'short', 'order': 'viewCount', 'publishedAfter': since,
                                                                                      'maxResults': 15, 'q': q, 'relevanceLanguage': 'en', 'regionCode': 'US'})
        for it in A.get(u, tok).get('items', []): seen[it['id']['videoId']] = {'title': it['snippet']['title'], 'channel': it['snippet']['channelTitle'], 'desc': it['snippet']['description'][:160]}
    ids = list(seen)[:50]
    if not ids: print('viral_scan: nothing found'); return
    st = A.get('https://www.googleapis.com/youtube/v3/videos?part=statistics,contentDetails&id=' + ','.join(ids), tok).get('items', [])
    rows = []
    for v in st:
        n = int(v['statistics'].get('viewCount', 0)); s = seen[v['id']]; s['views'] = n; rows.append(s)
    rows = sorted([r for r in rows if r['views'] >= 20000], key=lambda r: -r['views'])[:12]
    if not rows: print('viral_scan: no video above 20k views'); return
    import llm
    lst = '\n'.join('- "%s" (%d views) %s' % (r['title'], r['views'], r['desc'].replace('\n', ' ')) for r in rows)
    r = llm.json_call('You study viral short videos. Reply JSON only.', 'These Shorts are going viral right now:\n%s\n\nDescribe the reusable SHAPE, never copy any one video. Return {"title_shapes":["4-6 patterns of how the titles are worded, with a made-up example each"],"situations":["4-6 kinds of everyday situation that get watched, in plain words"],'
                      '"openings":["3-4 ways such videos open in the first 2 seconds"],"endings":["3-4 ways they end"]}' % lst, temperature=.4)
    if not r or not r.get('title_shapes'): print('viral_scan: no pattern returned'); return
    r.update(updated=day.isoformat(), based_on=[{'title': x['title'], 'views': x['views']} for x in rows]); OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(r, indent=1, ensure_ascii=False))
    print('viral_scan: saved patterns from %d videos' % len(rows))
if __name__ == '__main__':
    try: main()
    except Exception as e: print('viral_scan skipped:', str(e)[:200])
