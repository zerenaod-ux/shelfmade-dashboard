"""THE WRITER: turns a topic into a full scene description, working the way a careful human designer does, with the free LLMs.
  1. PLAN  - find the cause (principle), the chain of cause and effect, the cast of objects and where each one stands, and 7 steps that each PROVE one sentence.
  2. STAGE - turn the plan into the exact scene description (parts, keyframes, camera, sounds).
  3. CHECK - the checker applies the design logic (physics, connections, camera, labels, proof for every sentence). Problems go back to the writer to fix.
A description that still fails after the tries is rejected: no video is made from it.
  python3 scene_lib/writer.py --topic-file topic.txt out.json        (needs the free LLM keys in the environment)"""
import json, os, re, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scene_lib.catalog import CATALOG, catalog_text, SOUNDS_DUR, SOUNDS_FREQ, SOUNDS_PLAIN
from scene_lib.validate import check

TIMES = [(0.3, 4.5), (4.7, 9.2), (9.4, 13.6), (13.8, 18.6), (18.8, 23.4), (23.6, 28.4), (28.6, 33.5)]
DURATION = 33.6
SYS = 'You are a brilliant science animator and scene designer. You answer with ONE JSON object and nothing else.'
STAGE_TEXT = 'x goes right, y goes up. If there is ground, its surface is y=0 and things below 0 are underground. Keep everything between x=-380 and x=700 and between y=-220 and y=420. Objects are about 60 to 300 units big.'

def _num(v): return isinstance(v, (int, float)) and not isinstance(v, bool)

def plan_prompt(topic):
    return f"""TOPIC: {topic}

You will plan a 33-second animated explainer shown as ONE continuous living scene (no cuts): a cut-away side view where the viewer watches the thing work, step by step.
Work like a careful designer. Think in this order:

1. PRINCIPLE: the real cause. Why does it work? One or two true sentences.
2. CHAIN: 5 to 7 links of cause and effect, in the order they happen ("because A, B happens").
3. CAST: 4 to 8 objects the viewer must see. ANY topic can be drawn: "emoji" gives any recognisable object (animal, organ, planet, vehicle, tool, food, person, building), "path" draws any custom shape, and there are ready parts for water, pipes, wires, wheels, particles (fire, smoke, steam, sparks, bubbles, snow), meters and more. All part types: {', '.join(CATALOG)}.
   Also choose the SETTING: where it happens (outdoors, underground, underwater, in space, inside a body, in a lab) and whether there is ground.
4. LAYOUT: give every cast member a box on the stage: x0, x1, y0, y1. Stage: {STAGE_TEXT}
   - The layout must SHOW the principle. If gravity matters, the source is physically higher than where the water ends up. If something is underground, it is below y=0.
   - Put the objects in the order of the chain, left to right, so the camera travels one way.
   - Solid machines and buildings stand on dry ground, never inside water. Boxes of different objects must not overlap (a pipe or wire joins them).
5. STEPS: exactly 7. Each step = one spoken sentence + the ONE cast member that visibly changes to prove it (fills, drains, flows, spins, grows, lights up, appears).
   - "say": ONE energetic sentence, 8 to 13 plain words, vivid verbs. Step 1 is a hook question. Step 7 is the payoff that ties it to the viewer's life.
   - True, general facts only. No numbers you are not sure of. No medical or money advice.
   - Be creative: choose a surprising, concrete angle, not a textbook definition.

Return JSON:
{{"title": "starts with How or Why, 4-8 words, ends with ONE emoji",
 "principle": "...",
 "style": "flow" (mostly water, pipes, machines) or "icons" (living things, body, space, objects, ideas),
 "setting": {{"preset": "day|dusk|night|desert|snow|space|ocean|body|lab|clean", "ground": "grass|sand|snow|rock|seabed|floor|none"}},
 "chain": ["...", "..."],
 "cast": [{{"id": "shortname", "what": "what it is", "built_from": "part types", "x0": 0, "x1": 0, "y0": 0, "y1": 0}}],
 "steps": [{{"label": "2-16 letters", "say": "...", "shows": "cast id", "change": "what visibly changes"}}]}}"""

def check_plan(pl):
    E = []
    if not isinstance(pl, dict): return ['the plan must be one JSON object']
    if not isinstance(pl.get('principle'), str) or len(pl['principle'].split()) < 8: E.append('principle must be one or two full sentences')
    if pl.get('style') not in ('flow', 'icons'): E.append('style must be "flow" or "icons"')
    if not isinstance(pl.get('chain'), list) or not 4 <= len(pl['chain']) <= 8: E.append('chain must have 5 to 7 links')
    cast = pl.get('cast'); ids = {}
    if not isinstance(cast, list) or not 4 <= len(cast) <= 9: E.append('cast must have 4 to 8 objects'); cast = []
    for c in cast:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not all(_num(c.get(k)) for k in ('x0', 'x1', 'y0', 'y1')): E.append('each cast member needs id, x0, x1, y0, y1'); continue
        if c['id'] in ids: E.append('cast id "%s" is used twice' % c['id'])
        ids[c['id']] = c
        if c['x1'] <= c['x0'] or c['y1'] <= c['y0']: E.append('cast "%s": x1 must be greater than x0 and y1 greater than y0' % c['id'])
        if c['x0'] < -420 or c['x1'] > 760 or c['y0'] < -260 or c['y1'] > 460: E.append('cast "%s" is outside the stage' % c['id'])
    cs = list(ids.values())
    for i, a in enumerate(cs):
        for b in cs[i + 1:]:
            ox = min(a['x1'], b['x1']) - max(a['x0'], b['x0']); oy = min(a['y1'], b['y1']) - max(a['y0'], b['y0'])
            if ox > 0 and oy > 0:
                small = min((a['x1'] - a['x0']) * (a['y1'] - a['y0']), (b['x1'] - b['x0']) * (b['y1'] - b['y0']))
                if small > 0 and ox * oy / small > 0.35: E.append('cast "%s" and "%s" overlap; give each its own place and join them with a pipe or wire' % (a['id'], b['id']))
    st = pl.get('steps')
    if not isinstance(st, list) or len(st) != 7: E.append('steps must be exactly 7'); st = []
    for i, s in enumerate(st, 1):
        if not isinstance(s, dict): E.append('step %d must be an object' % i); continue
        if s.get('shows') not in ids: E.append('step %d: "shows" must be one of the cast ids' % i)
        w = len(str(s.get('say', '')).split())
        if not 6 <= w <= 14: E.append('step %d: "say" must be 8 to 13 words (it has %d)' % (i, w))
        if not isinstance(s.get('label'), str) or not 2 <= len(s['label']) <= 16: E.append('step %d: label must be 2 to 16 letters' % i)
    if st and isinstance(st[0], dict) and '?' not in str(st[0].get('say', '')): E.append('step 1 must be a hook question')
    return E

def stage_prompt(topic, plan, with_example=True):
    ex = (ROOT / 'scene_lib' / ('example_icons.json' if plan.get('style') == 'icons' else 'example_flow.json')).read_text() if with_example else ''
    return f"""TOPIC: {topic}

Here is the approved PLAN. Now build the exact scene description from it.
{json.dumps(plan, ensure_ascii=False)}

STAGE: {STAGE_TEXT}
Parts are drawn in list order (later parts cover earlier ones): sky first (with the preset from the plan's setting), then scenery, ground (if any), the main objects, labels last.

PARTS YOU MAY USE (only these). Use "emoji" for any recognisable object and "path" to draw custom shapes; never leave a main subject as a plain box:
{catalog_text()}
Any part may have an "id". Give every cast member's main part the same id as in the plan.

ANIMATION: any number field can be a fixed number or keyframes [[time, value], ...]. The value holds before the first and after the last keyframe and moves smoothly between.

STEPS: copy the 7 steps from the plan (label, say, shows) and use exactly these times: {', '.join('step %d: %.1f-%.1f' % (i + 1, a, b) for i, (a, b) in enumerate(TIMES))}.

DESIGN RULES (a checker enforces every one):
1. Proof: in each step the part named in "shows" must have keyframes that change INSIDE that step's time, and nothing important should move before its own step.
2. Camera: a list of [time, x, y, zoom]. x is the centre of the picture, y is the height shown a little below the middle. zoom 0.62 shows about 1160 units across, 1.0 shows 720, 1.6 shows 450.
   Start wide at time 0 (show the whole stage), move to each step's "shows" part and zoom in so it is large (1.1 to 2.0), end wide at {DURATION}.
3. Physics: add "flows": [{{"from":[x,y],"to":[x,y],"by":"gravity"|"pump"|"pressure"}}] for every pipe or stream. Gravity flows must go DOWN. A pump flow needs a pump part. Pressure can only lift water to below its source height.
4. Connections: every pipe and wire must start and end touching the things it joins.
5. Machines, wheels, pumps and houses stand on dry ground, never inside a body of water. Water never floats: it sits in a container, behind a wall, or in the ground.
6. Houses, towers, trees and plants stand on the ground (y=0) or on top of a shape.
7. Labels: CAPITALS, at most 16 letters, each with "show" keyframes so it fades in during its own step and out again. Never more than 2 labels at once. No labels in step 1.
8. Sounds: "sfx" is a list of [time, name, loudness 0.3-1.0, optional value], at least 10, at least one in every step, timed to the action.
   With an optional length in seconds: {', '.join(sorted(SOUNDS_DUR))}. With an optional pitch: {', '.join(sorted(SOUNDS_FREQ))}. Plain: {', '.join(sorted(SOUNDS_PLAIN))}.
9. Make it alive: at least 8 parts that change over time; water levels, pipe progress and flow, spinning wheels, growing plants, lights, arrows.
10. Make it beautiful: scenery for depth, clear colours, the main subject large, 22 to 34 parts in total. Write compact JSON.
11. Emoji: one common emoji per "char". Things that travel get x and y keyframes (or an orbit). Use particles for fire, smoke, steam, sparks, bubbles, dust.

Return JSON with keys: "title", "principle", "duration": {DURATION}, "music": {{"bpm": 118}}, "flows", "steps", "camera", "sfx", "parts".

{('One finished example for a DIFFERENT topic shows the format and the level of care. Do not copy its layout or sentences: ' + ex) if with_example else ''}"""

def tidy(spec, plan=None):
    """Small safe repairs that do not change the idea: exact step times, duration, music, and the plan's own sentences."""
    if not isinstance(spec, dict): return spec
    spec['duration'] = DURATION
    if not isinstance(spec.get('music'), dict): spec['music'] = {'bpm': 118}
    st = spec.get('steps')
    if isinstance(st, list) and len(st) == len(TIMES):
        for i, (s, (a, b)) in enumerate(zip(st, TIMES)):
            if isinstance(s, dict):
                s['start'], s['end'] = a, b; s.pop('caption', None); s.pop('change', None)
                if plan and isinstance(plan.get('steps'), list) and len(plan['steps']) == len(TIMES):
                    for k in ('label', 'say'): s[k] = plan['steps'][i][k]
    if plan:
        for k in ('title', 'principle'):
            if isinstance(plan.get(k), str): spec.setdefault(k, plan[k])
    return spec

def _call(llm, prompt, temp, turn, log):
    """Ask the free LLM services one at a time, starting with a different one each turn, and report why each one failed."""
    provs = [p for p in llm.PROVIDERS if os.environ.get(p[0], '').strip()]; saved = llm.PROVIDERS; why = []
    if not provs: raise ValueError('no free LLM key is configured')
    try:
        for p in provs[turn % len(provs):] + provs[:turn % len(provs)]:
            llm.PROVIDERS = [p]
            try: return llm.json_call(SYS, prompt, temperature=temp, max_tokens=5200)
            except Exception as e: why.append(str(e)[:110].replace('llm.py: ', ''))
    finally: llm.PROVIDERS = saved
    raise ValueError(' ; '.join(why))

def _ask(llm, prompt, checker, tries, temp, log, name, post=lambda x: x, repair_prompt=None):
    out = None; errs = None; turn = 0
    for k in range(1, tries + 1):
        base = prompt if (not errs or out is None or not repair_prompt) else repair_prompt
        p = base if (not errs or out is None) else base + '\n\nYOUR LAST ANSWER HAD THESE PROBLEMS. Fix every one, keep what was good, and return the full corrected JSON:\n' + '\n'.join('- ' + e for e in errs[:30]) + '\n\nYour last answer was:\n' + json.dumps(out, separators=(',', ':'), ensure_ascii=False)[:13000]
        try: got = _call(llm, p, temp if k == 1 else 0.35, turn, log)
        except Exception as e:
            log('%s try %d: no free LLM answered (%s); waiting 40 s' % (name, k, str(e)[:330])); turn += 1; time.sleep(40); continue
        try: out = post(got)
        except Exception as e: log('%s try %d: unusable answer (%s)' % (name, k, str(e)[:120])); errs = ['the answer was not a valid scene object']; continue
        errs = checker(out)
        log('%s try %d: %s' % (name, k, 'PASSED' if not errs else '%d problems: %s' % (len(errs), ' | '.join(errs[:8]))))
        if not errs: return out
    raise SystemExit('REJECTED: the %s could not pass the checker after %d tries. No video was made.' % (name, tries))

def write_scene(topic, log=print):
    import llm
    plan = _ask(llm, plan_prompt(topic), check_plan, 5, 0.9, log, 'plan')
    log('principle: ' + plan['principle']); log('cast: ' + ', '.join('%s (%s)' % (c['id'], c.get('what', '')) for c in plan['cast']))
    spec = _ask(llm, stage_prompt(topic, plan), check, 8, 0.5, log, 'scene', post=lambda s: tidy(s, plan), repair_prompt=stage_prompt(topic, plan, with_example=False))
    return plan, spec

if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] != '--topic-file': raise SystemExit(__doc__)
    topic = re.sub(r'\s+', ' ', Path(sys.argv[2]).read_text().splitlines()[0]).strip()[:200]
    if len(topic) < 8: raise SystemExit('the topic is too short')
    lines = ['topic: ' + topic]
    def log(m): print(m, flush=True); lines.append(m)
    try:
        plan, spec = write_scene(topic, log=log)
        Path(sys.argv[3]).write_text(json.dumps(spec, indent=1, ensure_ascii=False)); Path('auto-plan.json').write_text(json.dumps(plan, indent=1, ensure_ascii=False))
        log('title: %s | %d parts | %d sounds' % (spec['title'], len(spec['parts']), len(spec.get('sfx', []))))
    finally:
        Path('writer-log.txt').write_text('\n'.join(lines) + '\n')
