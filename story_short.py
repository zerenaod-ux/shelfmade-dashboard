"""MindLore STORY SHORTS: ~65-second vertical stories told in the strict storytelling style (story_rules.py): a claim about YOUR life, the surprising past/research, named real evidence,
the viewer's doubt answered, a loop ending. Writes scripts to story-shorts/mindlore/<id>.json; gh_story_short.py renders them with the 2D stick-man engine.
  python story_short.py <count>"""
import json, os, re, sys, random, hashlib, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
OUT = B / 'story-shorts' / 'mindlore'; HIST = B / 'data/mindlore/story-shorts.json'
THEMES = ['working hours and rest', 'sleep', 'attention and distraction', 'memory', 'stress and fear', 'friendship and group size', 'music and emotion', 'food and mood', 'loneliness', 'boredom', 'habits',
          'crowds and strangers', 'time in nature', 'laughter and play', 'anger', 'curiosity', 'gratitude', 'multitasking', 'social media comparison', 'decision fatigue', 'creativity', 'dreams', 'community and belonging',
          'storytelling', 'morning light and body clock', 'silence and noise', 'learning a language', 'walking and thinking', 'money and happiness', 'touch and hugs', 'smiling and mood', 'procrastination',
          'first impressions', 'jealousy', 'trust', 'kindness', 'nostalgia', 'risk and thrill', 'sharing food', 'handwriting vs typing']
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def hist(): return load(HIST, {'items': []})
def pick_theme(h):
    used = [i.get('theme') for i in h['items'][-30:]]
    cand = [t for t in THEMES if t not in used] or THEMES
    return random.choice(cand)
def one(llm_call):
    import story_rules
    h = hist(); theme = pick_theme(h); recent = [i['title'] for i in h['items'][-15:]]
    radar = ''
    try:
        r = load(B / 'data/radar/mindlore.json', {}); radar = '\nToday\'s winning pattern on YouTube (borrow the pattern, never the words): %s' % ((r.get('hook_patterns') or [''])[0])
    except Exception: pass
    base = ('You write a 60-70 second vertical Short for MindLore, a psychology channel about how your mind works, explained with real research and how people lived long ago.\nTHEME: %s.%s\n'
            'Titles already used, do not repeat: %s.\n' % (theme, radar, recent) + story_rules.rules('mindlore', short=True) +
            'Return JSON: {"public_title": "the hook or an everyday question, under 70 characters", "hook": "the exact first sentence of the narration", "thumb": "2-5 WORD CAPS HEADLINE", '
            '"narration": "150-190 words, first sentence EXACTLY the hook", "claims": [{"claim":"...","who":"...","year":"...","place":"..."}]}.')
    prompt = base; bad = ['no usable answer']; d = None
    for attempt in range(4):
        try: d = llm_call(prompt)
        except Exception as e: print('story_short: writer failed:', str(e)[:120], flush=True); continue
        if not isinstance(d, dict): continue
        nar = re.sub(r'\s+', ' ', str(d.get('narration', ''))).strip(); d['narration'] = nar; d['hook'] = str(d.get('hook', '')).strip()
        d['sections'] = [{'title': 'Story', 'narration': nar}]
        n = len(nar.split()); bad = []
        if not (140 <= n <= 200): bad.append('narration must be 150-190 words (now %d)' % n)
        if d['hook'] and not nar.startswith(d['hook']): bad.append('the narration must start with exactly the hook sentence')
        if re.search(r'[_#*]', nar): bad.append('no underscores, hashtags or stage directions')
        if not bad: bad = story_rules.check(d, 'mindlore', short=True)
        if not bad:
            v, rep = story_rules.verify_claims(d); bad = v; print('story_short: fact check:', '; '.join(rep), flush=True)
        if not bad: break
        print('story_short: attempt %d rejected: %s' % (attempt + 1, bad[:3]), flush=True)
        prompt = base + '\nYour last attempt failed these checks, fix them: ' + '; '.join(bad[:6])
    else:
        return None
    sid = 'st-%s-%s' % (datetime.date.today().strftime('%y%m%d'), hashlib.md5(d['hook'].encode()).hexdigest()[:5])
    out = {'book_id': sid, 'title': '', 'author': '', 'story_short': True, 'public_title': str(d.get('public_title') or d['hook'])[:95], 'hook': d['hook'], 'thumbnail_headline': str(d.get('thumb', ''))[:40].upper(),
           'sections': d['sections'], 'claims': d.get('claims', []), 'source_url': '', 'theme': theme}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / (sid + '.json')).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    h['items'].append({'id': sid, 'title': out['public_title'], 'theme': theme, 'date': datetime.date.today().isoformat()}); h['items'] = h['items'][-200:]
    HIST.parent.mkdir(parents=True, exist_ok=True); HIST.write_text(json.dumps(h, indent=1))
    print('story_short: wrote', sid, '-', out['public_title'], flush=True)
    return sid
def main(n):
    sys.path.insert(0, str(B))
    import ml_autoscripts as M
    made = 0
    for _ in range(n * 2):
        if made >= n: break
        if one(M._call): made += 1
    print('story_short: made', made); return made
if __name__ == '__main__':
    sys.exit(0 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 2) else 1)
