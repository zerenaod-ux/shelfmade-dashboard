"""Business idea #1 (notes: business-ideas/01-gap-finder.md). Weekly: find things people say they need but cannot find.
Sources (public, free, no login): Hacker News comments (Algolia API) + Stack Exchange question excerpts. Reddit NOT used (restricted 2026).
Privacy: only short text snippets are kept (no usernames, no links to people). LLM groups snippets into topics and scores them.
Output: data/gaps/ranked.json (top topics, history kept) + data/gaps/latest.md. Never fails the workflow (always exits 0)."""
import json, re, sys, time, urllib.parse, urllib.request, gzip, datetime
from pathlib import Path
B = Path(__file__).parent; OUT = B / 'data/gaps'
PHRASES = ['I wish there was', "there's no good", "I can't find a", 'why is there no', 'does anyone know a tool', 'looking for a template', 'nobody makes', "wish someone would build"]
SE_SITES = ['diy', 'parenting', 'pets', 'money', 'fitness', 'cooking', 'travel', 'workplace', 'gardening', 'lifehacks', 'health', 'outdoors']
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
            d = get('https://hn.algolia.com/api/v1/search_by_date?query=%s&tags=comment&hitsPerPage=40&numericFilters=created_at_i>%d' % (urllib.parse.quote('"%s"' % ph), since))
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
                d = get('https://api.stackexchange.com/2.3/search/excerpts?order=desc&sort=creation&q=%s&site=%s&pagesize=15&fromdate=%d' % (urllib.parse.quote(ph), site, since))
                for it in d.get('items', []):
                    if it.get('item_type') == 'question' and it.get('answer_count', 1) <= 1: out.append({'src': 'se:' + site, 'text': clean(it.get('title'))[:200]})
            except Exception as e: print('se', site, str(e)[:80])
            time.sleep(.5)
    return out
def rank(items):
    import llm
    sample = items[:140]; lines = '\n'.join('%d. %s' % (i, s['text']) for i, s in enumerate(sample))
    sysm = 'You find unmet needs people would pay to have solved. Reply JSON only.'
    usr = ('Below are numbered public snippets where people say they wish something existed or cannot find it. Group them into at most 8 TOPICS (a topic = one concrete unmet need that a small faceless digital product could serve: a guide, template, tracker, tool, or video series). '
           'Ignore pure software-developer chatter unless a non-developer would pay. For each topic give: topic (max 12 words), who (the person), ids (snippet numbers), '
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
def main():
    since = int(time.time()) - 21 * 86400
    items = from_hn(since) + from_se(since)
    seen = set(); uniq = []
    for it in items:
        k = it['text'][:60].lower()
        if k not in seen: seen.add(k); uniq.append(it)
    print('snippets', len(items), 'unique', len(uniq))
    if len(uniq) < 15: print('too few snippets, skipping'); return
    top = rank(uniq)
    OUT.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    f = OUT / 'ranked.json'
    try: hist = json.loads(f.read_text())
    except Exception: hist = {'runs': []}
    hist['runs'] = (hist.get('runs', []) + [{'date': today, 'snippets': len(uniq), 'topics': top}])[-12:]
    f.write_text(json.dumps(hist, indent=1))
    md = ['# Gap-finder, %s (%d snippets)' % (today, len(uniq)), '']
    for t in top[:6]:
        md.append('- **%s** (score %s, %d mentions, solved %s/10%s) - for: %s. Test product: %s' % (t['topic'], t['score'], t['mentions'], t['solved'], ', HEALTH: organisation tools only' if t['health'] else '', t['who'], t['product']))
    (OUT / 'latest.md').write_text('\n'.join(md) + '\n'); print('\n'.join(md))
if __name__ == '__main__':
    try: main()
    except Exception as e: print('gap_finder skipped:', str(e)[:300])
