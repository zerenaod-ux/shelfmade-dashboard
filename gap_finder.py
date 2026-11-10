"""Business idea #1 (notes: business-ideas/01-gap-finder.md). Weekly: find things people say they need but cannot find.
Sources (public, free, no login): Hacker News comments (Algolia API) + Stack Exchange question excerpts. Reddit NOT used (restricted 2026).
Privacy: only short text snippets are kept (no usernames, no links to people). LLM groups snippets into topics and scores them.
Output: data/gaps/ranked.json (top topics, history kept) + data/gaps/latest.md. Never fails the workflow (always exits 0)."""
import json, re, sys, time, urllib.parse, urllib.request, gzip, datetime
from pathlib import Path
B = Path(__file__).parent; OUT = B / 'data/gaps'
PHRASES = ['I wish there was', "there's no good", "I can't find a", 'why is there no', 'does anyone know a tool', 'looking for a template', 'nobody makes', "wish someone would build"]
SE_SITES = ['diy', 'parenting', 'pets', 'money', 'fitness', 'cooking', 'travel', 'workplace', 'gardening', 'lifehacks', 'health', 'outdoors', 'law', 'academia', 'sustainability', 'woodworking', 'mechanics', 'beer', 'coffee', 'sports', 'hermeneutics', 'islam', 'judaism', 'rpg', 'writing', 'music', 'photo', 'crafts', 'diy.meta'][:-1]
LEMMY = ['https://lemmy.world', 'https://lemmy.ml', 'https://sh.itjust.works']
HEALTH = re.compile(r'\b(cancer|diagnos|medicat|prescri|dose|symptom|disease|disorder|suicid|therapy|pregnan|surgery|drug)\w*', re.I)
def get(url):
    r = urllib.request.Request(url, headers={'User-Agent': 'gap-finder/1 (research script)', 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(r, timeout=25) as x:
        raw = x.read()
        if x.headers.get('Content-Encoding') == 'gzip': raw = gzip.decompress(raw)
        return json.loads(raw)
def clean(t): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>|https?://\S+|&#?\w+;', ' ', t or '')).strip()
def snippet(t, ph):
    i = t.lower().find(ph.lower()); i = max(0, i - 60)
    return t[i:i + 260]
def from_hn(since):
    out = []
    for ph in PHRASES:
        try:
            d = get('https://hn.algolia.com/api/v1/search_by_date?query=%s&tags=comment&hitsPerPage=100&numericFilters=created_at_i>%d' % (urllib.parse.quote('"%s"' % ph), since))
            for h in d.get('hits', []):
                t = clean(h.get('comment_text'))
                if ph.lower() in t.lower(): out.append({'src': 'hn', 'text': snippet(t, ph)})
        except Exception as e: print('hn', ph, str(e)[:80])
        time.sleep(1)
    return out
def from_se(since):
    out = []
    for site in SE_SITES:
        for ph in ("is there a", "no good way to"):
            try:
                d = get('https://api.stackexchange.com/2.3/search/excerpts?order=desc&sort=creation&q=%s&site=%s&pagesize=25&fromdate=%d' % (urllib.parse.quote(ph), site, since))
                for it in d.get('items', []):
                    if it.get('item_type') == 'question' and it.get('answer_count', 1) <= 1: out.append({'src': 'se:' + site, 'text': clean(it.get('title'))[:200]})
            except Exception as e: print('se', site, str(e)[:80])
            time.sleep(.5)
    return out
def from_lemmy(since):
    out = []
    for inst in LEMMY:
        for ph in PHRASES[:5]:
            try:
                d = get('%s/api/v3/search?q=%s&type_=Comments&sort=New&limit=40' % (inst, urllib.parse.quote(ph)))
                for c in d.get('comments', []):
                    t = clean(c.get('comment', {}).get('content'))
                    if ph.lower() in t.lower(): out.append({'src': 'lemmy', 'text': snippet(t, ph)})
            except Exception as e: print('lemmy', inst, ph, str(e)[:80])
            time.sleep(1)
    return out
def rank(items):
    import llm
    import random; random.seed(1); sample = random.sample(items, min(len(items), 200)); lines = '\n'.join('%d. %s' % (i, s['text']) for i, s in enumerate(sample))
    sysm = 'You find unmet needs people would pay to have solved. Reply JSON only.'
    usr = ('Below are numbered public snippets where people say they wish something existed or cannot find it. Group them into at most 8 TOPICS (a topic = one concrete unmet need that a small faceless digital product could serve: a guide, template, tracker, tool, or video series). '
           'Prefer needs of ordinary people (home, family, money, pets, work, hobbies, health organisation) over developer or gadget talk; the who field must be a specific kind of person, never Anonymous. For each topic give: topic (max 12 words), who (the person), ids (snippet numbers), '
           'demand 1-10 (how many/how strongly), solved 1-10 (10 = good solutions already exist), product (cheapest test product, one line), health true/false (medical topic). '
           'JSON: {"topics":[{"topic":"","who":"","ids":[1],"demand":5,"solved":3,"product":"","health":false}]}\n\n' + lines)
    r = llm.json_call(sysm, usr)
    res = []
    for t in (r or {}).get('topics', []):
        try:
            ids = [int(i) for i in t.get('ids', []) if 0 <= int(i) < len(sample)]
            d, s = float(t.get('demand', 0)), float(t.get('solved', 5))
            res.append({'topic': str(t['topic'])[:100], 'who': str(t.get('who', ''))[:80], 'mentions': len(ids), 'demand': d, 'solved': s,
                        'score': round(d * 1.0 + len(ids) * .5 + (10 - s) * .8, 1), 'product': str(t.get('product', ''))[:140],
                        'health': bool(t.get('health')) or any(HEALTH.search(sample[i]['text']) for i in ids),
                        'examples': [sample[i]['text'][:160] for i in ids[:2]], 'sources': sorted({sample[i]['src'].split(':')[0] for i in ids})})
        except Exception: continue
    return sorted(res, key=lambda x: -x['score'])
def key(it): return re.sub(r'\W+', '', it['text'][:80].lower())
def load(f, d):
    try: return json.loads(f.read_text())
    except Exception: return d
def main(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    sf, pf = OUT / 'seen.json', OUT / 'pool.json'
    now = int(time.time()); old = {k: v for k, v in load(sf, {}).items() if now - v < 90 * 86400}; pool = load(pf, [])
    if mode in ('collect', 'both'):   # daily: quietly add NEW snippets to the pool (only last 4 days, or 60 on the very first run)
        since = now - (4 if old or pool else 60) * 86400
        hn, se, lm = from_hn(since), from_se(since), from_lemmy(since); print('by source: hn', len(hn), 'se', len(se), 'lemmy', len(lm))
        have = set(old) | {key(x) for x in pool}
        for it in hn + se + lm:
            if key(it) not in have: have.add(key(it)); pool.append(it)
        pf.write_text(json.dumps(pool)); print('pool now', len(pool))
        if mode == 'collect': return
    uniq = pool; items = pool
    print('snippets', len(items), 'unique', len(uniq))
    if len(uniq) < 15: print('too few NEW snippets, skipping (not marked as read)'); return
    top = rank(uniq)
    for it in uniq: old[key(it)] = now
    sf.write_text(json.dumps(old)); pf.write_text('[]')   # mark as read + empty the pool only after ranking worked
    try: prev = json.loads((OUT / 'ranked.json').read_text()).get('runs', [])
    except Exception: prev = []
    def words(s): return {w for w in re.findall(r'[a-z]{4,}', s.lower())}
    for t_ in top:   # recurrence: how many earlier runs had a similar topic (>=2 shared words) = the strong signal
        w = words(t_['topic']); t_['weeks_seen'] = 1 + sum(1 for r in prev if any(len(w & words(o['topic'])) >= 2 for o in r.get('topics', [])))
        t_['score'] = round(t_['score'] + 2 * (t_['weeks_seen'] - 1), 1)
    top.sort(key=lambda x: -x['score'])
    today = datetime.date.today().isoformat()
    f = OUT / 'ranked.json'
    try: hist = json.loads(f.read_text())
    except Exception: hist = {'runs': []}
    hist['runs'] = (hist.get('runs', []) + [{'date': today, 'snippets': len(uniq), 'topics': top}])[-12:]
    f.write_text(json.dumps(hist, indent=1))
    md = ['# Gap-finder, %s (%d snippets)' % (today, len(uniq)), '']
    for t in top[:6]:
        md.append('- **%s** (score %s, seen in %d run(s), %d mentions, solved %s/10%s) - for: %s. Test product: %s' % (t['topic'], t['score'], t['weeks_seen'], t['mentions'], t['solved'], ', HEALTH: organisation tools only' if t['health'] else '', t['who'], t['product']))
    (OUT / 'latest.md').write_text('\n'.join(md) + '\n'); print('\n'.join(md))
if __name__ == '__main__':
    try: main(sys.argv[1] if len(sys.argv) > 1 else 'both')
    except Exception as e: print('gap_finder skipped:', str(e)[:300])
