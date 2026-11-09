"""G4 (owner OK Nov 9): clone winners. A YouTube video with views >= max(30, 3 x the channel median) gets 3 related follow-up ideas queued.
Doodles -> data/doodles/comment_ideas.json (used first by the story writer). MindLore/ShelfMade -> data/winner-ideas-<brand>.json (used first by story_short.pick_theme).
Each winner is cloned once (data/growth/cloned.json). Never fails the workflow."""
import json, re, statistics, sys
from pathlib import Path
B = Path(__file__).parent
def jl(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def ideas(brand, title):
    try:
        import llm
        if llm.available():
            r = llm.json_call('You help a short-video channel. Reply JSON only.', 'Our %s video "%s" is doing unusually well. Give 3 follow-up video topics that keep the SAME appeal (same feeling, same kind of relatable situation) but are clearly new, each under 12 words, plain ASCII. Return {"ideas":["...","...","..."]}' % (brand, title), temperature=.8)
            out = [str(x)[:90] for x in (r or {}).get('ideas', []) if x][:3]
            if out: return out
    except Exception as e: print('llm ideas failed:', str(e)[:120])
    return ['A follow-up to "%s": same idea, new everyday situation' % title, 'The other side of "%s"' % title, 'What most people get wrong about "%s"' % title]
def main():
    done = jl(B / 'data/growth/cloned.json', []); made = 0
    for brand in ('doodles', 'mindlore'):   # ShelfMade themes are books (picked from books.json), not cloned
        vs = [v for v in jl(B / ('data/analytics/%s.json' % brand), {}).get('videos', []) if v.get('privacy', 'public') == 'public']
        if len(vs) < 8: continue
        med = statistics.median(v.get('views', 0) for v in vs); bar = max(50, 3 * med); got = 0
        for v in sorted(vs, key=lambda x: -x.get('views', 0)):
            if v.get('views', 0) < bar or v['id'] in done or got >= 2: continue   # at most 2 clones per brand per run
            got += 1; new = ideas(brand, re.sub(r'[^\x20-\x7e]', '', v['title']).strip())
            if brand == 'doodles': f = B / 'data/doodles/comment_ideas.json'
            else: f = B / ('data/winner-ideas-%s.json' % brand)
            q = jl(f, []); q += new; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(q, indent=1))
            done.append(v['id']); made += 1; print('winner', brand, v['title'], v['views'], '(median %.0f) ->' % med, new)
    (B / 'data/growth').mkdir(parents=True, exist_ok=True); (B / 'data/growth/cloned.json').write_text(json.dumps(done, indent=1)); print('winners cloned:', made)
if __name__ == '__main__':
    try: main()
    except Exception as e: print('winner_clone skipped:', str(e)[:200])
