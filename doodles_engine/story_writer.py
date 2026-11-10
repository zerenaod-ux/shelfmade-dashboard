"""Writes new AnimationDoodles stories (free Gemini key from data/secrets.json) into data/doodles/story_pool.json.
Run: <img-lab python> story_writer.py [N]   - adds N new stories (default 3). Uses only the standard library."""
import json,re,sys,time,urllib.request,urllib.error
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;POOL=ROOT/'data/doodles/story_pool.json'
sys.path.insert(0,str(HERE));import stories
TOPICS=["Leo replied to a text way too fast and now acts like he did not","Mia asks 'what do you want for dinner' and Leo says 'anything' then rejects everything","the last slice of pizza and a very polite war","Leo hits snooze five times and calls it 'sleeping in stages'","a group chat with 99 new messages and nobody read them","texting the wrong person by mistake","the phone is at 1 percent and the charger is far away","someone says 'we need to talk' and Leo imagines the worst","Leo waves back at someone who was not waving at him","two roommates, one fridge, one stolen leftover","the thermostat fight (too hot, too cold, nobody wins)","the microwave beeps and Leo cannot decide to open it fast or slow","who pays on the date, and the awkward bill dance","Leo says 'you too' when the waiter says enjoy your meal","Mia's mom calls and Leo picks up by mistake","the self-checkout machine says 'unexpected item' again","autocorrect turns a sweet text into a disaster","Leo forgot a free trial and paid for a whole year","being on mute in a video call and talking for five minutes","Leo has 47 tabs open and one of them is playing music somewhere","a movie night where they cannot pick a movie for one hour","Leo cooks for the first time and the smoke alarm joins the date","a fake 'I'm five minutes away' when you have not left home","Leo practices a cool one-liner and says it at the wrong time","two friends in the elevator with someone from work and nobody talks","Leo loses his keys and they are in his hand","the wifi dies right at the best part","Leo texts 'lol' with a very sad face","a surprise party that Leo already knew about","the neighbor's dog likes Mia more than Leo","Leo says he will start the diet on Monday (it is Tuesday)","Leo borrowed a hoodie and now it is 'his'","a part-two story: yesterday's argument is still going today","a part-two story: Leo's big plan from yesterday went wrong, again","Mia gives advice and Leo does the exact opposite on purpose","the long goodbye at the door that takes twenty minutes","Leo promises to be on time and arrives with coffee as an apology","a lost sock that comes back as two","Leo is scared of a tiny spider and the spider is calm","a gift they both forgot to buy, on the same day"]
RULES="""You write 40-second funny animated skits starring LEO (goofy, dramatic, makes everything bigger than it is, yellow hoodie) and MIA (quick-witted best friend, teasing but kind, teal sweater). They talk like REAL people: fast, casual, simple words. NOT a lesson. NOT psychology. No big words, no science words, no concept names, no studies, no statistics.
Return ONE JSON object: {"id":"kebab-slug","title":"short funny title","concept":"UPPERCASE FUNNY LABEL (2-4 words)","mood":"one of curious|warm|mysterious|reflective|dramatic|calm - pick by the feel of THIS story (dramatic for fights and panic, warm for sweet moments, curious for mystery)","insight":"one funny line that sums it up (max 70 chars)","caption":"1-2 sentence hook for social media, simple words",
"explain_shot":3,"shots":[ exactly 6 of {"scene":"...","focus":"both|leo|mia","lines":[{"who":"leo|mia","feel":"confident|deadpan|sheepish|panicked|warm|tired|excited|hopeful|amused|anxious","beat":"snap|quick|normal|pause","text":"..."}]} ]}
BEAT = how fast this line comes AFTER the previous line. snap = jumps in right away, even cuts in (use for comebacks, 'wait-', 'excuse me?'); quick = answers fast; normal = a normal reply; pause = a real beat of silence first (use ONLY when the line needs it: shock, awkward truth, thinking, sad-funny). Use snap or quick for most lines, at most 2 pauses in the whole video, and put each pause where the silence itself is funny.
STRUCTURE (a tiny story, not a lecture): shot 1 HOOK starts in the middle of the problem, no intro; shot 2 the problem gets bigger because of what Leo does; shot 3 it gets even funnier (a twist or a rule-of-three joke); shot 4 the BIG funny moment or reveal; shot 5 the last twist, a comeback or a sweet little moment; shot 6 LOOP: ONE line only, it is the LAST line of the whole video and is a question or unfinished thought that the very FIRST line of shot 1 naturally answers or continues, so it replays like one endless chat. No moral, no tip, no sign-off, no 'follow'. Pick explain_shot=3 (just the index of the big funny moment).
SIZE: whole video 70 to 88 spoken words (never more than 50 seconds). 1-2 lines per shot, each line 2 to 9 words, often just 2 to 5. The FIRST line is 8 words or fewer and starts instantly with a bold funny claim, confession, accusation or question (never a greeting, never 'Did you know').
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


SPICE = ("VOICE OF THE SCRIPT (owner rule 2026-11-10, overrides any other tone instruction above): these are two real friends being funny, NOT professional, NOT serious, NOT explaining anything. "
         "SIMPLE ENGLISH ONLY: words a ten-year-old knows, short sentences, contractions (don't, it's, I'm), slang is fine (bro, dude, okay but, literally, no way, wait what). Never use words like 'bias', 'cognitive', 'anxiety', 'productivity', 'rumination', 'perspective', 'tendency', 'psychology'. "
         "Real talk rhythm: people interrupt ('wait-', 'no no no', 'excuse me?'), answer fast, finish each other's thoughts, repeat a word for a joke, say 'um', 'uh', 'okay so'. Some lines are just one or two words ('What?', 'Seriously?', 'No.'). Nobody speaks in perfect paragraphs. "
         "Funny = a situation everyone has lived (texts, food, sleep, phones, roommates, dates, family, money, being late), exaggerated a little, with one running joke, a rule of three with a twist, and one line a viewer would send to a friend with 'this is us'. "
         "Mia teases Leo with exact little details; Leo defends himself badly and loses; they stay friends underneath. No slurs, no hate, nothing mean about bodies. "
         "Make it feel like part of a series ('to be continued', 'tomorrow part two') only when the topic says part two. Return the 'beat' of every line honestly: most lines snap or quick, because real friends answer in milliseconds, and use pause only where silence is funny. "
         "EXAMPLE of the rhythm (do not copy): Leo: 'Did you eat my fries?' (snap) / Mia: 'What fries?' (snap) / Leo: 'My fries. Fridge. Blue box.' (quick) / Mia: 'Oh... those fries.' (pause) / Leo: 'Mia.' (snap) / Mia: 'They were lonely.' (quick)")


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
            for l in sh['lines']:assert l['who'] in('leo','mia') and 1<=len(l['text'].split())<=16; l['beat']=l.get('beat') if l.get('beat') in ('snap','quick','normal','pause') else 'quick'
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
         "SPOKEN (sounds like real fast friends talking in simple everyday words, NOT professional, NOT a lesson, replies snap back fast), RELATABLE (a viewer thinks 'this is literally me'), LOOP (last line sets up the first). "
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
FORMATS=[("ARGUMENT","a fast silly argument where both are sure they are right and it escalates"),
("FUNNY EXPLAINER","Mia explains ONE small everyday thing in plain words (why the phone dies at 1 percent, why waiting feels longer), Leo asks the dumb questions everyone thinks, ends on a funny twist. One real fact, said like a friend, no big words"),
("MINI MYSTERY","Leo plays a serious detective investigating a tiny crime (who ate the leftovers, who changed the thermostat), Mia is the unimpressed suspect"),
("PART TWO","a sequel: 'yesterday's mess is still going', refer to what happened before, end with 'to be continued'"),
("CONFESSION","Leo finally admits a small embarrassing thing he has been hiding, Mia reacts in the funniest way"),
("FAKE NEWS REPORT","Leo and Mia are news anchors reporting a very serious story about a tiny everyday problem"),
("RATING GAME","they rate or rank everyday things out of ten and argue over the scores"),
("MISUNDERSTANDING","each thinks the other said something different and the mix-up grows until the reveal"),
("PRANK","Mia plans a harmless prank on Leo and it backfires"),
("ADVICE FAIL","Mia gives good advice, Leo takes it completely wrong")]
MOODS=["very excited","dry and sarcastic","sweet and warm","chaotic","tired and deadpan","overdramatic"]
ENDS=["a sudden twist","a savage one-liner from Mia","Leo gets what he deserves","they both give up and laugh","a cliffhanger for part two","a sweet moment that gets ruined"]
FH=ROOT/'data/doodles/format_history.json'
def pick_format():
    """Rotating menu with memory: never the same format as any of the last 4 videos, plus a random mood and ending. Remembered in data/doodles/format_history.json."""
    import random
    try:h=json.loads(FH.read_text())
    except Exception:h=[]
    recent=[x['format'] for x in h[-4:]]
    f=random.choice([x for x in FORMATS if x[0] not in recent] or FORMATS)
    m,e=random.choice(MOODS),random.choice(ENDS)
    h.append({'format':f[0],'mood':m,'end':e});FH.parent.mkdir(parents=True,exist_ok=True);FH.write_text(json.dumps(h[-30:],indent=1))
    note=f" FORMAT OF THIS VIDEO (owner rule: every video must feel different, never repeat a pattern): {f[0]} - {f[1]}. Mood: {m}. Ending: {e}. Make the topic fit this format; do NOT reuse the shape, jokes or opening of recent videos."
    return f[0],note
LEO_A=("You are LEO, a goofy, dramatic 20-something with a yellow hoodie. You are in a REAL back-and-forth with your best friend MIA (quick, teasing, kind). Nobody wrote a script. ")
MIA_A=("You are MIA, a quick-witted 20-something in a teal sweater, best friend of LEO (goofy, dramatic). You are in a REAL back-and-forth with him. Nobody wrote a script. ")
ACT=("Reply with ONLY your next spoken line, 1 to 12 words, simple everyday words, contractions, slang ok. React to EXACTLY what the other person just said, like real talk: interrupt, be wrong, deny, trail off with '...', answer a question with a question, say 'wait', 'no', 'okay but'. Never explain, never narrate, no stage directions, no quotes, no names before the line. Be funny the way real friends are funny, by being specific and a little exaggerated. ")
def improv(topic,fmt,turns=12):
    """Improvised real conversation: two free-LLM 'actors' play Leo and Mia turn by turn, each seeing only the chat so far (no script). The writer then edits it. Any failure -> '' and the normal writer runs alone."""
    try:
        sys.path.insert(0,str(HERE.parent));import llm
        if not llm.available():return ''
        sit=f"Situation: {topic}. Style of this scene: {fmt}. "
        chat=[];who='leo'
        for i in range(turns):
            sysm=(LEO_A if who=='leo' else MIA_A)+sit+ACT
            hist='\n'.join(f"{n.upper()}: {t}" for n,t in chat) or '(nothing said yet, you speak first and open the scene)'
            t=llm.text(sysm,'Conversation so far:\n'+hist+'\n\nYour next line:',False,1.0,60).strip().split('\n')[0]
            t=re.sub(r'^(leo|mia)\s*[:\-]\s*','',t,flags=re.I).strip(' "\'')
            if not t:break
            chat.append((who,t));who='mia' if who=='leo' else 'leo'
        if len(chat)<6:return ''
        raw='\n'.join(f"{n.upper()}: {t}" for n,t in chat)
        print('improv:',len(chat),'turns')
        return (" RAW IMPROV: two actors really talked this out with no script. This is the natural flow you must keep. Build the final episode FROM it: keep their best lines, words and rhythm in their natural order (trim, merge or cut the weak ones to fit the length, add one punch ending that loops). Do not replace their human phrasing with polished writing. "+"\nRAW IMPROV TRANSCRIPT:\n"+raw)
    except BaseException as e:
        print('improv skipped:',str(e)[:100]);return ''
def load():return json.loads(POOL.read_text()) if POOL.exists() else []
def main():
    n=int(sys.argv[1]) if len(sys.argv)>1 else 3;pool=load();taken={s['id'] for s in stories.STORIES}|{s['id'] for s in pool};made=0
    for attempt in range(n*3):
        if made>=n:break
        topic=_viewer_topic() or next((t for t in TOPICS if re.sub(r'[^a-z]+','-',t.lower()).strip('-')[:20] not in ' '.join(taken)),TOPICS[attempt%len(TOPICS)])
        TOPICS.remove(topic) if topic in TOPICS else None
        variant=('micro','tight','standard')[len(pool)%3]   # length test (G1, Nov 9): ~18 s / ~30 s / ~42 s Shorts, the learner compares them
        vnote=' LENGTH VARIANT (overrides the word count above): the whole video is 36 to 52 spoken words in total (about 15 to 22 seconds), SIX shots with ONE short line each, the joke lands in the first 2 seconds, keep the payoff and the loop.' if variant=='micro' else ' LENGTH VARIANT (overrides the word count above): the whole video is 52 to 68 spoken words in total (about 28 to 35 seconds), every line punchy, keep the hook, the payoff and the loop.' if variant=='tight' else ''
        tstyle='you' if len(pool)%2==0 else 'plain'   # title test (Nov 9): half the Doodles titles start with You/Your (our data: ~4x views on the other channels)
        if tstyle=='you':vnote+=' TITLE STYLE: the title is 2 to 5 words and starts with You or Your (a statement, e.g. "You Replied K Again").'
        fmt,fnote=pick_format()
        raw=improv(topic,fmt)
        s=pick_best(topic,taken,variant,vnote+fnote+raw)
        if s is None:continue
        if valid(s,taken,variant):s['variant']=variant;s['tstyle']=tstyle;s['style']='v2';s['format']=fmt;s['improv']=bool(raw);pool.append(s);_rec(s);taken.add(s['id']);made+=1;POOL.write_text(json.dumps(pool,indent=1));print('wrote',s['id'])
        else:print('rejected a story (format)')
    print('pool size',len(pool))
if __name__=='__main__':main()
