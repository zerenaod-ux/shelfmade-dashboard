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
def _lg():
    try:   # what our real viewers watch (learner.py); empty when not available
        sys.path.insert(0,str(HERE.parent)); import learned
        return learned.guidance('doodles')
    except Exception:
        return ''
def gemini(prompt):
    key=secret();last=None;rules=RULES+_lg()
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
    raise SystemExit('Gemini failed: '+str(last))
def valid(s,taken):
    try:
        assert re.fullmatch(r'[a-z0-9-]{3,40}',s['id']) and s['id'] not in taken
        assert len(s['shots'])==6
        for sh in s['shots']:
            assert 1<=len(sh['lines'])<=2 and sh['scene']
            for l in sh['lines']:assert l['who'] in('leo','mia') and 3<=len(l['text'].split())<=18
        alll=[l['text'] for sh in s['shots'] for l in sh['lines']]
        assert len(alll[0].split())<=8, 'hook too long'
        assert 70<=sum(len(t.split()) for t in alll)<=90, 'length'
        assert alll[-1].strip()[-1:] in ('?','—','…','-') or alll[-1].strip().endswith('...'), 'no loop'
        s['explain_shot']=int(s.get('explain_shot',3));assert 0<=s['explain_shot']<=5
        return True
    except Exception:return False
def load():return json.loads(POOL.read_text()) if POOL.exists() else []
def main():
    n=int(sys.argv[1]) if len(sys.argv)>1 else 3;pool=load();taken={s['id'] for s in stories.STORIES}|{s['id'] for s in pool};made=0
    for attempt in range(n*3):
        if made>=n:break
        topic=next((t for t in TOPICS if re.sub(r'[^a-z]+','-',t.lower()).strip('-')[:20] not in ' '.join(taken)),TOPICS[attempt%len(TOPICS)])
        TOPICS.remove(topic) if topic in TOPICS else None
        try:s=json.loads(gemini(f'Write a new episode about: {topic}. Already used ids (do not reuse): {sorted(taken)}'))
        except SystemExit as e:print(e);time.sleep(20);continue
        except Exception as e:print('bad json',e);continue
        if valid(s,taken):pool.append(s);taken.add(s['id']);made+=1;POOL.write_text(json.dumps(pool,indent=1));print('wrote',s['id'])
        else:print('rejected a story (format)')
    print('pool size',len(pool))
if __name__=='__main__':main()
