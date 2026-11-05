"""AnimationDoodles FULL VIDEO writer (8-9 min). An EPISODE is one continuous story with a through-line: 12 scenes (about 40 s each) in which Leo's day is
sabotaged and rescued by a different psychology trap each time, Mia as the dry friend, one running gag, and a payoff in the last scene.
Step 1: Gemini plans the episode outline. Step 2: Gemini writes each scene as an ordinary Doodles skit (same 6-shot format and checks as the Shorts).
Output: data/doodles/episode_pool.json  [ {id,title,premise,running_gag,scenes:[{time,concept,beat,story:{...skit...}}], description} ].
Usage: python episode_writer.py [N]  (needs data/secrets.json GEMINI_API_KEY, like story_writer.py). Posts nothing."""
import json, re, sys, time, random
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import story_writer as sw, stories
sw.KIND = 'full'   # this module writes episodes: use the full-video viewer notes
POOL = ROOT / 'data/doodles/episode_pool.json'
import os
SCENES = int(os.environ.get('EPISODE_SCENES', '4'))   # 4 scenes = about 3:40 with cards (owner decision 2026-11-04: 3-4 min for now)
THEMES = ["Leo's presentation day (everything that can sabotage a talk, from 7 AM alarm to the 5 PM stage)", "Leo moves into a new apartment (decisions, boxes, neighbours, first night)",
          "Leo's first date with someone he met online (nerves, texts, restaurant, the walk home)", "Leo vs. the inbox: one Monday at work that will not end",
          "Mia's surprise birthday: Leo has to keep a secret and plan it in one day", "Leo tries to become a morning person for exactly one day",
          "Leo's job interview day, from the night before to the callback", "Leo finally cleans his phone: one Saturday, thousands of photos and tabs",
          "Leo's road trip with Mia: a wrong turn, a playlist war, a roadside diner", "Leo adopts a plant named Gerald and tries to keep him alive for a week (told as seven days)",
          "Leo runs his first 5K (training, gear, the starting line)", "Leo hosts a dinner party for six strangers-turned-friends"]
OUTLINE_RULES = """You are the head writer of the animated channel AnimationDoodles: LEO (anxious overthinker, yellow hoodie) and MIA (dry, kind, blunt, teal sweater).
You plan ONE 3-to-4-minute episode as a single continuous day/story, not a list of unrelated lessons. Return ONE JSON object only:
{"id":"kebab-slug","title":"short punchy episode title","premise":"2 sentences: what Leo wants today and what is at stake","running_gag":"one small recurring joke or object that returns in most scenes",
"payoff":"how the last scene pays off the premise and the running gag","scenes":[ exactly __N__ of {"time":"clock time or day label that moves forward","setting":"where","concept":"ONE pop-psychology idea that naturally shows up in this moment (UPPERCASE NAME)","beat":"1-2 sentences: what happens, how it escalates or resolves the day"} ],
"description":"3 sentences for the YouTube description, curious and warm"}
Rules: concepts must be different in every scene and soft ('can', 'often'), no invented statistics, no named studies with numbers. Scene 1 starts mid-trouble (no introduction); the last scene is the payoff and lands on a warm laugh.
Each scene must make sense alone for a new viewer yet move the day forward (cause and effect from scene to scene). Keep Leo and Mia visible together in everyday places."""
SCENE_NOTE = ("This skit is scene {i} of {n} of ONE continuous episode titled '{title}'. Premise: {premise} Running gag (use it lightly, maybe as a prop or one line): {gag}. "
              "Scene setting/time: {time}, {setting}. What happens: {beat}. The psychology idea to show: {concept}. Previous scene: {prev}. "
              "Write it as a 6-shot skit in the usual JSON format, 75 to 95 spoken words in total, every line 3 to 18 words, every line with a 'feel'. Use the id '{sid}'. Do not introduce the characters; do not say goodbye unless this is the last scene. "
              "Only the last scene may end warmly; every other scene may end on a hook that leads to the next scene.")

COMEDY = ("COMEDY DIRECTION (this is the main goal): make it genuinely funny, like chaotic best friends. Mia is dry, savage but loving: backhanded compliments, petty roasts, 'I told you so', "
          "passive-aggressive texts, guilt trips. Leo catastrophizes, over-explains and loses arguments with himself. Toxic-friend banter is allowed and encouraged as long as it is playful (never cruel to real groups, no slurs, no self-harm, no sex). "
          "Every scene needs a clear punchline in its last one or two lines and one specific, concrete, absurd detail (an exact object, number of minutes, or petty grievance). Escalate the absurdity scene by scene and call back to the running gag. "
          "Show the psychology idea through behaviour and jokes, never as a lecture. Other people who are mentioned (a boss, a barista, an ex, a neighbour) should be visible in the shot descriptions, "
          "described in a few words (clothes, expression) and placed in the background or at the edge so Leo and Mia stay in front. Backgrounds should look like real, specific places with real clutter, not empty rooms.")


def jcall(system, prompt):
    keep = sw.RULES
    sw.RULES = system
    try:
        return json.loads(sw.gemini(prompt))
    finally:
        sw.RULES = keep


def scene_why(s, taken):
    """Relaxed Shorts check for a scene inside an episode. Returns '' when fine, else the reason (fed back to the writer)."""
    try:
        if not (re.fullmatch(r'[a-z0-9-]{3,40}', s['id']) and s['id'] not in taken): return 'bad or reused id'
        if len(s['shots']) != 6: return 'needs exactly 6 shots, got %d' % len(s['shots'])
        for sh in s['shots']:
            if not (1 <= len(sh['lines']) <= 2 and sh['scene']): return 'each shot needs a scene text and 1-2 lines'
            for l in sh['lines']:
                if l['who'] not in ('leo', 'mia'): return "who must be 'leo' or 'mia'"
                if not 3 <= len(l['text'].split()) <= 18: return 'every line must be 3 to 18 words: "%s"' % l['text'][:40]
                if not l.get('feel'): return "every line needs a 'feel'"
        n = sum(len(l['text'].split()) for sh in s['shots'] for l in sh['lines'])
        if not 55 <= n <= 115: return 'total spoken words must be 75 to 95, yours was %d' % n
        s['explain_shot'] = 3
        return ''
    except Exception as e:
        return 'wrong JSON shape (%s)' % repr(e)[:50]


def check_outline(o):
    assert re.fullmatch(r'[a-z0-9-]{3,50}', o['id'])
    assert len(o['scenes']) == SCENES
    cs = [s['concept'].strip().upper() for s in o['scenes']]
    assert len(set(cs)) == SCENES, 'concepts repeat'
    for s in o['scenes']:
        assert s['time'] and s['setting'] and s['beat']
    assert o['title'] and o['premise'] and o['running_gag'] and o['description']
    return True


def load():
    return json.loads(POOL.read_text()) if POOL.exists() else []


def make_episode(pool):
    taken = {e['id'] for e in pool}
    used_themes = ' '.join(e.get('theme', '') for e in pool)
    theme = next((t for t in THEMES if t not in used_themes), random.choice(THEMES))
    o = None
    for attempt in range(4):
        try:
            o = jcall(OUTLINE_RULES.replace("__N__", str(SCENES)) + "\n" + COMEDY, "Plan a new episode. Theme: %s. Already used episode ids: %s" % (theme, sorted(taken)))
            check_outline(o)
            if o['id'] in taken:
                o['id'] += '-' + time.strftime('%m%d')
            break
        except Exception as e:
            print('outline problem:', str(e)[:100], flush=True)
            o = None
    if not o:
        return None
    ep = {'id': o['id'], 'title': o['title'], 'theme': theme, 'premise': o['premise'], 'running_gag': o['running_gag'], 'payoff': o.get('payoff', ''),
          'description': o['description'], 'scenes': []}
    skit_taken = {s['id'] for s in stories.STORIES}
    prev = 'none (this is the first scene)'
    for i, sc in enumerate(o['scenes'], 1):
        sid = '%s-%02d' % (ep['id'][:30], i)
        note = SCENE_NOTE.format(i=i, title=o['title'], premise=o['premise'], gag=o['running_gag'], time=sc['time'], setting=sc['setting'], beat=sc['beat'],
                                 concept=sc['concept'], prev=prev, sid=sid, n=SCENES)
        story = None; hint = ''
        for attempt in range(8):
            try:
                txt = sw.gemini(note + ' ' + COMEDY + hint)
                s, _ = json.JSONDecoder().raw_decode(txt.strip())
                s['id'] = sid
                why = scene_why(s, skit_taken)
                if not why:
                    story = s
                    break
                print('scene %d rejected (%s), retry' % (i, why), flush=True)
                hint = '\n\nYour previous attempt was rejected: %s. Fix exactly that. Return ONE JSON object only.' % why
            except SystemExit as e:
                print(e, flush=True); time.sleep(20)
            except Exception as e:
                print('bad json', str(e)[:80], flush=True); hint = '\n\nReturn exactly ONE JSON object and nothing after it.'
        if not story:
            print('could not write scene %d; episode dropped' % i, flush=True)
            return None
        ep['scenes'].append({'time': sc['time'], 'setting': sc['setting'], 'concept': sc['concept'].strip().upper(), 'beat': sc['beat'], 'story': story})
        skit_taken.add(sid)
        prev = '%s: %s' % (sc['time'], sc['beat'])
        print('episode %s scene %d/%d written' % (ep['id'], i, SCENES), flush=True)
    return ep


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    pool = load()
    for _ in range(n):
        ep = make_episode(pool)
        if ep:
            pool.append(ep)
            try:
                import series; series.record(ep['id'], ep['title'], ep.get('theme', ''), 'full')
            except Exception:
                pass
            POOL.write_text(json.dumps(pool, indent=1))
            print('wrote episode', ep['id'], flush=True)
    print('episode pool size', len(pool))


if __name__ == '__main__':
    main()
