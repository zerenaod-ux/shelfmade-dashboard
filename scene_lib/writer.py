"""THE WRITER: turns a topic into a full scene description (pictures, narration, sounds, camera) with the free LLMs, then checks it.
If the checker finds problems, the writer is shown them and must fix them (up to 4 tries). A description that still fails is rejected: no video is made from it.
  python3 scene_lib/writer.py --topic-file topic.txt out.json        (needs the free LLM keys in the environment)"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scene_lib.catalog import catalog_text, SOUNDS_DUR, SOUNDS_FREQ, SOUNDS_PLAIN
from scene_lib.validate import check

TIMES = [(0.3, 4.5), (4.7, 9.2), (9.4, 13.6), (13.8, 18.6), (18.8, 23.4), (23.6, 28.4), (28.6, 33.5)]
DURATION = 33.6
SYS = 'You design short animated explainer scenes for a 2D scene engine. You answer with ONE JSON object and nothing else.'

def prompt_for(topic):
    example = json.dumps(json.loads((ROOT / 'scenes' / 'water-tower.json').read_text()), separators=(',', ':'))
    return f"""Design a 33-second vertical video that explains: {topic}

STYLE: one continuous living scene (no cuts). The picture itself must prove each sentence: things fill, flow, turn, grow, move or light up, step by step, so the viewer SEES how it works.

STAGE: x goes right, y goes up, the ground is y=0. Keep the main action between x=-350 and x=650. Objects are about 100 to 300 units big. Things at y below 0 are underground (shown as a cut-away).
Parts are drawn in list order (later parts cover earlier ones): sky first, then trees, ground, underground things, the main objects, labels last.

PARTS YOU MAY USE (only these; build anything else from rect, circle and poly):
{catalog_text()}

ANIMATION: any number field listed for a part can be a fixed number or keyframes [[time, value], [time, value], ...]. The value holds before the first and after the last keyframe and moves smoothly between them.

CAMERA: a list of [time, x, y, zoom]. x is the centre of the picture, y is the height shown a little below the middle of the screen. zoom 0.66 shows about 1090 units across, 1.0 shows 720, 1.5 shows 480.
Start wide (show everything), then for each step move to the part that is acting (zoom 1.2 to 1.7), and end wide again. The first entry must be at time 0 and the last at {DURATION}.

STEPS: exactly 7, with exactly these times: {', '.join('step %d: %.1f-%.1f' % (i + 1, a, b) for i, (a, b) in enumerate(TIMES))}.
Each step has "label" (2-16 letters) and "say": ONE energetic spoken sentence of 8 to 13 plain words. Step 1 is a hook question. Step 7 is the payoff.
Facts must be true and general. Do not give numbers you are not sure of. No medical or money advice.
During every step something on screen must change, and the camera must be looking at it.

SOUNDS: "sfx" is a list of [time, name, loudness 0.3-1.0, optional value]. Give at least 8, each timed to an action on screen.
Sounds with an optional length in seconds: {', '.join(sorted(SOUNDS_DUR))}. With an optional pitch: {', '.join(sorted(SOUNDS_FREQ))}. Plain: {', '.join(sorted(SOUNDS_PLAIN))}.

Return JSON with these keys: "title" (starts with How or Why, 4-8 words, ends with ONE emoji), "duration": {DURATION}, "music": {{"bpm": 118}}, "steps", "camera", "sfx", "parts" (20 to 45 parts).

Here is a finished example for a DIFFERENT topic, to show the format. Do not copy its layout or its sentences; design the stage for your own topic:
{example}"""

def tidy(spec):
    """Small safe repairs that do not change the idea: exact step times, duration, music."""
    if not isinstance(spec, dict): return spec
    spec['duration'] = DURATION; spec.setdefault('music', {'bpm': 118})
    st = spec.get('steps')
    if isinstance(st, list) and len(st) == len(TIMES):
        for s, (a, b) in zip(st, TIMES):
            if isinstance(s, dict): s['start'], s['end'] = a, b; s.pop('caption', None)
    return spec

def write_scene(topic, tries=4, log=print):
    import llm
    base = prompt_for(topic); spec = None; errs = None
    for k in range(1, tries + 1):
        p = base if not errs else base + '\n\nYOUR LAST ANSWER HAD THESE PROBLEMS. Fix every one and return the full corrected JSON:\n' + '\n'.join('- ' + e for e in errs[:25]) + '\n\nYour last answer was:\n' + json.dumps(spec, separators=(',', ':'))[:14000]
        try: spec = tidy(llm.json_call(SYS, p, temperature=0.75 if k == 1 else 0.4, max_tokens=8000))
        except Exception as e:
            log('try %d: the writer did not return usable JSON (%s)' % (k, str(e)[:160])); errs = errs or ['the answer was not valid JSON']; continue
        errs = check(spec)
        log('try %d: %s' % (k, 'PASSED the checker' if not errs else '%d problems: %s' % (len(errs), ' | '.join(errs[:6]))))
        if not errs: return spec
    raise SystemExit('REJECTED: the writer could not produce a scene that passes the checker after %d tries. No video was made.' % tries)

if __name__ == '__main__':
    if sys.argv[1] != '--topic-file': raise SystemExit(__doc__)
    topic = re.sub(r'\s+', ' ', Path(sys.argv[2]).read_text().splitlines()[0]).strip()[:200]
    if len(topic) < 8: raise SystemExit('the topic is too short')
    lines = ['topic: ' + topic]
    def log(m): print(m, flush=True); lines.append(m)
    try:
        spec = write_scene(topic, log=log); Path(sys.argv[3]).write_text(json.dumps(spec, indent=1)); log('title: %s | %d parts | %d sounds' % (spec['title'], len(spec['parts']), len(spec.get('sfx', []))))
    finally:
        Path('writer-log.txt').write_text('\n'.join(lines) + '\n')
