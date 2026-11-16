"""QUEUE_TITLES (owner 2026-11-15/16: the title rule must also cover videos already waiting in the queue). Rewrites the title of every approved item that has NOT been
handed to Buffer/YouTube yet so it follows title_rule (How/Why, 4-8 words, one emoji). The same video keeps ONE title on all platforms. Sent items are never touched.
Usage: python queue_titles.py [max titles per brand]  (needs the free LLM keys; without them only missing emojis are added)."""
import json, sys, time
from pathlib import Path
import title_rule
B = Path(__file__).resolve().parent
FILES = [('shelfmade', 'approved.json', 'state.json'), ('mindlore', 'approved-mindlore.json', 'state-mindlore.json'), ('doodles', 'approved-doodles.json', 'state-doodles.json'),
         ('shelfmade', 'approved-shfull.json', 'state-shfull.json'), ('mindlore', 'approved-mlfull.json', 'state-mlfull.json'), ('doodles', 'approved-ddfull.json', 'state-ddfull.json')]
def load(p, d):
    try: return json.loads(p.read_text())
    except (OSError, ValueError): return d
def main():
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    for brand, ap, st in FILES:
        p = B / 'publish' / ap; a = load(p, {'items': []}); done = load(B / 'publish' / st, {'done': {}}).get('done', {})
        new, n, changed = {}, 0, 0
        for i in a.get('items', []):
            if i.get('id') in done: continue
            old = i.get('title', '')
            if old not in new:
                if title_rule.ok(old, brand): new[old] = old
                elif n < cap:
                    n += 1; new[old] = title_rule.enforce(old, i.get('text') or i.get('description') or '', brand); time.sleep(3)
                else: new[old] = old
            t = new[old]
            if t != old and title_rule.ok(t, brand):
                i['title'] = t; changed += 1
                for f in ('text', 'description'):
                    if isinstance(i.get(f), str) and i[f].startswith(old): i[f] = t + i[f][len(old):]
        if changed: p.write_text(json.dumps(a, indent=1, ensure_ascii=False))
        left = sum(1 for i in a.get('items', []) if i.get('id') not in done and not title_rule.ok(i.get('title', ''), brand))
        print('%s %s: %d items retitled, %d still break the rule' % (brand, ap, changed, left), flush=True)
if __name__ == '__main__': main()
