"""Checks a scene description before any video is made. Returns a list of plain-language problems (empty list = good).
  python3 scene_lib/validate.py scenes/<name>.json"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scene_lib.catalog import CATALOG, ANIM, POINT_LISTS, POINTS, SOUNDS, SOUNDS_DUR, SOUNDS_FREQ

def _num(v): return isinstance(v, (int, float)) and not isinstance(v, bool)
def _kfs(v): return isinstance(v, list) and len(v) > 0 and all(isinstance(k, list) and len(k) == 2 and _num(k[0]) and _num(k[1]) for k in v)
def _pt(v): return isinstance(v, list) and len(v) == 2 and _num(v[0]) and _num(v[1])

def _at(v, t, d=0.0):
    if _num(v): return v
    if not _kfs(v): return d
    if t <= v[0][0]: return v[0][1]
    for a, b in zip(v, v[1:]):
        if t <= b[0]: return a[1] + (b[1] - a[1]) * (t - a[0]) / max(1e-6, b[0] - a[0])
    return v[-1][1]

def _where(p):
    """Rough position of a part, for the camera check."""
    if 'pts' in p and isinstance(p['pts'], list) and p['pts'] and _pt(p['pts'][0]): xs = [q[0] for q in p['pts'] if _pt(q)]; ys = [q[1] for q in p['pts'] if _pt(q)]; return min(xs), max(xs), min(ys), max(ys)
    if 'x0' in p: return p.get('x0', 0), p.get('x1', 0), p.get('y0', 0), _at(p.get('level'), 1e9, p.get('y0', 0))
    if 'from' in p and _pt(p.get('from')) and _pt(p.get('to')): return min(p['from'][0], p['to'][0]), max(p['from'][0], p['to'][0]), min(p['from'][1], p['to'][1]), max(p['from'][1], p['to'][1])
    x = _at(p.get('x'), 0, 0); y = _at(p.get('y'), 0, 0)
    if p.get('type') == 'tower': return x - 90, x + 90, y, y + p.get('legH', 240) + p.get('h', 130)
    return x, x + (_at(p.get('w'), 0, 0) if p.get('type') in ('rect', 'house') else 0), y, y + (_at(p.get('h'), 0, 0) if p.get('type') in ('rect', 'house') else 0)

def check(spec):
    E = []
    if not isinstance(spec, dict): return ['the description must be one JSON object']
    D = spec.get('duration')
    if not _num(D) or not 20 <= D <= 50: E.append('duration must be a number of seconds between 20 and 50'); D = 33.6
    if not isinstance(spec.get('title'), str) or not 3 <= len(spec['title']) <= 70: E.append('title must be a short text')
    steps = spec.get('steps')
    if not isinstance(steps, list) or not 5 <= len(steps) <= 9: E.append('steps must be a list of 5 to 9 steps'); steps = []
    last = -1.0
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict) or not _num(s.get('start')) or not _num(s.get('end')): E.append('step %d needs start and end times' % i); continue
        if s['start'] < last - 0.01: E.append('step %d starts before step %d ends' % (i, i - 1))
        if s['end'] <= s['start'] or s['end'] > D + 0.01: E.append('step %d: end must be after start and within the duration' % i)
        last = s['end']
        say = s.get('say'); lab = s.get('label')
        if not isinstance(lab, str) or not 2 <= len(lab) <= 16: E.append('step %d: label must be 2 to 16 letters' % i)
        if not isinstance(say, str): E.append('step %d needs a "say" sentence' % i); continue
        w = len(say.split())
        if not 4 <= w <= 18: E.append('step %d: "say" must be 4 to 18 words (it has %d)' % (i, w))
        if w / 3.3 > (s['end'] - s['start']) + 0.4: E.append('step %d: the sentence is too long to speak in %.1f seconds; cut it to about %d words' % (i, s['end'] - s['start'], int((s['end'] - s['start']) * 3.3)))
    cam = spec.get('camera')
    if not isinstance(cam, list) or len(cam) < 3 or not all(isinstance(c, list) and len(c) == 4 and all(_num(v) for v in c) for c in cam): E.append('camera must be a list of at least 3 [time, x, y, zoom] entries'); cam = []
    else:
        if any(b[0] <= a[0] for a, b in zip(cam, cam[1:])): E.append('camera times must go up')
        if cam[0][0] > 0.5 or cam[-1][0] < D - 1.5: E.append('camera must start at time 0 and run to the end of the video')
        if any(not 0.45 <= c[3] <= 3.2 for c in cam): E.append('camera zoom must stay between 0.45 and 3.2')
    parts = spec.get('parts')
    if not isinstance(parts, list) or not 8 <= len(parts) <= 70: E.append('parts must be a list of 8 to 70 parts'); parts = []
    if parts and (not isinstance(parts[0], dict) or parts[0].get('type') != 'sky'): E.append('the first part must be the sky (background)')
    anim_times = []; movers = []
    for n, p in enumerate(parts, 1):
        if not isinstance(p, dict) or p.get('type') not in CATALOG: E.append('part %d: unknown type %r (allowed: %s)' % (n, p.get('type') if isinstance(p, dict) else p, ', '.join(CATALOG))); continue
        req, opt, _ = CATALOG[p['type']]; tag = 'part %d (%s)' % (n, p['type'])
        for f in req:
            if f not in p: E.append('%s is missing "%s"' % (tag, f))
        moving = False
        for f, v in p.items():
            if f == 'type': continue
            if f not in req and f not in opt: E.append('%s has a field the engine does not know: "%s"' % (tag, f)); continue
            if f in POINT_LISTS:
                if not (isinstance(v, list) and len(v) >= 2 and all(_pt(q) for q in v)): E.append('%s: "%s" must be a list of [x,y] points' % (tag, f))
                elif any(abs(q[0]) > 1400 or not -500 <= q[1] <= 950 for q in v): E.append('%s: a point is far outside the stage' % tag)
            elif f in POINTS:
                if not _pt(v): E.append('%s: "%s" must be one [x,y] point' % (tag, f))
            elif f in ANIM:
                if _num(v): pass
                elif _kfs(v):
                    ts = [k[0] for k in v]
                    if any(b < a for a, b in zip(ts, ts[1:])): E.append('%s: times in "%s" must go up' % (tag, f))
                    if ts[0] < -0.01 or ts[-1] > D + 0.6: E.append('%s: "%s" has a time outside the video' % (tag, f))
                    if len({k[1] for k in v}) > 1: moving = True; anim_times += ts
                else: E.append('%s: "%s" must be a number or keyframes [[time, value], ...]' % (tag, f))
            elif f in ('x0', 'x1', 'legH', 'lw', 'size', 'teeth', 'dir', 'head', 'floor') and not _num(v): E.append('%s: "%s" must be a number' % (tag, f))
            elif f in ('fill', 'stroke', 'color', 'bg', 'text', 'preset', 'kind', 'wall', 'roof', 'rgb') and not isinstance(v, str): E.append('%s: "%s" must be text' % (tag, f))
        if p['type'] == 'label' and isinstance(p.get('text'), str) and len(p['text']) > 18: E.append('%s: label text is too long (max 16 letters)' % tag)
        for f in ('x', 'y'):
            v = p.get(f)
            for val in ([v] if _num(v) else [k[1] for k in v] if _kfs(v) else []):
                if (f == 'x' and abs(val) > 1400) or (f == 'y' and not -500 <= val <= 950): E.append('%s: %s=%s is far outside the stage' % (tag, f, val)); break
        if moving: movers.append(p)
    if parts and len(movers) < 6: E.append('too little movement: only %d parts change over time; a living scene needs at least 6' % len(movers))
    cam_times = [c[0] for c in cam]
    for i, s in enumerate(steps, 1):
        if not (isinstance(s, dict) and _num(s.get('start')) and _num(s.get('end'))): continue
        a, b = s['start'] - 0.4, s['end']
        if sum(1 for t in anim_times + cam_times if a <= t <= b) < 2: E.append('step %d: nothing changes on screen during this step; make something move, fill, grow or appear between %.1f and %.1f' % (i, s['start'], s['end']))
        if cam:   # the camera must be looking at something that is changing in this step
            mid = (s['start'] + s['end']) / 2; cx = _at([[c[0], c[1]] for c in cam], mid); cy = _at([[c[0], c[2]] for c in cam], mid); z = _at([[c[0], c[3]] for c in cam], mid)
            vx0, vx1, vy0, vy1 = cx - 360 / z, cx + 360 / z, cy - 520 / z, cy + 760 / z; seen = False
            for p in movers:
                act = any(a <= k[0] <= b for f, v in p.items() if f in ANIM and _kfs(v) for k in v)
                if not act: continue
                x0, x1, y0, y1 = _where(p)
                if x1 >= vx0 and x0 <= vx1 and y1 >= vy0 and y0 <= vy1: seen = True; break
            if not seen and any(any(a <= k[0] <= b for f, v in p.items() if f in ANIM and _kfs(v) for k in v) for p in movers):
                E.append('step %d: the camera (centre %d,%d zoom %.2f) is not pointing at the thing that moves in this step' % (i, cx, cy, z))
    for n, c in enumerate(spec.get('sfx', []) or [], 1):
        if not (isinstance(c, list) and len(c) >= 2 and _num(c[0]) and isinstance(c[1], str)): E.append('sound %d must be [time, name, loudness]' % n); continue
        if c[1] not in SOUNDS: E.append('sound %d: unknown sound %r (allowed: %s)' % (n, c[1], ', '.join(sorted(SOUNDS))))
        if not 0 <= c[0] <= D: E.append('sound %d: time is outside the video' % n)
        if len(c) > 2 and not (_num(c[2]) and 0 < c[2] <= 1.2): E.append('sound %d: loudness must be between 0 and 1.2' % n)
        if len(c) > 3:
            if c[1] in SOUNDS_DUR and not (_num(c[3]) and 0.1 <= c[3] <= 6): E.append('sound %d: length must be 0.1 to 6 seconds' % n)
            elif c[1] in SOUNDS_FREQ and not (_num(c[3]) and 100 <= c[3] <= 4000): E.append('sound %d: pitch must be 100 to 4000' % n)
            elif c[1] not in SOUNDS_DUR and c[1] not in SOUNDS_FREQ: E.append('sound %d: %s takes no 4th value' % (n, c[1]))
        if len(c) > 4: E.append('sound %d has too many values' % n)
    if isinstance(spec.get('sfx'), list) and len(spec['sfx']) < 6: E.append('add more sounds: at least 6, one for each action on screen')
    return E

if __name__ == '__main__':
    errs = check(json.loads(Path(sys.argv[1]).read_text()))
    print('\n'.join(errs) if errs else 'OK'); sys.exit(1 if errs else 0)
