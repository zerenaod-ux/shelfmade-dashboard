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
    try:
        import llm
        return llm.json_call('You are a short-form video growth analyst. Reply with JSON only.', prompt, temperature=0.4)
    except Exception as e:
        print('  free fallback failed:', str(e)[:150])
        return None


def one(b, kind, rows):
    rows = [r for r in rows if r['kind'] == kind]
    if len(rows) < MINVIDS:
        return None, 'only %d %s videos (need %d)' % (len(rows), kind, MINVIDS)
    rows.sort(key=lambda r: -r['vpd'])
    k = max(3, len(rows) // 4)
    top, low = rows[:k], rows[-k:]
    prompt = ('You are a short-form video growth analyst. Channel: %s\nFormat being analysed: %s videos only.\nTOP videos (views per day since publishing):\n%s\n\nBOTTOM videos:\n%s\n\n'
              'Find what the winners share that the losers lack (topic, angle, hook, title wording, length, emotion, format; if a variant field exists, tight = about 30 s and standard = about 42 s, so say which length wins). Be concrete and honest; sample sizes are small, so give patterns, not statistics. '
              'Return ONLY JSON: {"do_more":[3-5 short concrete instructions for the script writer],"avoid":[2-4 short instructions],"title_style":"one sentence about hook/title wording that wins","next_tests":[2-3 experiments to try next week]}'
              ) % (BRIEF[b], 'Short (up to 3 minutes)' if kind == 'short' else 'full-length (over 3 minutes)', json.dumps(top, indent=0), json.dumps(low, indent=0))
    j = ask(prompt)
    if not j:
        return None, 'Gemini unavailable'
    j.update(n=len(rows), best_vpd=top[0]['vpd'], best_title=top[0]['title'])
    return j, 'learned from %d %s videos; best: %s (%.1f views/day)' % (len(rows), kind, top[0]['title'][:50], top[0]['vpd'])


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
    if b == 'doodles':    # length test: Shorts are written as 'tight' (~30 s) or 'standard' (~42 s); tag each video so the analysis can compare
        try:
            pool = {x['title'].strip().lower(): x.get('variant', 'standard') for x in json.loads(Path('data/doodles/story_pool.json').read_text())}
        except Exception:
            pool = {}
        for r in rows:
            r['variant'] = pool.get(r['title'].strip().lower(), 'standard')
    try:
        doc = json.loads((OUT / (b + '.json')).read_text())
        if 'short' not in doc and 'full' not in doc:
            doc = {}          # old single-notes format: replaced
    except Exception:
        doc = {}
    msgs = []
    for kind in ('short', 'full'):
        j, m = one(b, kind, rows)
        msgs.append(m)
        if j:
            doc[kind] = j
    doc['updated'] = str(NOW.date())
    if doc.get('short') or doc.get('full'):
        (OUT / (b + '.json')).write_text(json.dumps(doc, indent=1))
    return ' | '.join(msgs)


bad = []
for b in ('mindlore', 'shelfmade', 'doodles'):
    try:
        print(b, '->', brand(b))
    except Exception as e:
        bad.append('%s: %s' % (b, str(e)[:120]))
open('alert.md', 'w').write('\n'.join('- ' + x for x in bad))
sys.exit(1 if bad else 0)
