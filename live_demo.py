"""MindLore 'LIVE DEMO' look: the picture acts out the script as it is spoken. Fast beats (new visual every ~1.5-3 s), emoji stickers on key words,
funny reaction beats, loop ending. A 'director' (free LLM, rule-based fallback) turns any story script into a scene plan from a fixed toolkit.
  python live_demo.py <story.json> <out.mp4>      FAKE=1 silent timing for local look-tests, DUMP=2,5,9 saves PNG frames
Test-only until the roll-out in ROADMAP-LIVE.md (section L)."""
import asyncio, json, math, os, re, subprocess, sys, bisect, random
from pathlib import Path
from PIL import Image
import brain_demo as B
from brain_demo import Cv, emoji, mix, ease, back, lerp, clamp, CW, CH, K, FPS, INK, ACC, PAPER, font

KINDS = {'title_slam': 'text (<=3 words), emoji', 'icon_burst': 'emoji, text (label, 1-3 words)', 'counter': 'value (number that appears in narration), unit (e.g. % or "x" or ""), text (label), emoji, start (optional)',
         'chart': 'shape (decay|rise|bars), text (label), to (end percent), values (bars: 2-4 numbers), labels (bars: 2-4 short names), emoji', 'slots': 'items (2-4 emoji), over (emoji that overflows), text',
         'flow': 'a (emoji), b (emoji), la (label), lb (label), dot (emoji), text', 'versus': 'a (emoji), b (emoji), la, lb, win (a|b), text', 'meter': 'text, emoji, frm (0-1), to (0-1)',
         'reaction': 'emoji (face), text (funny quip, <=6 words, kind, never mocking people)', 'brain': 'regions (list from front,parietal,occip,temporal,hippo), text'}
PALS = [((247, 240, 225), (224, 86, 60), INK), ((24, 40, 96), (255, 205, 70), (255, 255, 255)), ((18, 90, 96), (255, 150, 120), (255, 255, 255)),
        ((70, 30, 110), (255, 214, 110), (255, 255, 255)), ((255, 224, 120), (40, 60, 160), INK), ((30, 30, 40), (90, 230, 170), (255, 255, 255)), ((226, 244, 236), (200, 60, 90), INK)]
KEY = {'brain': '🧠', 'memory': '🧠', 'stress': '😰', 'fear': '😨', 'money': '💰', 'dollar': '💵', 'happy': '😊', 'happiness': '😊', 'sleep': '😴', 'dream': '💭', 'dreams': '💭', 'time': '⏰', 'clock': '⏰', 'deadline': '⏳',
       'phone': '📱', 'social': '📱', 'friends': '👫', 'friend': '👫', 'lonely': '🥺', 'loneliness': '🥺', 'music': '🎵', 'work': '💼', 'office': '🏢', 'nature': '🌳', 'tree': '🌳', 'danger': '⚠️', 'risk': '🎲', 'heart': '❤️', 'kind': '🤝',
       'kindness': '🤝', 'doodle': '✏️', 'doodles': '✏️', 'creative': '🎨', 'language': '🗣️', 'learn': '📚', 'learning': '📚', 'study': '📚', 'focus': '🎯', 'attention': '👀', 'distracted': '🔔', 'multitask': '🤹', 'multitasking': '🤹',
       'boredom': '🥱', 'bored': '🥱', 'brain.': '🧠', 'study.': '📊', 'research': '🔬', 'scientists': '🔬', 'experiment': '🧪', 'ancient': '🏛️', 'hunter': '🏹', 'savanna': '🌍', 'cortisol': '🧪', 'hormone': '🧪', 'energy': '⚡',
       'mood': '🎭', 'emotion': '🎭', 'emotions': '🎭', 'mirror': '🪞', 'strangers': '🧍', 'crowd': '👥', 'crowds': '👥', 'rest': '🛋️', 'break': '☕', 'coffee': '☕', 'forgot': '😵', 'forget': '😵', 'danger.': '⚠️'}
QUIPS = [('😳', 'Wait, what?!'), ('🤯', 'Mind. Blown.'), ('😅', 'Oops. That is us.'), ('🙃', 'Plot twist!'), ('😬', 'Awkward...'), ('🤨', 'Sure, Jan.'), ('💀', 'Brain: dead.'), ('😮', 'Okay WOW.')]
NUMW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'ten': 10, 'half': 50, 'hundred': 100}

# ---------- helpers ----------
def wrap(c, t, sz, maxw):
    out, cur = [], ''
    for w in t.split():
        n = (cur + ' ' + w).strip()
        if c.tw(n, sz) <= maxw or not cur: cur = n
        else: out.append(cur); cur = w
    return out + ([cur] if cur else [])
def ctext(c, x, y, t, sz, col, maxw=640, stroke=0, scol=PAPER, lh=1.12):
    ls = wrap(c, t, sz, maxw)
    while len(ls) > 1 and sz > 28 and max(c.tw(l, sz) for l in ls) > maxw: sz -= 4; ls = wrap(c, t, sz, maxw)
    y0 = y - (len(ls) - 1) * sz * lh / 2
    for i, l in enumerate(ls): c.text(x, y0 + i * sz * lh, l, sz, col, 'mm', stroke, scol)
    return len(ls) * sz * lh
def emo(c, ch, x, y, sz, a=1.0, rot=0):
    if ch and sz > 2: c.emo(ch, x, y, sz, a, rot)

# ---------- beat drawers: f(c, b, lt, T, bg, acc, ink) ----------
def d_title(c, b, lt, T, bg, acc, ink):
    ws = (b.get('text') or '').upper().split() or ['WAIT']
    lines = [' '.join(ws[i:i + 2]) for i in range(0, len(ws), 2)]
    emo(c, b.get('emoji'), 360 + 8 * math.sin(lt * 20), 330 + 6 * math.sin(lt * 7), 300 * back(lt / .3))
    for i, l in enumerate(lines):
        u = back((lt - i * .16) / .22)
        if u > 0:
            sz = 150
            while c.tw(l, sz) > 650 and sz > 40: sz -= 6
            c.text(360 + 5 * math.sin(lt * 30) * (1 - ease(lt / .5)), 700 + i * 175, l, sz * u, acc if i % 2 == 0 else ink, 'mm', 5, bg if bg != acc else PAPER)
def d_icon(c, b, lt, T, bg, acc, ink):
    for i in range(16):
        a = i / 16 * 2 * math.pi + lt * .5
        c.d.polygon([(360 * K, 560 * K), ((360 + 900 * math.cos(a - .09)) * K, (560 + 900 * math.sin(a - .09)) * K), ((360 + 900 * math.cos(a + .09)) * K, (560 + 900 * math.sin(a + .09)) * K)], fill=mix(bg, acc, .18) if i % 2 else mix(bg, acc, .08))
    emo(c, b.get('emoji'), 360, 560 + 10 * math.sin(lt * 4), 360 * back(lt / .3), 1, int(8 * math.sin(lt * 5)))
    for i in range(3):
        a = lt * 1.6 + i * 2.09; emo(c, b.get('emoji'), 360 + 270 * math.cos(a), 560 + 150 * math.sin(a), 90 * ease(lt / .5), .85)
    ctext(c, 360, 900, (b.get('text') or '').upper(), 82 * back((lt - .1) / .25), acc, 640, 5, bg)
def d_counter(c, b, lt, T, bg, acc, ink):
    v0 = float(b.get('start') or 0); v1 = float(b.get('value') or 0); u = ease(lt / min(1.2, T * .65)); v = lerp(v0, v1, u)
    unit = b.get('unit') or ''; s = ('%d' % round(v)) if abs(v1 - round(v1)) < 1e-6 else ('%.1f' % v)
    big = 1 + .1 * math.exp(-max(0, lt - min(1.2, T * .65)) * 8) * (lt > min(1.2, T * .65))
    emo(c, b.get('emoji'), 360, 330 + 10 * math.sin(lt * 5), 240 * back(lt / .3))
    c.text(360, 620, s + unit, min(260, 760 / max(1, len(s + unit)) * 1.55) * big, acc, 'mm', 6, bg)
    ctext(c, 360, 860, (b.get('text') or '').upper(), 58, ink, 620)
def d_chart(c, b, lt, T, bg, acc, ink):
    x0, y0, x1, y1 = 100, 420, 640, 900; panel = mix(bg, (255, 255, 255), .85 if sum(bg) > 400 else .1)
    c.rr(50, 330, 670, 960, 26, panel, ink, 4); ctext(c, 360, 375, (b.get('text') or '').upper(), 34, ink, 580)
    emo(c, b.get('emoji'), 600, 250, 100 * back(lt / .3))
    c.line([(x0, y0), (x0, y1), (x1, y1)], 6, ink); p = ease(lt / max(.8, T * .7)); sh = b.get('shape', 'decay'); to = float(b.get('to') or 40)
    if sh == 'bars':
        vals = [float(x) for x in (b.get('values') or [30, 70])][:4]; labs = (b.get('labels') or [''] * 4); m = max(vals) or 1; n = len(vals); wd = (x1 - x0 - 30) / n
        for i, v in enumerate(vals):
            h = (y1 - y0 - 40) * v / m * ease((lt - i * .25) / .6); bx = x0 + 15 + i * wd
            c.rr(bx + 8, y1 - h, bx + wd - 8, y1, 10, [acc, (60, 110, 220), (90, 200, 140), (250, 190, 60)][i % 4], ink, 3)
            if h > 20: c.text(bx + wd / 2, y1 - h - 22, ('%g' % v), 32, ink)
            c.text(bx + wd / 2, y1 + 28, str(labs[i] if i < len(labs) else '')[:12], 24, ink)
        return
    pts = []
    for i in range(int(p * 60) + 1):
        q = i / 60; R = (to + (100 - to) * math.exp(-4 * q)) if sh == 'decay' else (10 + (to - 10) / (1 + math.exp(-9 * (q - .5))))
        pts.append((x0 + q * (x1 - x0 - 20), y1 - 10 - R / 100 * (y1 - y0 - 40)))
    if len(pts) > 1: c.line(pts, 10, acc)
    if pts: c.ell(pts[-1][0], pts[-1][1], 14, 14, acc, ink, 3)
    R = (to + (100 - to) * math.exp(-4 * p)) if sh == 'decay' else (10 + (to - 10) / (1 + math.exp(-9 * (p - .5)))); c.text(520, y0 + 70, '%d%%' % round(R), 92, acc, 'mm', 4, panel)
def d_slots(c, b, lt, T, bg, acc, ink):
    items = (b.get('items') or ['📝', '📞', '🔑'])[:4]; cap = len(items); SP = 128; X0 = 360 - cap * SP / 2 + SP / 2 - SP / 2 + 0; X0 = 360 - (cap - 1) * SP / 2; y = 620
    c.rr(X0 - 80, y - 100, X0 + (cap - 1) * SP + 80, y + 100, 28, mix(bg, (255, 255, 255), .25), acc, 5)
    ctext(c, 360, y - 150, (b.get('text') or 'FULL CAPACITY').upper(), 38, ink, 640)
    t_ov = cap * .3 + .5; fall = max(0, lt - t_ov - .3); sh = ease(fall / .4)
    for i, ch in enumerate(items):
        u = back((lt - i * .3) / .3)
        if u <= 0: continue
        x = X0 + i * SP; yy = y; rot = 0; a = 1.0
        if i == 0 and fall > 0: x -= 60 * fall; yy += 1100 * fall * fall; rot = int(160 * fall); a = 1 - ease(fall / .9)
        elif i > 0: x -= sh * SP
        if a > .02: c.rr(x - 54 * u, yy - 54 * u, x + 54 * u, yy + 54 * u, 16, (255, 249, 214), INK, 4); emo(c, ch, x, yy, 70 * u, a, rot)
    if lt > t_ov - .3 and b.get('over'):
        u = ease((lt - t_ov + .3) / .4); x = lerp(860, X0 + (cap - 1) * SP + SP - sh * SP * 0 - SP * sh, u) if True else 0
        x = lerp(860, X0 + cap * SP - sh * SP, u); c.rr(x - 54, y - 54, x + 54, y + 54, 16, (255, 249, 214), ACC, 5); emo(c, b['over'], x, y, 70)
        if int(lt * 6) % 2 == 0 and fall < .2: c.text(360, y + 150, 'FULL!', 44, ACC, 'mm', 3, bg)
def d_flow(c, b, lt, T, bg, acc, ink):
    A, Bp = (360, 360), (360, 900); u = ease((lt - .35) / max(.6, T * .55)); arr = ease((lt - .2) / .3)
    c.line([A, (A[0], A[1] + (Bp[1] - A[1]) * arr)], 8, mix(bg, acc, .5))
    emo(c, b.get('a'), A[0], A[1], 200 * back(lt / .3)); emo(c, b.get('b'), Bp[0], Bp[1], 200 * back((lt - .1) / .3) * (1 + .15 * math.exp(-max(0, lt - .35 - max(.6, T * .55)) * 7) * (u >= 1)))
    c.text(A[0] + 150, A[1], (b.get('la') or '').upper(), 34, ink, 'lm'); c.text(Bp[0] + 150, Bp[1], (b.get('lb') or '').upper(), 34, ink, 'lm')
    if .35 <= lt:
        px = 360 + 120 * math.sin(u * math.pi); py = lerp(A[1] + 100, Bp[1] - 100, u)
        for k in range(6, 0, -1):
            uu = max(0, u - k * .04); c.ell(360 + 120 * math.sin(uu * math.pi), lerp(A[1] + 100, Bp[1] - 100, uu), 10, 10, mix(bg, acc, .6))
        if u < 1: c.ell(px, py, 40, 40, acc, ink, 3); emo(c, b.get('dot') or '✨', px, py, 50)
        else:
            r = (lt - .35 - max(.6, T * .55)) * 3; c.ell(Bp[0], Bp[1], 120 + 80 * r, 120 + 80 * r, None, acc, max(1, 8 - 6 * clamp(r)))
    ctext(c, 360, 1040, (b.get('text') or '').upper(), 40, ink, 640)
def d_versus(c, b, lt, T, bg, acc, ink):
    win = b.get('win', 'a'); t_w = .9
    for side, x in (('a', 190), ('b', 530)):
        w = (side == win); k = ease((lt - t_w) / .4); s = 220 * back((lt - (0 if side == 'a' else .15)) / .3) * (1 + .35 * k if w else 1 - .35 * k); a = 1.0 if w else 1 - .55 * k
        emo(c, b.get(side), x, 560, s, a); ctext(c, x, 780, (b.get('l' + side) or '').upper(), 36, ink, 300)
        if w and k > 0: emo(c, '👑', x, 390 - 20 * (1 - k), 110 * k)
    if lt > .35: c.text(360, 560, 'VS', 100 * back((lt - .35) / .25) * (1 - .6 * ease((lt - t_w) / .3)), acc, 'mm', 5, bg)
    ctext(c, 360, 1000, (b.get('text') or '').upper(), 42, ink, 640)
def d_meter(c, b, lt, T, bg, acc, ink):
    f, t_ = float(b.get('frm') or 0), float(b.get('to') or 1); u = ease((lt - .2) / max(.7, T * .6)); v = lerp(f, t_, u)
    c.rr(70, 600, 650, 700, 50, mix(bg, (255, 255, 255), .3), ink, 5)
    col = mix((230, 70, 60), (70, 200, 110), v); w = max(8, 560 * v); c.rr(80, 610, 80 + w, 690, 40, col, None, 0)
    emo(c, b.get('emoji'), 80 + w, 520 - 20 * abs(math.sin(lt * 6)), 150 * back(lt / .3)); c.text(360, 780, '%d%%' % round(v * 100), 110, acc, 'mm', 5, bg)
    ctext(c, 360, 940, (b.get('text') or '').upper(), 48, ink, 640)
def d_react(c, b, lt, T, bg, acc, ink):
    emo(c, b.get('emoji') or '😳', 360 + 10 * math.sin(lt * 35) * (1 - ease(lt / 1.2)), 470, 380 * back(lt / .25))
    if lt > .25:
        k = back((lt - .25) / .25); c.rr(360 - 300 * k, 760, 360 + 300 * k, 960, 36, (255, 255, 255), INK, 5); c.d.polygon([(330 * K, 760 * K), (400 * K, 760 * K), (350 * K, 700 * K)], fill=(255, 255, 255), outline=INK)
        c.d.rectangle([332 * K, 756 * K, 398 * K, 764 * K], fill=(255, 255, 255))
        if k > .7: ctext(c, 360, 860, b.get('text') or '', 64, INK, 520)
    emo(c, '💦' if lt > .5 else None, 520, 330, 80 * ease((lt - .5) / .3))
def d_brain(c, b, lt, T, bg, acc, ink):
    class S:
        z = 1.5 + .08 * ease(lt / T)
        def __call__(s, x, y): return ((x - 20) * s.z + 360, (y + 70) * s.z + 540)
    s = S(); g = {}
    for r in b.get('regions') or ['front']: g[r] = ease(lt / .4) * (.7 + .3 * math.sin(lt * 6))
    B.brain_draw(c, s, g, lt); ctext(c, 360, 960, (b.get('text') or '').upper(), 46, ink, 640)
DRAW = {'title_slam': d_title, 'icon_burst': d_icon, 'counter': d_counter, 'chart': d_chart, 'slots': d_slots, 'flow': d_flow, 'versus': d_versus, 'meter': d_meter, 'reaction': d_react, 'brain': d_brain}

# ---------- director ----------
def numval(w):
    w = w.lower().strip('.,;:!?'); m = re.fullmatch(r'\$?(\d+(?:\.\d+)?)(%?)', w)
    if m: return float(m.group(1)), ('%' if m.group(2) else '')
    return (NUMW[w], '') if w in NUMW else None
def rule_director(words):
    n = len(words); beats = []; i = 0; k = 0; rnd = random.Random(7)
    while i < n:
        j = i
        while j < n and (j - i < 9 and not (j - i >= 4 and re.search(r'[.!?,;:]$', words[j]['w']))): j += 1
        j = min(n, j + 1); chunk = words[i:j]; txt = ' '.join(w['w'] for w in chunk); kind = None
        nums = [(q, numval(w['w'])) for q, w in enumerate(chunk) if numval(w['w'])]
        keys = [(q, KEY[clean(w['w'])]) for q, w in enumerate(chunk) if clean(w['w']) in KEY]
        short = ' '.join(re.sub(r'[^\w%$\'-]', '', w['w']) for w in chunk[-3:])
        if k == 0: kind = {'kind': 'title_slam', 'text': ' '.join(re.sub(r'[^\w%$\']', '', w['w']) for w in chunk[:3]), 'emoji': keys[0][1] if keys else '🧠'}
        elif nums and k % 2 == 1: v, u = nums[0][1]; kind = {'kind': 'counter', 'value': v, 'unit': u, 'text': short, 'emoji': keys[0][1] if keys else '📊'}
        elif k % 6 == 5: e, q = QUIPS[rnd.randrange(len(QUIPS))]; kind = {'kind': 'reaction', 'emoji': e, 'text': q}
        elif keys: kind = {'kind': 'icon_burst', 'emoji': keys[0][1], 'text': ' '.join(re.sub(r'[^\w%$\'-]', '', w['w']) for w in chunk[max(0, keys[0][0] - 1):keys[0][0] + 2])}
        else: kind = {'kind': 'title_slam', 'text': short, 'emoji': (keys[0][1] if keys else rnd.choice(['💡', '✨', '👀', '🤔', '🔥']))}
        kind['at'] = i; beats.append(kind); i = j; k += 1
    return beats
def llm_director(words, total):
    try:
        import llm
        if not llm.available(): return None
        narr = ' '.join('%d:%s' % (i, w['w']) for i, w in enumerate(words)); want = max(8, int(total / 2.2))
        sysm = 'You are a viral short-video director for a psychology channel. Reply JSON only.'
        usr = ('Plan a fast, funny, creative explainer video whose pictures ACT OUT the narration live, in sync with the words.\nNarration with word indexes (index:word):\n%s\n\n'
               'Toolkit (kind: params):\n%s\n\nRules: about %d beats; each beat has "at" = word index where it starts (strictly increasing, first is 0; a new visual every 1.5-3 seconds); the first beat is a title_slam hook of <=3 words. '
               'Use a VARIETY of kinds, at least 3 different besides title_slam; at least 2 reaction beats with kind, clean, funny quips (<=6 words, never mocking people). '
               'Numbers/stats in counter/chart/meter MUST come from the narration, never invent facts. Emoji must be single emoji characters. Every beat may also have "tag" (<=3 word label) and "sticker" (one emoji popped on a key word). '
               'Make the visuals literally show what is being said (e.g. a memory slot overflowing, a bar filling, a thing travelling from A to B, two things competing). Output {"beats":[{"at":0,"kind":"title_slam","text":"...","emoji":"..."}, ...]}'
               % (narr, '\n'.join('- %s: %s' % kv for kv in KINDS.items()), want))
        r = llm.json_call(sysm, usr, temperature=0.8, max_tokens=5000) if 'max_tokens' in llm.json_call.__code__.co_varnames or True else None
        bs = (r or {}).get('beats') or []; out = []; last = -1
        for b in bs:
            if not isinstance(b, dict) or b.get('kind') not in KINDS: continue
            try: a = int(b['at'])
            except Exception: continue
            if a <= last or a >= len(words): continue
            if out and words[a]['s'] - words[out[-1]['at']]['s'] < 1.0: continue
            b['at'] = a; out.append(b); last = a
        if out: out[0]['at'] = 0
        kinds = {b['kind'] for b in out}
        return out if len(out) >= total / 4.5 and len(kinds) >= 3 else None
    except Exception as e:
        print('llm_director failed:', str(e)[:200]); return None
def clean(w): return B.clean(w)

# ---------- render ----------
def stages(beats, words, total):
    st = []
    for i, b in enumerate(beats): st.append(0.0 if i == 0 else words[b['at']]['s'])
    return st
def frame(t, beats, starts, words, total, wstarts):
    i = max(0, bisect.bisect_right(starts, t) - 1); b = beats[i]; lt = t - starts[i]; T = (starts[i + 1] if i + 1 < len(starts) else total) - starts[i]
    bg, acc, ink = PALS[b['_pal']]; c = Cv(bg)
    # wipe from previous palette
    if i > 0 and lt < .2:
        pb = PALS[beats[i - 1]['_pal']][0]; k = ease(lt / .2); c.d.rectangle([0, 0, CW * K, CH * K], fill=pb)
        x = int(CW * K * k) if i % 2 else int(CW * K * (1 - k)); c.d.rectangle([0, 0, x, CH * K] if i % 2 else [x, 0, CW * K, CH * K], fill=bg)
    for gx in range(0, 760, 120):
        for gy in range(0, 1320, 120): c.ell(gx + (t * 14) % 120, gy, 4, 4, mix(bg, acc, .12))
    if b.get('tag'): w_ = c.tw(b['tag'].upper(), 30) + 50; c.rr(360 - w_ / 2, 100, 360 + w_ / 2, 152, 26, acc, INK, 4); c.text(360, 126, b['tag'].upper(), 30, bg if sum(acc) > 400 else (255, 255, 255))
    DRAW[b['kind']](c, b, lt, T, bg, acc, ink)
    if b.get('sticker') and lt < 1.4: k = back(lt / .25) * (1 - ease((lt - 1.1) / .3)); c.emo(b['sticker'], 620, 210, 120 * k, 1.0, int(12 * math.sin(lt * 14) * (1 - lt / 1.4)))
    im = c.im; z = 1 + .07 * math.exp(-lt * 9) + (.02 * math.sin(t * 2.2) if b['kind'] != 'reaction' else .0)
    sx = sy = 0
    if b['kind'] == 'reaction' and lt < .8: sx, sy = 10 * math.sin(lt * 50) * (1 - lt / .8) * K, 8 * math.cos(lt * 43) * (1 - lt / .8) * K
    if z > 1.001 or sx or sy:
        w, h = im.size; cw, ch = w / z, h / z; l = (w - cw) / 2 + sx; tp = (h - ch) / 2 + sy; im = im.resize((w, h), Image.BICUBIC, box=(l, tp, l + cw, tp + ch))
    c.im = im; c.d = B.ImageDraw.Draw(im)
    c.text(40, 60, 'MINDLORE', 30, ink, 'lm')
    wi = max(0, bisect.bisect_right(wstarts, t) - 1)
    if t >= words[0]['s']:
        st = wi
        while st > 0 and not re.search(r'[.?!,]$', words[st - 1]['w']) and wi - st < 5: st -= 1
        seg = words[st:wi + 1]; sz = 40; full = ' '.join(w['w'] for w in seg)
        if c.tw(full, sz) > 650: sz = 40 * 650 / c.tw(full, sz)
        x = 360 - c.tw(full, sz) / 2
        for j, w in enumerate(seg):
            on = st + j == wi; c.d.text((x * K, 1190 * K), w['w'] + ' ', font=font(sz), fill=acc if on else ink, anchor='lm', stroke_width=int(4 * K), stroke_fill=bg); x += c.tw(w['w'] + ' ', sz)
    c.d.rectangle([40 * K, 1250 * K, (CW - 40) * K, 1258 * K], fill=mix(bg, (150, 150, 160), .5)); c.d.rectangle([40 * K, 1250 * K, (40 + (CW - 80) * clamp(t / total)) * K, 1258 * K], fill=acc)
    return c.im.resize((CW, CH), Image.LANCZOS)

def build(story, outp):
    d = json.load(open(story)); text = ' '.join(s['narration'] for s in d['sections']).replace('‑', '-').replace('–', '-')
    B.TEXT = text; words, mp3 = B.get_words(); total = words[-1]['e'] + 1.0
    for w in words: w['w'] = w['w']
    beats = llm_director(words, total); src = 'llm'
    if not beats: beats = rule_director(words); src = 'rules'
    if beats[-1]['kind'] != 'title_slam': beats.append({'at': max(beats[-1]['at'] + 1, len(words) - 3), 'kind': 'title_slam', 'text': 'AGAIN?', 'emoji': '🔁'}) if words[-1]['s'] - words[beats[-1]['at']]['s'] > 2.4 else None
    last = -1; prev = -1
    for b in beats:
        p = (prev + 1 + random.Random(b['at']).randrange(len(PALS) - 1)) % len(PALS)
        while p == prev: p = (p + 1) % len(PALS)
        b['_pal'] = prev = p
    starts = stages(beats, words, total); wst = [w['s'] for w in words]
    print('director:', src, 'beats:', len(beats), 'kinds:', sorted({b['kind'] for b in beats}), 'secs:', round(total, 1), flush=True)
    dump = [float(x) for x in os.environ.get('DUMP', '').split(',') if x]
    for tt in dump: frame(tt, beats, starts, words, total, wst).save(Path(outp).parent / ('ld_%05.1f.png' % tt))
    if dump: return
    args = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (CW, CH), '-r', str(FPS), '-i', '-'] + (['-i', str(mp3)] if mp3 else [])
    args += ['-vf', 'scale=1080:1920:flags=lanczos', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p'] + (['-c:a', 'aac', '-b:a', '160k', '-shortest'] if mp3 else ['-an']) + [str(outp)]
    ff = subprocess.Popen(args, stdin=subprocess.PIPE)
    for f in range(int(total * FPS)): ff.stdin.write(frame(f / FPS, beats, starts, words, total, wst).tobytes())
    ff.stdin.close(); ff.wait()
    Path(str(outp) + '.plan.json').write_text(json.dumps({'director': src, 'title': d.get('public_title'), 'seconds': round(total, 1), 'beats': [{k: v for k, v in b.items() if k != '_pal'} for b in beats]}, indent=1))

if __name__ == '__main__':
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True); build(sys.argv[1], sys.argv[2])
