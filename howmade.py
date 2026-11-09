"""HOW IT'S MADE (M1, weekly, GitHub, no Mac). For the top hits already found by viral.py, read each video's public captions and measure HOW it is built:
speaking pace, hook length, sentence length, question/number/'you' use, caption-line length. Writes numbers + an LLM 'recipe' (patterns only, never text or titles copied) to data/viral/<brand>-howmade.json.
Fail-soft: YouTube often blocks cloud IPs for captions; whatever is reachable is used, the rest is reported in 'skipped'. Read by learned.guidance() later (M3)."""
import json, re, sys, statistics, datetime
from pathlib import Path
OUT = Path('data/viral'); N = 12

def transcript(vid):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi as Y
        try: segs = Y().fetch(vid, languages=['en']).to_raw_data()
        except AttributeError: segs = Y.get_transcript(vid, languages=['en'])
        return segs
    except Exception as e:
        return str(e)[:80]

def stats(segs):
    text = ' '.join(s['text'].replace('\n', ' ') for s in segs); words = text.split(); dur = segs[-1]['start'] + segs[-1].get('duration', 2) - segs[0]['start']
    sents = [s for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()] or [text]
    first = sents[0].split()
    return {'wps': round(len(words) / max(1, dur), 2), 'secs': round(dur), 'hook_words': len(first), 'hook_is_question': first[-1:] and sents[0].strip().endswith('?'), 'avg_sentence_words': round(statistics.mean(len(s.split()) for s in sents), 1),
            'question_rate': round(sum(s.strip().endswith('?') for s in sents) / len(sents), 2), 'you_rate': round(len(re.findall(r'\b(you|your)\b', text, re.I)) / max(1, len(words)), 3),
            'numbers_per_100w': round(100 * len(re.findall(r'\d', text)) / max(1, len(words)), 1), 'caption_line_words': round(statistics.mean(len(s['text'].split()) for s in segs), 1), 'cuts_proxy_per_10s': round(10 * len(segs) / max(1, dur), 1)}

def main():
    for brand in ('mindlore', 'shelfmade', 'doodles'):
        lib = OUT / (brand + '-library.json')
        try: hits = json.loads(lib.read_text())['hits']
        except Exception: continue
        hits = sorted(hits, key=lambda h: h.get('breakout') or 0, reverse=True)[:N]; rows, skipped = [], []
        for h in hits:
            segs = transcript(h['id'])
            if isinstance(segs, str) or not segs: skipped.append(str(segs)[:60] if isinstance(segs, str) else 'empty'); continue
            try: r = stats(segs); r['views'] = h.get('views'); r['vpd'] = h.get('vpd'); rows.append(r)
            except Exception as e: skipped.append('stats ' + str(e)[:40])
        out = {'updated': datetime.date.today().isoformat(), 'brand': brand, 'tried': len(hits), 'read': len(rows), 'skipped': sorted(set(skipped))[:5]}
        if rows:
            for k in ('wps', 'hook_words', 'avg_sentence_words', 'question_rate', 'you_rate', 'numbers_per_100w', 'caption_line_words', 'cuts_proxy_per_10s'):
                vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
                if vals: out.setdefault('median', {})[k] = round(statistics.median(vals), 2)
            out['rows'] = rows
            try:
                import llm
                if llm.available():
                    rec = llm.json_call('You analyse short-video structure. Reply JSON only.', 'Brand: %s. Median structure numbers of %d top hits: %s. Write {"recipe":["5-7 short rules on pacing, hook, sentence length, caption rhythm, how to follow in OUR style (never copy anything)"]}' % (brand, len(rows), json.dumps(out['median'])), temperature=0.3)
                    if rec and rec.get('recipe'): out['recipe'] = rec['recipe'][:7]
            except Exception as e: out['recipe_error'] = str(e)[:80]
        (OUT / (brand + '-howmade.json')).write_text(json.dumps(out, indent=1)); print(brand, 'read', len(rows), 'of', len(hits), out.get('skipped'))

if __name__ == '__main__':
    main()
