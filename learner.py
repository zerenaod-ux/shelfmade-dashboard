"""Fast learning loop (GitHub, no Mac). Twice a week: reads data/analytics/<brand>.json, ranks videos by views PER DAY since publishing (so new and old compare fairly,
videos need only 3 days of age), asks Gemini what the winners share versus the losers, writes data/learned/<brand>.json. The writers read it via learned.guidance().
Small data is fine: it reads patterns (topic, hook, title style), not statistics, and the notes are refreshed every run so they follow what viewers do NOW."""
import datetime, json, os, re, sys, urllib.request, urllib.error
from pathlib import Path
A, OUT = Path('data/analytics'), Path('data/learned'); OUT.mkdir(parents=True, exist_ok=True)
KEY = os.environ.get('GEMINI_API_KEY', '').strip()
NOW = datetime.datetime.now(datetime.timezone.utc)
MINAGE, MINVIDS = 3, 6
BRIEF = {
    'mindlore': 'MindLore: psychology Shorts and longer videos from public-domain psychology books. Goal: the most watched, shared, binge-able videos.',
    'shelfmade': 'ShelfMade: Shorts and full videos built from public-domain books (quotes, lessons, summaries). Goal: the most watched, shared, binge-able videos.',
    'doodles': 'Animation Doodles: funny animated skits of Leo and Mia (best friends) explaining psychology ideas. Goal: the most watched, shared, binge-able videos; funnier and more creative is the main lever.'}


def secs(d):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0) if m else 0


def ask(prompt):
    """Uses the same model discovery + retries as the script writers (model names change, so Google is asked which ones exist)."""
    try:
        import ml_autoscripts as M
        return M._call(prompt)
    except Exception as e:
        print('  Gemini failed:', str(e)[:150])
        return None


def brand(b):
    d = json.loads((A / (b + '.json')).read_text())
    rows = []
    for v in d['videos']:
        if v.get('privacy') != 'public':
            continue
        age = (NOW - datetime.datetime.fromisoformat(v['published'].replace('Z', '+00:00'))).total_seconds() / 86400
        if age < MINAGE:
            continue
        rows.append(dict(title=v['title'], kind='short' if secs(v['duration']) <= 180 else 'full', vpd=round(v['views'] / max(age, 1), 2), views=v['views'], likes=v['likes'],
                         avgPercent=v.get('avgPercent'), days=round(age, 1)))
    if len(rows) < MINVIDS:
        return 'only %d usable videos (need %d): keep previous notes' % (len(rows), MINVIDS)
    rows.sort(key=lambda r: -r['vpd'])
    k = max(3, len(rows) // 4)
    top, low = rows[:k], rows[-k:]
    prompt = ('You are a short-form video growth analyst. Channel: %s\nTOP videos (views per day since publishing):\n%s\n\nBOTTOM videos:\n%s\n\n'
              'Find what the winners share that the losers lack (topic, angle, hook, title wording, length, emotion, format). Be concrete and honest; sample sizes are small, so give patterns, not statistics. '
              'Return ONLY JSON: {"do_more":[3-5 short concrete instructions for the script writer],"avoid":[2-4 short instructions],"title_style":"one sentence about hook/title wording that wins","next_tests":[2-3 experiments to try next week]}'
              ) % (BRIEF[b], json.dumps(top, indent=0), json.dumps(low, indent=0))
    j = ask(prompt)
    if not j:
        return 'Gemini unavailable: keep previous notes'
    j.update(updated=str(NOW.date()), n=len(rows), best_vpd=top[0]['vpd'], best_title=top[0]['title'])
    (OUT / (b + '.json')).write_text(json.dumps(j, indent=1))
    return 'learned from %d videos; best: %s (%.1f views/day)' % (len(rows), top[0]['title'][:50], top[0]['vpd'])


bad = []
for b in ('mindlore', 'shelfmade', 'doodles'):
    try:
        print(b, '->', brand(b))
    except Exception as e:
        bad.append('%s: %s' % (b, str(e)[:120]))
open('alert.md', 'w').write('\n'.join('- ' + x for x in bad))
sys.exit(1 if bad else 0)
