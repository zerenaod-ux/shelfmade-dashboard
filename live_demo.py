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
         'reaction': 'emoji (face), text (funny quip, <=6 words, kind, never mocking people)', 'brain': 'regions (list from front,parietal,occip,temporal,hippo), text',
         'search': 'text (a search-bar question typed live, <=7 words, lowercase), emoji (top result)', 'chat': 'msgs (2-4 short text-message lines, <=7 words each, plain letters), emoji (avatar)',
         'headline': 'text (newspaper headline <=8 words), emoji', 'countdown': 'text (<=3 words shown after 3-2-1), emoji', 'timeline': 'items (2-4 emoji), labels (2-4 words each, no digits unless in narration), text',
         'scale': 'a (emoji), b (emoji), la, lb, heavy (a|b), text', 'crowd': 'emoji (the crowd icon), pick (emoji of the one who stands out), text', 'checklist': 'items (2-4 short lines, <=4 words), text',
         'before_after': 'a (emoji), b (emoji), la (before label), lb (after label), text', 'notif': 'items (2-4 short notification lines <=5 words), emoji', 'zoom': 'emoji (big object), labels (2-4 callout words), text',
         'clock': 'emoji, text (time passing / waiting / late-night type of idea)'}
OPENERS = ['search', 'headline', 'chat', 'countdown', 'notif', 'zoom', 'title_slam', 'icon_burst', 'clock']
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


MOOD = {'😳': 'shock', '🤯': 'blown', '😅': 'sweat', '🙃': 'smirk', '😬': 'grimace', '🤨': 'brow', '💀': 'dead', '😮': 'wow', '😂': 'laugh', '😱': 'shock', '😵': 'dead', '🤔': 'brow', '😏': 'smirk', '😰': 'sweat'}
def mascot(c, cx, cy, s, mood, lt):
    """Recurring character 'Brainy': a pink brain with big eyes that reacts (consistent mascot = viewers come back)."""
    PINK = (246, 196, 204); DK = (214, 140, 158); bob = 8 * math.sin(lt * 7); cy += bob
    for (dx, dy, rx, ry) in [(-95, -40, 120, 105), (95, -40, 120, 105), (0, -85, 135, 90), (0, 30, 175, 120)]: c.ell(cx + dx * s, cy + dy * s, (rx + 7) * s, (ry + 7) * s, INK)
    for (dx, dy, rx, ry) in [(-95, -40, 120, 105), (95, -40, 120, 105), (0, -85, 135, 90), (0, 30, 175, 120)]: c.ell(cx + dx * s, cy + dy * s, rx * s, ry * s, PINK)
    for a in (-60, 0, 60): c.line([(cx + (a - 20) * s, cy - 120 * s), (cx + a * s, cy - 90 * s), (cx + (a + 20) * s, cy - 120 * s)], 6 * s, DK)
    ex = 62 * s; ey = cy + 5 * s; er = 44 * s
    for sx in (-1, 1):
        c.ell(cx + sx * ex, ey, er, er * (1.15 if mood in ('shock', 'blown', 'wow') else 1), (255, 255, 255), INK, 5)
        pr = er * (.28 if mood in ('shock', 'blown') else .45); off = 10 * s * math.sin(lt * 9) if mood in ('sweat', 'shock') else 0
        if mood == 'dead':
            for k in (-1, 1): c.line([(cx + sx * ex - 20 * s, ey - 20 * s * k), (cx + sx * ex + 20 * s, ey + 20 * s * k)], 7 * s, INK)
        else: c.ell(cx + sx * ex + off + (8 * s if mood == 'brow' else 0), ey + (6 * s if mood != 'smirk' else 0), pr, pr, INK)
    if mood in ('brow', 'smirk'): c.line([(cx - ex - 40 * s, ey - 60 * s), (cx - ex + 40 * s, ey - 74 * s)], 8 * s, INK); c.line([(cx + ex - 40 * s, ey - 74 * s), (cx + ex + 40 * s, ey - 50 * s)], 8 * s, INK)
    my = cy + 95 * s
    if mood in ('shock', 'wow', 'blown'): c.ell(cx, my, 30 * s, 38 * s * (1 + .15 * math.sin(lt * 12)), (120, 40, 50), INK, 5)
    elif mood == 'laugh': c.ell(cx, my - 10 * s, 55 * s, 40 * s, (120, 40, 50), INK, 5)
    elif mood == 'grimace': c.line([(cx - 55 * s, my), (cx - 20 * s, my + 8 * s), (cx + 20 * s, my - 8 * s), (cx + 55 * s, my)], 8 * s, INK)
    elif mood == 'smirk': c.line([(cx - 40 * s, my + 8 * s), (cx + 10 * s, my + 8 * s), (cx + 50 * s, my - 14 * s)], 8 * s, INK)
    elif mood == 'dead': c.line([(cx - 40 * s, my), (cx + 40 * s, my)], 8 * s, INK)
    else: c.line([(cx - 45 * s, my - 5 * s), (cx, my + 12 * s), (cx + 45 * s, my - 5 * s)], 8 * s, INK)
    if mood in ('sweat', 'shock', 'grimace'): drop = (lt * 160) % 90; emo(c, '💦', cx + 150 * s, cy - 70 * s + drop * .5, 70 * s)
    if mood == 'blown': emo(c, '💥', cx, cy - 190 * s, 150 * s * back(lt / .3))

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
    R = (to + (100 - to) * math.exp(-4 * p)) if sh == 'decay' else (10 + (to - 10) / (1 + math.exp(-9 * (p - .5)))); (None if b.get('hide') else c.text(520, y0 + 70, '%d%%' % round(R), 92, acc, 'mm', 4, panel))
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
    emo(c, b.get('emoji'), 80 + w, 520 - 20 * abs(math.sin(lt * 6)), 150 * back(lt / .3)); (None if b.get('hide') else c.text(360, 780, '%d%%' % round(v * 100), 110, acc, 'mm', 5, bg))
    ctext(c, 360, 940, (b.get('text') or '').upper(), 48, ink, 640)
def d_react(c, b, lt, T, bg, acc, ink):
    mood = MOOD.get(b.get('emoji') or '😳', 'shock')
    mascot(c, 360 + 10 * math.sin(lt * 35) * (1 - ease(lt / 1.2)), 470, 1.25 * back(lt / .25), mood, lt)
    if lt > .25:
        k = back((lt - .25) / .25); c.rr(360 - 300 * k, 760, 360 + 300 * k, 960, 36, (255, 255, 255), INK, 5); c.d.polygon([(330 * K, 760 * K), (400 * K, 760 * K), (350 * K, 700 * K)], fill=(255, 255, 255), outline=INK)
        c.d.rectangle([332 * K, 756 * K, 398 * K, 764 * K], fill=(255, 255, 255))
        if k > .7: ctext(c, 360, 860, b.get('text') or '', 64, INK, 520)
def d_brain(c, b, lt, T, bg, acc, ink):
    class S:
        z = 1.5 + .08 * ease(lt / T)
        def __call__(s, x, y): return ((x - 20) * s.z + 360, (y + 70) * s.z + 540)
    s = S(); g = {}
    for r in b.get('regions') or ['front']: g[r] = ease(lt / .4) * (.7 + .3 * math.sin(lt * 6))
    B.brain_draw(c, s, g, lt); ctext(c, 360, 960, (b.get('text') or '').upper(), 46, ink, 640)

def _s(v, n=40): return re.sub(r'[^\x20-\x7e]', '', str(v if v is not None else ''))[:n]
def _l(v, n=4, m=34):
    if isinstance(v, str): v = [v]
    return [_s(x if not isinstance(x, dict) else (x.get('text') or x.get('label') or ''), m) for x in (v or []) if x][:n]
def d_search(c, b, lt, T, bg, acc, ink):
    q = _s(b.get('text') or 'why do we do this', 36); k = back(lt / .3); tt = max(.9, T * .5); n = int(clamp(lt / tt) * len(q)); sz = 36
    while c.tw(q, sz) > 440 and sz > 18: sz -= 2
    c.rr(50, 420 + 20 * (1 - k), 670, 530 + 20 * (1 - k), 54, (255, 255, 255), INK, 5); emo(c, '🔍', 110, 475, 58 * k)
    c.text(160, 478, q[:n] + ('|' if int(lt * 3) % 2 == 0 and n < len(q) + 1 else ''), sz, INK, 'lm')
    for i in range(3):
        u = back((lt - tt - .15 - i * .18) / .25)
        if u <= 0: continue
        y = 660 + i * 160; hot = i == 0
        c.rr(60, y - 60 * u, 660, y + 60 * u, 28, acc if hot else (255, 255, 255), INK, 4)
        if u > .6:
            emo(c, (b.get('emoji') or '💡') if hot else ['📄', '📰'][i - 1], 130, y, 70 * u)
            c.rr(190, y - 26, 580 - 60 * i, y - 10, 8, (255, 255, 255) if hot else (205, 205, 210)); c.rr(190, y + 12, 500 - 40 * i, y + 28, 8, mix(acc if hot else (205, 205, 210), (255, 255, 255), .5))
def d_chat(c, b, lt, T, bg, acc, ink):
    ms = _l(b.get('msgs') or b.get('items') or ['wait', 'really?'], 4, 44); y = 330
    for i, m in enumerate(ms):
        u = back((lt - .15 - i * .75) / .3)
        left = i % 2 == 0; sz = 38; ls = wrap(c, m, sz, 380); h = len(ls) * 46 + 40; w = max(c.tw(l, sz) for l in ls) + 50
        if u > 0:
            x0 = 130 if left else 590 - w
            if i % 2 == 0 and False: pass
            cy = y + h / 2; c.rr(x0, cy - h / 2 * u, x0 + w, cy + h / 2 * u, 34, (255, 255, 255) if left else acc, INK, 4)
            if u > .7:
                for j, l in enumerate(ls): c.text(x0 + w / 2, cy + (j - (len(ls) - 1) / 2) * 46, l, sz, INK if left else (bg if sum(acc) > 450 else (255, 255, 255)))
            if left: emo(c, b.get('emoji') or '🙂', 85, cy, 60 * u)
        y += h + 34
    if lt > .15 + len(ms) * .75 and int(lt * 4) % 2 == 0: ctext(c, 360, min(y + 20, 1120), '...', 80, ink)
def d_headline(c, b, lt, T, bg, acc, ink):
    k = back(lt / .3); P = (250, 244, 228)
    c.rr(60, 330 + 30 * (1 - k), 660, 1050, 14, P, INK, 5); c.text(360, 405, 'THE DAILY MIND', 46 * k, INK); c.line([(90, 450), (630, 450)], 5, INK)
    emo(c, b.get('emoji'), 360, 590, 190 * back((lt - .1) / .3)); ctext(c, 360, 790, _s(b.get('text'), 70).upper(), 56 * back((lt - .25) / .25), INK, 520)
    for i in range(3): c.rr(100, 930 + i * 28, 620 - (i % 2) * 120, 942 + i * 28, 6, (200, 195, 185))
    s = back((lt - .6) / .25)
    if s > 0: c.text(360, 285, 'BREAKING', 70 * s, (214, 40, 40), 'mm', 5, bg)
def d_countdown(c, b, lt, T, bg, acc, ink):
    n = 3 - int(lt / .55)
    if n > 0:
        ph = (lt % .55) / .55; c.ell(360, 600, 200 + 60 * ph, 200 + 60 * ph, None, acc, max(1, 10 - 8 * ph)); c.text(360, 600, str(n), 420 * back(ph / .5) , acc, 'mm', 8, bg)
    else:
        u = back((lt - 1.65) / .25); emo(c, b.get('emoji'), 360, 430, 260 * u); ctext(c, 360, 760, _s(b.get('text') or 'GO', 30).upper(), 120 * u, acc, 640, 6, bg)
def d_timeline(c, b, lt, T, bg, acc, ink):
    it = _l(b.get('items'), 4, 4) or ['⏳']; lb = _l(b.get('labels'), 4, 22); n = len(it); y0, y1 = 360, 1000
    ctext(c, 360, 280, _s(b.get('text'), 40).upper(), 40, ink, 620); c.line([(200, y0), (200, y0 + (y1 - y0) * ease(lt / (n * .6 + .3)))], 10, mix(bg, acc, .6))
    for i, e in enumerate(it):
        u = back((lt - .2 - i * .6) / .3); y = y0 + (y1 - y0) * (i / max(1, n - 1)) if n > 1 else 600
        if u > 0:
            c.ell(200, y, 46 * u, 46 * u, acc, INK, 4); emo(c, e, 200, y, 56 * u)
            if i < len(lb): ctext(c, 330 + 100, y, lb[i].upper(), 38 * u, ink, 380)
def d_scale(c, b, lt, T, bg, acc, ink):
    heavy = 1 if b.get('heavy', 'b') == 'b' else -1; a = .3 * heavy * ease((lt - .5) / .7) + .03 * math.sin(lt * 5) * (1 - ease((lt - .5) / .7)); pv = (360, 560)
    c.d.polygon([(pv[0] - 70) * K, 900 * K, (pv[0] + 70) * K, 900 * K, pv[0] * K, pv[1] * K], fill=mix(bg, ink, .5)); L = 185
    Lp = (pv[0] - L * math.cos(a), pv[1] - L * math.sin(a)); Rp = (pv[0] + L * math.cos(a), pv[1] + L * math.sin(a)); c.line([Lp, Rp], 14, ink)
    for side, P_, key in ((0, Lp, 'a'), (1, Rp, 'b')):
        u = back((lt - side * .15) / .3); c.line([P_, (P_[0], P_[1] + 130)], 5, ink); c.ell(P_[0], P_[1] + 140, 100, 26, acc, INK, 4)
        emo(c, b.get(key), P_[0], P_[1] + 70 - 20 * (1 - u), 130 * u); ctext(c, P_[0], P_[1] + 215, _s(b.get('l' + key), 22).upper(), 32, ink, 260)
    c.ell(pv[0], pv[1], 22, 22, acc, INK, 4); ctext(c, 360, 1060, _s(b.get('text'), 60).upper(), 42, ink, 640)
def d_crowd(c, b, lt, T, bg, acc, ink):
    cols, rows = 5, 5; e = b.get('emoji') or '🧍'; pk = b.get('pick') or '🤩'; sel = (random.Random(int(b.get('_seed', 1))).randrange(cols * rows))
    for r in range(rows):
        for q in range(cols):
            i = r * cols + q; u = back((lt - i * .03) / .25)
            if u <= 0: continue
            x = 100 + q * 130; y = 340 + r * 130; hot = i == sel and lt > 1.0
            if hot: k = back((lt - 1.0) / .3); c.ell(x, y, 62 * k, 62 * k, acc, INK, 4); emo(c, pk, x, y, 110 * k)
            else: emo(c, e, x, y, 82 * u, .55 if lt > 1.0 else 1)
    ctext(c, 360, 1060, _s(b.get('text'), 60).upper(), 44, ink, 640)
def d_checklist(c, b, lt, T, bg, acc, ink):
    it = _l(b.get('items') or ['one', 'two'], 4, 30); ctext(c, 360, 300, _s(b.get('text'), 40).upper(), 42, ink, 620)
    for i, s_ in enumerate(it):
        u = back((lt - .1 - i * .7) / .3); y = 430 + i * 160
        if u <= 0: continue
        c.rr(60, y - 60 * u, 660, y + 60 * u, 26, (255, 255, 255), INK, 4)
        if u > .6:
            c.rr(90, y - 34, 158, y + 34, 12, None, INK, 5); ctext(c, 420, y, s_.upper(), 38, INK, 440); k = ease((lt - .3 - i * .7) / .25)
            if k > 0: c.line([(102, y), (122, y + 22 * k), (122 + 36 * k, y - 26 * k)] if k > .5 else [(102, y), (102 + 20 * k * 2, y + 22 * k * 2)], 12, (60, 170, 90))
def d_before_after(c, b, lt, T, bg, acc, ink):
    k = ease((lt - .7) / .5); c.rr(40, 340, 680, 960, 30, mix(bg, (120, 120, 130), .25), INK, 5)
    xr = lerp(680, 360, k); c.rr(xr, 340, 680, 960, 30, mix(bg, acc, .35), INK, 5)
    emo(c, b.get('a'), 200, 640, 200 * back(lt / .3) * (1 - .3 * k)); ctext(c, 200, 840, _s(b.get('la') or 'BEFORE', 18).upper(), 40, ink, 280)
    if k > 0: emo(c, b.get('b'), 520, 640, 230 * k); ctext(c, 520, 840, _s(b.get('lb') or 'AFTER', 18).upper(), 40, ink, 280)
    ctext(c, 360, 1040, _s(b.get('text'), 60).upper(), 42, ink, 640)
def d_notif(c, b, lt, T, bg, acc, ink):
    it = _l(b.get('items') or ['new message'], 4, 40)
    for i, s_ in enumerate(it):
        u = ease((lt - .1 - i * .55) / .25)
        if u <= 0: continue
        y = 330 + i * 170 - 120 * (1 - u); sh = 5 * math.sin(lt * 40) * (1 - ease((lt - i * .55 - .35) / .3)) if lt > i * .55 + .1 else 0
        c.rr(50 + sh, y - 65, 670 + sh, y + 65, 30, (255, 255, 255), INK, 4); emo(c, b.get('emoji') or '🔔', 120 + sh, y, 70); ctext(c, 400 + sh, y, s_, 36, INK, 420)
    c.ell(650, 300, 28 * back(lt / .3), 28 * back(lt / .3), (230, 50, 50), INK, 3)
def d_zoom(c, b, lt, T, bg, acc, ink):
    z = 1.8 - .8 * ease(lt / .7); lb = _l(b.get('labels'), 4, 18); emo(c, b.get('emoji'), 360, 640, 380 * z * (1 + .03 * math.sin(lt * 5)))
    pts = [(150, 400), (580, 440), (150, 900), (580, 880)]
    for i, s_ in enumerate(lb):
        u = back((lt - .6 - i * .3) / .3)
        if u <= 0: continue
        x, y = pts[i]; c.line([(360 + (x - 360) * .35, 640 + (y - 640) * .35), (x, y)], 6, acc); c.rr(x - 130 * u, y - 36 * u, x + 130 * u, y + 36 * u, 22, (255, 255, 255), INK, 4)
        if u > .6: ctext(c, x, y, s_.upper(), 28, INK, 240)
    ctext(c, 360, 1090, _s(b.get('text'), 60).upper(), 42, ink, 640)
def d_clock(c, b, lt, T, bg, acc, ink):
    cx, cy, r = 360, 600, 230; c.ell(cx, cy, r, r, (255, 255, 255), INK, 8)
    for i in range(12): a = i / 12 * 2 * math.pi; c.line([(cx + (r - 30) * math.sin(a), cy - (r - 30) * math.cos(a)), (cx + (r - 8) * math.sin(a), cy - (r - 8) * math.cos(a))], 6, INK)
    sp = ease(lt / 2.5) * 14 + lt; a = sp * 2 * math.pi
    c.line([(cx, cy), (cx + 170 * math.sin(a), cy - 170 * math.cos(a))], 9, acc); c.line([(cx, cy), (cx + 110 * math.sin(a / 12), cy - 110 * math.cos(a / 12))], 14, INK); c.ell(cx, cy, 16, 16, INK)
    emo(c, b.get('emoji') or '⏰', 360 + 190, 380 + 8 * math.sin(lt * 9), 120 * back(lt / .3), 1, int(14 * math.sin(lt * 18))); ctext(c, 360, 950, _s(b.get('text'), 50).upper(), 50, ink, 640)
DRAW = {'title_slam': d_title, 'icon_burst': d_icon, 'counter': d_counter, 'chart': d_chart, 'slots': d_slots, 'flow': d_flow, 'versus': d_versus, 'meter': d_meter, 'reaction': d_react, 'brain': d_brain,
        'search': d_search, 'chat': d_chat, 'headline': d_headline, 'countdown': d_countdown, 'timeline': d_timeline, 'scale': d_scale, 'crowd': d_crowd, 'checklist': d_checklist, 'before_after': d_before_after, 'notif': d_notif, 'zoom': d_zoom, 'clock': d_clock}

# ---------- director ----------
def numval(w):
    w = w.lower().strip('.,;:!?'); m = re.fullmatch(r'\$?(\d+(?:\.\d+)?)(%?)', w)
    if m: return float(m.group(1)), ('%' if m.group(2) else '')
    return (NUMW[w], '') if w in NUMW else None
def pick_open(title):
    return OPENERS[sum(ord(ch) for ch in (title or 'x')) % len(OPENERS)]
def rule_director(words, title='', opening=True, pace=9):
    n = len(words); beats = []; i = 0; k = 0; rnd = random.Random(7 + len(title)); op = pick_open(title)
    while i < n:
        j = i
        while j < n and (j - i < pace and not (j - i >= max(4, pace - 5) and re.search(r'[.!?,;:]$', words[j]['w']))): j += 1
        j = min(n, j + 1); chunk = words[i:j]; txt = ' '.join(w['w'] for w in chunk); kind = None
        nums = [(q, numval(w['w'])) for q, w in enumerate(chunk) if re.search(r'\d', w['w']) and numval(w['w'])]
        keys = [(q, KEY[clean(w['w'])]) for q, w in enumerate(chunk) if clean(w['w']) in KEY]
        short = ' '.join(re.sub(r'[^\w%$\'-]', '', w['w']) for w in chunk[-3:]); e0 = keys[0][1] if keys else rnd.choice(['💡', '✨', '👀', '🤔', '🔥'])
        w3 = ' '.join(re.sub(r'[^\w%$\']', '', w['w']) for w in chunk[:3]); w6 = ' '.join(re.sub(r'[^\w%$\']', '', w['w']) for w in chunk[:7])
        if k == 0 and opening:
            kind = {'search': {'kind': 'search', 'text': w6.lower(), 'emoji': e0}, 'headline': {'kind': 'headline', 'text': w6, 'emoji': e0}, 'chat': {'kind': 'chat', 'msgs': [w3.lower(), 'wait really?', 'yes. keep watching'], 'emoji': '🙂'},
                    'countdown': {'kind': 'countdown', 'text': w3, 'emoji': e0}, 'notif': {'kind': 'notif', 'items': [w3, 'your brain says hi', 'open me now'], 'emoji': '🔔'}, 'zoom': {'kind': 'zoom', 'emoji': e0, 'labels': [w3], 'text': w3},
                    'title_slam': {'kind': 'title_slam', 'text': w3, 'emoji': e0}, 'icon_burst': {'kind': 'icon_burst', 'emoji': e0, 'text': w3}, 'clock': {'kind': 'clock', 'emoji': '⏰', 'text': w3}}[op]
        elif nums and k % 2 == 1: v, u = nums[0][1]; kind = {'kind': 'counter', 'value': v, 'unit': u, 'text': short, 'emoji': keys[0][1] if keys else '📊'}
        elif k % 6 == 5: e, q = QUIPS[rnd.randrange(len(QUIPS))]; kind = {'kind': 'reaction', 'emoji': e, 'text': q}
        elif keys and k % 4 == 3: kind = {'kind': 'zoom', 'emoji': keys[0][1], 'labels': [short], 'text': ''}
        elif keys: kind = {'kind': 'icon_burst', 'emoji': keys[0][1], 'text': ' '.join(re.sub(r'[^\w%$\'-]', '', w['w']) for w in chunk[max(0, keys[0][0] - 1):keys[0][0] + 2])}
        else: kind = rnd.choice([{'kind': 'title_slam', 'text': short, 'emoji': e0}, {'kind': 'icon_burst', 'emoji': e0, 'text': short}, {'kind': 'zoom', 'emoji': e0, 'labels': [short], 'text': ''}])
        kind['at'] = i; beats.append(kind); i = j; k += 1
    return beats
def llm_director(words, total, title='', opening=True, pace=2.2, min_react=3, mood_hint=''):
    try:
        import llm
        if not llm.available(): return None
        narr = ' '.join('%d:%s' % (i, w['w']) for i, w in enumerate(words)); want = max(3, int(total / pace)); op = pick_open(title)
        sysm = 'You are a viral short-video director for a psychology channel. Reply JSON only.'
        first = ('The first beat (at 0) is the HOOK. For THIS video open with kind "%s" (adapt the params to the topic; if it truly cannot fit, choose another opening from: search, headline, chat, countdown, notif, zoom, title_slam, clock). ' % op) if opening else 'This is a middle part of a longer video: do NOT open with a hook, just continue naturally. '
        usr = ('Plan a fast, funny, creative explainer video whose pictures ACT OUT the narration live, in sync with the words.\nNarration with word indexes (index:word):\n%s\n\n'
               'Toolkit (kind: params):\n%s\n\nRules: about %d beats; each beat has "at" = word index where it starts (strictly increasing, first is 0; a new visual every %.1f-%.1f seconds). %s'
               'Be SMART and creative: pick the kind that literally shows what the words say (a question being typed into a search bar, a text-message exchange, a newspaper headline, a balance scale for trade-offs, a crowd with one standing out, a checklist of steps, a timeline of stages, before/after, phone notifications for distraction, a clock for time, zoom with callouts for an object, flow for something travelling, slots for limits). '
               'Use MANY different kinds (never the same kind twice in a row; at least %d different kinds besides the opening); at least %d reaction beats starring the mascot Brainy (a talking brain): relatable, self-aware, exaggerated jokes in the style of a witty friend (<=7 words, e.g. \"Me, opening my 47th tab.\"), clean, never mocking people or groups; the emoji field sets Brainy mood (😳 😅 🤯 🙃 😬 🤨 💀 😮 😂). '
               'Numbers/stats in counter/chart/meter/timeline/checklist MUST come from the narration and keep the SAME meaning (never put two different quantities together or compare them); never invent facts or statistics. Do NOT use chart shape bars. Emoji fields must be single emoji characters; text fields use plain ASCII letters only. Every beat may also have "tag" (<=3 word label) and "sticker" (one emoji popped on a key word). %s'
               'Output {"beats":[{"at":0,"kind":"...", ...params}, ...]}'
               % (narr, '\n'.join('- %s: %s' % kv for kv in KINDS.items()), want, pace * .7, pace * 1.4, first, 3 if total > 25 else 2, min_react, mood_hint))
        r = llm.json_call(sysm, usr, temperature=0.85, max_tokens=7000)
        bs = (r or {}).get('beats') or []; out = []; last = -1
        for b in bs:
            if not isinstance(b, dict) or b.get('kind') not in KINDS: continue
            try: a = int(b['at'])
            except Exception: continue
            if a <= last or a >= len(words): continue
            if out and words[a]['s'] - words[out[-1]['at']]['s'] < 1.0: continue
            if out and out[-1]['kind'] == b['kind'] and b['kind'] != 'reaction': continue
            b['at'] = a; out.append(b); last = a
        if out: out[0]['at'] = 0
        kinds = {b['kind'] for b in out}
        return out if len(out) >= total / (pace * 2.2) and len(kinds) >= (3 if total > 25 else 2) else None
    except Exception as e:
        print('llm_director failed:', str(e)[:200]); return None
def clean(w): return B.clean(w)
def nums_in(text):
    s = set()
    for m in re.findall(r'\d+(?:\.\d+)?', text.replace(',', '')): s.add(float(m))
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in NUMW: s.add(float(NUMW[w]))
    return s
def ground(beats, text):
    """L7: a number shown on screen must be in the narration; otherwise the number is hidden (or the beat becomes a plain icon)."""
    ok = nums_in(text); fixed = 0
    for b in beats:
        k = b['kind']
        if k == 'counter' and float(b.get('value') or 0) not in ok:
            b.update({'kind': 'icon_burst', 'emoji': b.get('emoji') or '📊'}); fixed += 1
        elif k == 'chart':
            if b.get('shape') == 'bars':
                b.update({'kind': 'icon_burst', 'emoji': b.get('emoji') or '📊', 'text': b.get('text') or 'DATA'}); fixed += 1   # bars compared different quantities: never show bars
            elif float(b.get('to') or -1) not in ok: b['hide'] = True; fixed += 1
        elif k == 'meter' and round(float(b.get('to') or 0) * 100) not in ok: b['hide'] = True; fixed += 1
        for f, v in list(b.items()):   # any other text on screen that carries a number must have it in the narration
            def bad(s): return isinstance(s, str) and any(float(x) not in ok for x in re.findall(r'\d+(?:\.\d+)?', s.replace(',', '')))
            def fix(s): return re.sub(r'\$?\d+(?:[.,]\d+)?%?', '', s).strip()
            if k in ('counter',) and f == 'value': continue
            if bad(v): b[f] = fix(v); fixed += 1
            elif isinstance(v, list) and any(bad(x) for x in v): b[f] = [fix(x) if bad(x) else x for x in v]; fixed += 1
    return fixed
TOPIC_PAL = [(r'sleep|night|dream|dark|bed|tired', 1), (r'money|cost|price|pay|rich|spend|buy', 4), (r'calm|rest|relax|happy|nature|peace|kind', 6), (r'fear|danger|panic|anxi|stress|threat|risk', 5),
             (r'love|heart|friend|lonel|social|family|relationship', 3), (r'focus|learn|study|memory|attention|brain|think', 2), (r'habit|morning|routine|work|office|time', 0)]
def topic_pal(title, text):
    s = (title + ' ' + text[:600]).lower(); sc = [(len(re.findall(rx, s)), p) for rx, p in TOPIC_PAL]; sc.sort(reverse=True)
    return sc[0][1] if sc and sc[0][0] > 0 else sum(ord(ch) for ch in title) % len(PALS)
TRANS = ['wipe', 'wipe_v', 'iris', 'flash', 'slide', 'wipe']; CAMS = ['punch', 'drift', 'tilt', 'punch', 'push']
def assign_style(beats, title, text):
    prev = topic_pal(title, text) if beats else 0
    for n_, b in enumerate(beats):
        rr_ = random.Random(b['at'] * 7 + len(title))
        if n_ == 0: p = prev
        else:
            p = (prev + 1 + rr_.randrange(len(PALS) - 1)) % len(PALS)
            while p == prev: p = (p + 1) % len(PALS)
        b['_pal'] = prev = p; b['_tr'] = rr_.choice(TRANS); b['_cam'] = rr_.choice(CAMS); b['_seed'] = rr_.randrange(1000)

def make_plan(words, total, text, title='', opening=True, long=False):
    """Director for one video. Long videos are directed in ~45 s chunks (free LLM per chunk, rule fallback per chunk)."""
    if not long:
        beats = llm_director(words, total, title, opening); src = 'llm'
        if not beats: beats = rule_director(words, title, opening); src = 'rules'
    else:
        beats = []; srcs = set(); n = len(words); i = 0
        while i < n:
            j = min(n, i + 110)
            while j < n and not re.search(r'[.!?]$', words[j - 1]['w']) and j - i < 160: j += 1
            sub = words[i:j]; tt = (words[j - 1]['e'] if j - 1 < n else sub[-1]['e']) - sub[0]['s']
            for w in sub: w['_o'] = i
            loc = [{'w': w['w'], 's': w['s'], 'e': w['e']} for w in sub]
            bs = llm_director(loc, tt, title, opening=(i == 0), pace=3.6, min_react=1)
            if bs: srcs.add('llm')
            else: bs = rule_director(loc, title, opening=(i == 0), pace=16); srcs.add('rules')
            for b in bs: b['at'] += i
            if beats and bs and bs[0]['at'] <= beats[-1]['at']: bs = bs[1:]
            beats += bs; i = j
        src = '+'.join(sorted(srcs))
    return beats, src

# ---------- render ----------
def stages(beats, words, total):
    return [0.0 if i == 0 else words[b['at']]['s'] for i, b in enumerate(beats)]
def draw_wrapped(c, seg, wi0, x0, y0, maxw, sz, acc, ink, bg, wi):
    """left-aligned wrapped caption with the spoken word highlighted"""
    lines = [[]]; w_ = 0
    for j, w in enumerate(seg):
        ww = c.tw(w['w'] + ' ', sz)
        if w_ + ww > maxw and lines[-1]: lines.append([]); w_ = 0
        lines[-1].append((wi0 + j, w)); w_ += ww
    y = y0 - (len(lines) - 1) * sz * 1.15 / 2
    for ln in lines:
        x = x0
        for idx, w in ln:
            c.d.text((x * K, y * K), w['w'] + ' ', font=font(sz), fill=acc if idx == wi else ink, anchor='lm', stroke_width=int(4 * K), stroke_fill=bg); x += c.tw(w['w'] + ' ', sz)
        y += sz * 1.15
def scene(t, b, lt, T, i, starts, beats, land):
    bg, acc, ink = PALS[b['_pal']]; c = Cv(bg)
    if i > 0 and lt < .24:
        pb = PALS[beats[i - 1]['_pal']][0]; k = ease(lt / .24); tr = b.get('_tr', 'wipe'); W_, H_ = CW * K, CH * K
        c.d.rectangle([0, 0, W_, H_], fill=pb)
        if tr == 'wipe_v': c.d.rectangle([0, 0, W_, int(H_ * k)], fill=bg)
        elif tr == 'iris': R = 1.2 * H_ * k; c.d.ellipse([W_ / 2 - R, H_ / 2 - R, W_ / 2 + R, H_ / 2 + R], fill=bg)
        elif tr == 'flash': c.d.rectangle([0, 0, W_, H_], fill=mix((255, 255, 255), bg, k))
        elif tr == 'slide': x = int(W_ * (1 - k)); c.d.rectangle([x, 0, W_, H_], fill=bg); c.d.rectangle([x - 14 * K, 0, x, H_], fill=INK)
        else:
            x = int(W_ * k); c.d.rectangle([0, 0, x, H_] if i % 2 else [W_ - x, 0, W_, H_], fill=bg)
    for gx in range(0, 760, 120):
        for gy in range(0, 1320, 120): c.ell(gx + (t * 14) % 120, gy, 4, 4, mix(bg, acc, .12))
    try: DRAW[b['kind']](c, b, lt, T, bg, acc, ink)
    except Exception as e:
        if not b.get('_warned'): b['_warned'] = 1; print('drawer failed', b['kind'], str(e)[:120], flush=True)
        c.d.rectangle([0, 0, CW * K, CH * K], fill=bg); d_icon(c, {'emoji': b.get('emoji') or '💡', 'text': _s(b.get('text'), 30)}, lt, T, bg, acc, ink)
    if b.get('tag'): w_ = c.tw(_s(b['tag'], 24).upper(), 30) + 50; c.rr(360 - w_ / 2, 100, 360 + w_ / 2, 152, 26, acc, INK, 4); c.text(360, 126, _s(b['tag'], 24).upper(), 30, bg if sum(acc) > 400 else (255, 255, 255))
    if b.get('sticker') and lt < 1.4: k = back(lt / .25) * (1 - ease((lt - 1.1) / .3)); c.emo(b['sticker'], 620, 210, 120 * k, 1.0, int(12 * math.sin(lt * 14) * (1 - lt / 1.4)))
    im = c.im; cam = b.get('_cam', 'punch'); z = 1.03 + .07 * math.exp(-lt * 9) + (.02 * math.sin(t * 2.2) if b['kind'] != 'reaction' else .0); sx = sy = 0; ang = 0
    if cam == 'push': z += .05 * min(1, lt / max(.8, T))
    if cam == 'drift': z += .02; sx = 16 * math.sin(lt * 1.3) * K; sy = 10 * math.cos(lt * 1.1) * K
    if cam == 'tilt': z += .025; ang = 1.3 * math.sin(lt * 1.7 + 1) * min(1, lt / .3)
    if b['kind'] == 'reaction' and lt < .8: sx, sy = 10 * math.sin(lt * 50) * (1 - lt / .8) * K, 8 * math.cos(lt * 43) * (1 - lt / .8) * K
    if z > 1.001 or sx or sy:
        w, h = im.size; cw, ch = w / z, h / z; l = min(max(0, (w - cw) / 2 + sx), w - cw); tp = min(max(0, (h - ch) / 2 + sy), h - ch); im = im.resize((w, h), Image.BICUBIC, box=(l, tp, l + cw, tp + ch))
    if ang: im = im.rotate(ang, resample=Image.BICUBIC, fillcolor=bg)
    c.im = im; c.d = B.ImageDraw.Draw(im)
    return c, bg, acc, ink
def frame(t, beats, starts, words, total, wstarts, land=False):
    i = max(0, bisect.bisect_right(starts, t) - 1); b = beats[i]; lt = t - starts[i]; T = (starts[i + 1] if i + 1 < len(starts) else total) - starts[i]
    c, bg, acc, ink = scene(t, b, lt, T, i, starts, beats, land); wi = max(0, bisect.bisect_right(wstarts, t) - 1)
    if land:   # 1280x720: the portrait scene becomes a panel on the left, live captions on the right
        sc = c.im.crop((0, 150 * K, CW * K, 1110 * K)).resize((540 * K, 720 * K), Image.LANCZOS)
        L = Cv(bg); L.im = Image.new('RGB', (1280 * K, 720 * K), bg); L.d = B.ImageDraw.Draw(L.im)
        for gx in range(0, 1300, 100):
            for gy in range(0, 740, 100): L.ell(gx + (t * 10) % 100, gy, 4, 4, mix(bg, acc, .14))
        L.im.paste(sc, (44 * K, 0)); L.d.rectangle([44 * K, 0, 584 * K, 720 * K], outline=INK, width=int(5 * K)); L.text(640, 44, 'MINDLORE', 30, ink, 'lm')
        if t >= words[0]['s']:
            st = wi
            while st > 0 and not re.search(r'[.?!,]$', words[st - 1]['w']) and wi - st < 7: st -= 1
            draw_wrapped(L, words[st:wi + 1], st, 640, 360, 590, 58, acc, ink, bg, wi)
        L.d.rectangle([640 * K, 676 * K, 1240 * K, 684 * K], fill=mix(bg, (150, 150, 160), .5)); L.d.rectangle([640 * K, 676 * K, (640 + 600 * clamp(t / total)) * K, 684 * K], fill=acc)
        return L.im.resize((1280, 720), Image.LANCZOS)
    c.text(40, 60, 'MINDLORE', 30, ink, 'lm')
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

G = {}
def _fr(f): return frame(f / G['fps'], G['beats'], G['starts'], G['words'], G['total'], G['wst'], G['land']).tobytes()
def render(words, total, mp3, outp, text, title='', land=False, fps=None, long=False, plan_out=None):
    """Shared by Shorts (portrait 1080x1920, 30fps) and full videos (landscape 1280x720, 15fps). Audio: mp3 path (already mixed for full videos)."""
    beats, src = make_plan(words, total, text, title, True, long)
    print('numbers hidden/replaced (not in narration):', ground(beats, text), flush=True)
    if beats[-1]['kind'] != 'title_slam' and not long and words[-1]['s'] - words[beats[-1]['at']]['s'] > 2.4: beats.append({'at': max(beats[-1]['at'] + 1, len(words) - 3), 'kind': 'title_slam', 'text': 'AGAIN?', 'emoji': '🔁'})
    assign_style(beats, title, text); fps = fps or (15 if land else FPS)
    starts = stages(beats, words, total); wst = [w['s'] for w in words]
    print('director:', src, 'beats:', len(beats), 'kinds:', sorted({b['kind'] for b in beats}), 'open:', beats[0]['kind'], 'secs:', round(total, 1), flush=True)
    G.update(beats=beats, starts=starts, words=words, total=total, wst=wst, land=land, fps=fps)
    dump = [float(x) for x in os.environ.get('DUMP', '').split(',') if x]
    for tt in dump: frame(tt, beats, starts, words, total, wst, land).save(Path(outp).parent / ('ld_%05.1f.png' % tt))
    if dump: return beats, src
    size = (1280, 720) if land else (CW, CH)
    args = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % size, '-r', str(fps), '-i', '-'] + (['-i', str(mp3)] if mp3 else [])
    args += ['-vf', 'scale=1280:720:flags=lanczos' if land else 'scale=1080:1920:flags=lanczos', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p'] + (['-c:a', 'copy' if land else 'aac'] + ([] if land else ['-b:a', '160k']) + ['-t', '%.2f' % total] if mp3 else ['-an']) + ['-movflags', '+faststart', str(outp)]
    ff = subprocess.Popen(args, stdin=subprocess.PIPE); nf = int(total * fps)
    if land:
        import multiprocessing as mp
        with mp.get_context('fork').Pool(max(1, os.cpu_count() or 2)) as pool:
            for k, by in enumerate(pool.imap(_fr, range(nf), chunksize=16)):
                ff.stdin.write(by)
                if k % 600 == 0: print('live: frame %d/%d' % (k, nf), flush=True)
    else:
        for f in range(nf): ff.stdin.write(frame(f / fps, beats, starts, words, total, wst).tobytes())
    ff.stdin.close()
    if ff.wait(): raise RuntimeError('live encode failed')
    if plan_out: Path(plan_out).write_text(json.dumps({'director': src, 'title': title, 'seconds': round(total, 1), 'beats': [{k: v for k, v in b.items() if not k.startswith('_')} for b in beats]}, indent=1))
    return beats, src

def build(story, outp):
    d = json.load(open(story)); text = ' '.join(s['narration'] for s in d['sections'])
    text = re.sub(r'[‐-―]', '-', text).replace('’', "'").replace('‘', "'"); text = re.sub(r'[^\x20-\x7e]', '', text); text = re.sub(r'\s+', ' ', text).strip()
    B.TEXT = text; words, mp3 = B.get_words(); total = words[-1]['e'] + 1.0
    render(words, total, mp3, outp, text, d.get('public_title') or d.get('title') or '', plan_out=str(outp) + '.plan.json')

if __name__ == '__main__':
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True); build(sys.argv[1], sys.argv[2])
