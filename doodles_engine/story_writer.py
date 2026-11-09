"""Writes new AnimationDoodles stories (free Gemini key from data/secrets.json) into data/doodles/story_pool.json.
Run: <img-lab python> story_writer.py [N]   - adds N new stories (default 3). Uses only the standard library."""
import json,re,sys,time,urllib.request,urllib.error
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;POOL=ROOT/'data/doodles/story_pool.json'
sys.path.insert(0,str(HERE));import stories
TOPICS=["rehearsing a phone call in your head five times (rumination and the spotlight feeling)","the Sunday scaries (anticipatory anxiety)","replying 'k' because a long text feels like too much (avoidance)","nodding in a meeting you did not understand (pluralistic ignorance)","replaying a cringe memory at 2 AM (rumination)","cleaning the whole room instead of starting the task (avoidance as emotion relief)","checking your phone for nothing (variable rewards)","doomscrolling the bad news (negativity bias)","feeling everyone else is doing better (social comparison)","saying yes to everything then resenting it (people-pleasing)","resting feels guilty (productivity guilt)","AI is taking my job panic (catastrophizing, told gently)","being an introvert at a party (social battery)","overreacting to a short text (mind reading)","starting a hobby then quitting at the first mistake (all-or-nothing thinking)","waiting for motivation before starting (motivation follows action)","anchoring bias","loss aversion","the endowment effect","hindsight bias","decision fatigue","the IKEA effect","the bystander effect","the halo effect",
"the availability heuristic","the mere-exposure effect","social proof","hedonic adaptation","confirmation bias","the Dunning-Kruger effect (told softly)","temporal discounting (now vs later)",
"the Baader-Meinhof illusion","the sunk-cost of finishing a bad book","analysis paralysis","the illusion of transparency","imposter feelings","the contrast effect","the peak-end rule",
"habit stacking","the two-minute rule","the Pomodoro idea","the fresh-start effect","the Ovsiankina urge to finish","the framing effect","the false-consensus effect","the pratfall effect","rubber-duck thinking","the curse of knowledge"]
RULES="""You write 40-second animated explainer scripts starring LEO (anxious overthinker, yellow hoodie) and MIA (dry, kind, blunt, teal sweater). Pop-psychology idea, soft claims ('can', 'often'), no invented statistics, no real studies named with numbers.
Return ONE JSON object: {"id":"kebab-slug","title":"The ...","concept":"UPPERCASE NAME","mood":"one of curious|warm|mysterious|reflective|dramatic|calm - pick by the emotional feel of THIS story (mysterious for hidden/unconscious things, reflective for time/regret/memory, dramatic for stress/pressure/conflict, warm for kindness/relationships, calm for gentle/soothing, curious only for pure how-and-why puzzles)","insight":"one-line takeaway (max 70 chars)","caption":"1-2 sentence hook for social media",
"explain_shot":3,"shots":[ exactly 6 of {"scene":"...","focus":"both|leo|mia","lines":[{"who":"leo|mia","feel":"confident|deadpan|sheepish|panicked|warm|tired|excited|hopeful|amused|anxious","text":"..."}]} ]}
STRUCTURE (five beats, escalating mini-skit, NOT a lecture): shot 1 HOOK starts mid-conflict with no introduction; shot 2 SETUP in one beat then Leo's overthinking visibly makes it WORSE; shot 3 ESCALATION raises the stakes and the funny; shot 4 PAYOFF: Mia's blunt reversal NAMES the concept plainly only now, with a one-line explanation; shot 5 a relatable practical tip Leo can actually try; shot 6 LOOP: ONE line only, and it is the LAST line of the whole video: a question or an unfinished thought that the very FIRST line of shot 1 naturally ANSWERS or COMPLETES, so when the Short replays it continues seamlessly like one endless conversation. No sign-off, no moral, no tip, no 'follow', no ending text as the last line. Whole video 74 to 88 spoken words in total (40 to 48 seconds, NEVER more than 50). Pick explain_shot=3 (the 0-based index of the payoff shot). Original everyday scenarios, relatable work and social-life moments, never lecture-like. Shot rules: 1-2 lines per shot, each line 4-14 words, funny and relatable, shot 1 is a HOOK: its FIRST line is 8 words or fewer, starts instantly with a bold relatable claim, confession, question or myth-buster about the idea (never a greeting, never 'Did you know', never the concept name), and the concept is NOT named until the payoff shot; the first line must read as the natural answer to the last line of the video; the payoff shot (explain_shot, 0-based index 3) names the concept plainly and explains it; the practical tip is one short line in shot 5; the last shot is the loop callback.
SCENE rules (very important, pictures are AI-made): describe an everyday setting + props + body language. Both characters must be visible, FACING THE CAMERA, standing or sitting upright. Faces never hidden by hands, props or hair. Describe closed-mouth expressions only (worried eyes, smirk, raised eyebrow) - NEVER shouting, screaming, laughing with open mouth or anything with teeth. No text, signs, screens with writing or logos in the scene. Max 30 words per scene."""
def secret():
    return json.loads((ROOT/'data/secrets.json').read_text())['GEMINI_API_KEY']
_MODELS=[]
def models():
    """Model names change, so ask Google which text models this key can use (newest flash first); fall back to the old list."""
    if _MODELS:return _MODELS
    try:
        req=urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=200',headers={'x-goog-api-key':secret()})
        ms=json.load(urllib.request.urlopen(req,timeout=60)).get('models',[])
        ok=[m['name'].split('/')[-1] for m in ms if 'generateContent' in m.get('supportedGenerationMethods',[])]
        ok=[m for m in ok if m.startswith('gemini') and not re.search(r'image|tts|audio|live|embed|vision|robotics|computer|thinking|preview|exp',m)]
        ver=lambda m:float((re.findall(r'\d+(?:\.\d+)?',m) or ['0'])[0])
        flash=sorted([m for m in ok if re.search(r'flash(?!-lite)',m)],key=lambda m:-ver(m));lite=sorted([m for m in ok if 'lite' in m],key=lambda m:-ver(m))
        _MODELS.extend(flash[1:]+flash[:1]+lite+[m for m in ok if m not in flash and m not in lite])
    except Exception as e:print('model list failed:',str(e)[:80])
    if not _MODELS:_MODELS.extend(['gemini-2.5-flash','gemini-2.5-flash-lite','gemini-2.0-flash','gemini-flash-latest','gemini-flash-lite-latest','gemma-3-27b-it','gemma-3-12b-it'])
    print('story models:',_MODELS[:5],flush=True);return _MODELS
KIND='short'   # episode_writer switches this to 'full' while it writes an episode
ACTION = ("ACTION AND SOUND: in EVERY shot's 'scene' text describe one clear physical action in plain words, so the animation moves and real sounds can be added from the words. "
          "Use these everyday actions and these exact words: typing on his phone / texting / scrolling, typing on a laptop, someone knocking on the door, walking / pacing the hallway, "
          "a coffee mug / a cup of tea, pulling the blanket / pillow / lying in bed, an alarm going off, a notification / message arrives, a digital clock showing a time. "
          "Vary the action from shot to shot (never the same twice in a row), at most two actions per shot, and keep Leo and Mia large in frame and visibly moving, not standing still.")


SPICE = ("VOICE OF THE SCRIPT (make it addictive, owner request): write like real best friends talking, never like a script. Mia is the savage deadpan roaster (lovingly toxic): "
         "one-line burns about Leo's habits, calling him out with EXACT specifics. Leo is the dramatic, defensive overthinker who over-reacts, gets petty, argues back and loses. "
         "Humor tools: playful roasting, petty drama, exaggeration, a running joke where the same object or habit comes back, rule of three with a twist, an unexpected comparison, "
         "and at least ONE line a viewer would screenshot or send to a friend with 'this is literally you'. Make it spoken and fast: contractions, fragments, interruptions "
         "('wait-', 'no, listen', 'excuse me?'), reactions ('oh my god', 'okay but why'), lines of 4 to 9 words, quick back-and-forth, never a speech or a lecture. "
         "Roast habits and everyday situations only: no slurs, no hate, no jokes about bodies or real harm, and the friendship stays warm underneath. "
         "The viewer should feel 'I need to see what Leo and Mia do tomorrow'.")


def _lg():
    try:   # what our real viewers watch (learner.py); empty when not available
        sys.path.insert(0,str(HERE.parent)); import learned
        return learned.guidance('doodles',KIND)
    except Exception:
        return ''
def _sr():
    try:   # series bible: recurring cast, running gag, callback (series.py)
        sys.path.insert(0,str(HERE)); import series
        return series.brief(KIND)
    except Exception:
        return ''
def _rec(s):
    try:
        import series; series.record(s['id'],s.get('title',''),s.get('concept',''),'short')
    except Exception:
        pass
def gemini(prompt,system=None):
    key=secret();last=None;rules=system or (RULES+_lg()+_sr()+" "+ACTION+" "+SPICE)
    for model in models():
        for attempt in range(3):
            if model.startswith('gemma'):
                body=json.dumps({"contents":[{"role":"user","parts":[{"text":rules+"\nReturn ONLY the JSON object, no markdown.\n\n"+prompt}]}],"generationConfig":{"temperature":0.95}}).encode()
            else:
                body=json.dumps({"systemInstruction":{"parts":[{"text":rules}]},"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.95,"responseMimeType":"application/json"}}).encode()
            req=urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",body,{'Content-Type':'application/json'})
            try:
                d=json.loads(urllib.request.urlopen(req,timeout=120).read());t=''.join(p.get('text','') for p in d['candidates'][0]['content']['parts']);m=re.search(r'\{.*\}',t,re.S);return m.group(0) if m else t
            except urllib.error.HTTPError as e:
                last=f'{model} HTTP {e.code}'
                if e.code==429:break
                if e.code in (500,503):time.sleep(15*(attempt+1));continue
                break
            except Exception as e:last=f'{model} {e}';break
    try:   # Gemini quota used up: free fallback providers (llm.py in the repo root) when a key is configured
        sys.path.insert(0,str(HERE.parent));import llm
        if llm.available():
            t=llm.text(rules,prompt+"\nReturn ONLY the JSON object, no markdown.",True,0.95);m=re.search(r'\{.*\}',t,re.S);return m.group(0) if m else t
    except Exception as e:last=f'{last}; free fallback: {str(e)[:80]}'
    raise SystemExit('Gemini failed: '+str(last))
def valid(s,taken,variant='standard'):
    try:
        assert re.fullmatch(r'[a-z0-9-]{3,40}',s['id']) and s['id'] not in taken
        assert len(s['shots'])==6
        for sh in s['shots']:
            assert 1<=len(sh['lines'])<=2 and sh['scene']
            for l in sh['lines']:assert l['who'] in('leo','mia') and 3<=len(l['text'].split())<=18
        alll=[l['text'] for sh in s['shots'] for l in sh['lines']]
        assert len(alll[0].split())<=8, 'hook too long'
        lo,hi={'micro':(36,52),'tight':(52,68)}.get(variant,(70,90))
        assert lo<=sum(len(t.split()) for t in alll)<=hi, 'length'
        assert alll[-1].strip()[-1:] in ('?','—','…','-') or alll[-1].strip().endswith('...'), 'no loop'
        s['explain_shot']=int(s.get('explain_shot',3));assert 0<=s['explain_shot']<=5
        try:stories.show_people(s)
        except Exception:pass
        return True
    except Exception:return False
JUDGE = ("You are a ruthless comedy editor for viral 40-second animated skits starring best friends Leo (anxious, dramatic) and Mia (dry, savage, loving). "
         "Score each candidate script 1-10 on: FUNNY (specific roast, surprise, a line worth screenshotting), HOOK (the first line grabs in two seconds), "
         "SPOKEN (sounds like real fast friends talking, not a written script), RELATABLE (a viewer thinks 'this is literally me'), LOOP (last line sets up the first). "
         "Be harsh and honest; do not give everyone the same score. Return ONLY JSON: {\"scores\":[{\"i\":0,\"funny\":7,\"hook\":6,\"spoken\":8,\"relatable\":7,\"loop\":5}],\"best\":0,\"why\":\"one short sentence\"}")
BESTOF = int(__import__('os').environ.get('DOODLES_BESTOF', '3'))


def _text(c):
    return '\n'.join(('%s: %s' % (l['who'].title(), l['text'])) for sh in c['shots'] for l in sh['lines'])


def judge(cands):
    """Pick the strongest candidate. ANY problem -> the first candidate (never blocks the pipeline). Returns (index, scores_dict_or_None)."""
    if len(cands) < 2: return 0, None
    try:
        prompt = 'Candidates:\n' + '\n\n'.join('### %d (%s)\n%s' % (i, c.get('title', ''), _text(c)) for i, c in enumerate(cands)) + '\n\nScore them and choose the best.'
        r = json.loads(gemini(prompt, JUDGE)); best = int(r.get('best'))
        sc = {int(x['i']): x for x in r.get('scores', []) if 'i' in x}
        assert 0 <= best < len(cands)
        return best, {'best': best, 'why': str(r.get('why', ''))[:160], 'scores': sc.get(best), 'n': len(cands)}
    except BaseException as e:   # SystemExit from gemini() included
        print('judge skipped:', str(e)[:80]); return 0, None


def pick_best(topic, taken, variant, vnote):
    """Write BESTOF candidates for the same topic, let the judge keep the best one."""
    cands = []; ids = set(taken)
    for k in range(max(1, BESTOF)):
        try: c = json.loads(gemini(f'Write a new episode about: {topic}. Already used ids (do not reuse): {sorted(ids)}' + vnote))
        except SystemExit as e: print(e); time.sleep(20); continue
        except Exception as e: print('bad json', e); continue
        if valid(c, ids, variant): cands.append(c); ids.add(c['id'])
        else: print('candidate rejected (format)')
    if not cands: return None
    i, info = judge(cands)
    best = cands[i]
    if info: best['judge'] = info
    print('best-of-%d: kept %s%s' % (len(cands), best['id'], (' (' + info['why'] + ')') if info else ''))
    return best


def _viewer_topic():
    """A topic suggested by real viewer comments (comment_ideas.py), used once then removed. Any problem -> None."""
    try:
        f=HERE.parent/'data/doodles/comment_ideas.json';L=json.loads(f.read_text())
        if not L:return None
        t=L.pop(0);f.write_text(json.dumps(L,indent=1));print('viewer topic:',t);return t
    except Exception:return None
def load():return json.loads(POOL.read_text()) if POOL.exists() else []
def main():
    n=int(sys.argv[1]) if len(sys.argv)>1 else 3;pool=load();taken={s['id'] for s in stories.STORIES}|{s['id'] for s in pool};made=0
    for attempt in range(n*3):
        if made>=n:break
        topic=_viewer_topic() or next((t for t in TOPICS if re.sub(r'[^a-z]+','-',t.lower()).strip('-')[:20] not in ' '.join(taken)),TOPICS[attempt%len(TOPICS)])
        TOPICS.remove(topic) if topic in TOPICS else None
        variant=('micro','tight','standard')[len(pool)%3]   # length test (G1, Nov 9): ~18 s / ~30 s / ~42 s Shorts, the learner compares them
        vnote=' LENGTH VARIANT (overrides the word count above): the whole video is 36 to 52 spoken words in total (about 15 to 22 seconds), SIX shots with ONE short line each, the joke lands in the first 2 seconds, keep the payoff and the loop.' if variant=='micro' else ' LENGTH VARIANT (overrides the word count above): the whole video is 52 to 68 spoken words in total (about 28 to 35 seconds), every line punchy, keep the hook, the payoff and the loop.' if variant=='tight' else ''
        s=pick_best(topic,taken,variant,vnote)
        if s is None:continue
        if valid(s,taken,variant):s['variant']=variant;pool.append(s);_rec(s);taken.add(s['id']);made+=1;POOL.write_text(json.dumps(pool,indent=1));print('wrote',s['id'])
        else:print('rejected a story (format)')
    print('pool size',len(pool))
if __name__=='__main__':main()
