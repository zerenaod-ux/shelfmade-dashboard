"""TEST ONLY (never posted): MindLore 'live demonstration' Short. The picture ACTS OUT the script as it is spoken:
camera flies into a head, prefrontal cortex lights up, 4 working-memory slots fill and one falls out, forgetting curve is drawn live,
at night a note travels to the hippocampus, repeated notes become stored stars. Emoji stickers pop on key words (same idea as the real MindLore look).
Output: out/mindlore-braintest.mp4   (FAKE=1 -> silent even timing for local look-tests; DUMP=3,10,20 saves PNG frames)"""
import asyncio, json, math, os, re, subprocess, sys, bisect
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CW, CH, K, FPS = 720, 1280, 2, 30
OUT = Path('out'); OUT.mkdir(exist_ok=True)
PAPER = (247, 240, 225); INK = (34, 34, 42); ACC = (224, 86, 60); BLUE = (52, 110, 190); GOLD = (244, 186, 52); NIGHT = (22, 26, 58)
PINK = (246, 196, 204); SKIN = (255, 226, 200)
TEXT = ("Your brain deletes most of what you learn today. Here's why. Let's go inside. Up front, your prefrontal cortex holds whatever you're thinking about right now. "
        "But it only fits about four things. Add a fifth, and one falls out. Then it gets worse. Ebbinghaus tracked his own memory, and found he forgot over half within an hour. "
        "Unless you sleep. At night, your brain moves the important notes to the hippocampus, the memory center. Repeat them, and they're stored for years. So what did your brain just keep?")
VOICE = 'en-US-AndrewNeural'

def fnt(sz):
    sz = max(8, int(sz * K))
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()
_F = {}
def font(sz):
    k = max(8, int(sz))
    if k not in _F: _F[k] = fnt(k)
    return _F[k]
EMO = {}
def emoji(ch, size, alpha=1.0):
    if ch not in EMO:
        im = Image.new('RGBA', (136, 128), (0, 0, 0, 0))
        try:
            f = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 109); ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
        except Exception: pass
        EMO[ch] = im.crop(im.getbbox() or (0, 0, 8, 8))
    im = EMO[ch]; s = size * K / max(im.size); im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    if alpha < 1: a = im.getchannel('A').point(lambda v: int(v * alpha)); im.putalpha(a)
    return im

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def back(x):
    x = clamp(x); c = 1.70158; x -= 1; return 1 + (c + 1) * x ** 3 + c * x * x
def lerp(a, b, t): return a + (b - a) * t
def mix(c1, c2, t): return tuple(int(lerp(c1[i], c2[i], clamp(t))) for i in range(3))

class Cv:
    def __init__(s, col, size=None): s.W, s.H = size or (CW, CH); s.im = Image.new('RGB', (s.W * K, s.H * K), col); s.d = ImageDraw.Draw(s.im)
    def ell(s, x, y, rx, ry, fill=None, out=None, w=0):
        s.d.ellipse([(x - rx) * K, (y - ry) * K, (x + rx) * K, (y + ry) * K], fill=fill, outline=out, width=int(w * K))
    def line(s, pts, w, col):
        P = [(x * K, y * K) for x, y in pts]; s.d.line(P, fill=col, width=max(1, int(w * K)), joint='curve')
        r = w * K / 2
        for x, y in (P[0], P[-1]): s.d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    def rr(s, x0, y0, x1, y1, rad, fill=None, out=None, w=0): s.d.rounded_rectangle([x0 * K, y0 * K, x1 * K, y1 * K], radius=rad * K, fill=fill, outline=out, width=int(w * K))
    def text(s, x, y, t, sz, col=INK, anchor='mm', stroke=0, scol=PAPER): s.d.text((x * K, y * K), t, font=font(sz), fill=col, anchor=anchor, stroke_width=int(stroke * K), stroke_fill=scol)
    def tw(s, t, sz): return font(sz).getlength(t) / K
    def emo(s, ch, x, y, size, alpha=1.0, rot=0):
        im = emoji(ch, size, alpha)
        if rot: im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
        s.im.paste(im, (int(x * K - im.width / 2), int(y * K - im.height / 2)), im)

# ---------- narration + timing ----------
async def _narrate(text, mp3):
    try: com = __import__('edge_tts').Communicate(text, VOICE, rate='+6%', boundary='WordBoundary')
    except TypeError: com = __import__('edge_tts').Communicate(text, VOICE, rate='+6%')
    ws, au = [], bytearray()
    async for c in com.stream():
        if c['type'] == 'audio': au += c['data']
        elif c['type'] == 'WordBoundary': ws.append({'w': c['text'], 's': c['offset'] / 1e7, 'e': (c['offset'] + c['duration']) / 1e7})
    mp3.write_bytes(bytes(au)); return ws
def dur(p): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)], capture_output=True, text=True).stdout)
def get_words():
    toks = TEXT.split()
    if os.environ.get('FAKE'):
        return [{'w': w, 's': i / 2.9 + .3, 'e': (i + 1) / 2.9 + .3} for i, w in enumerate(toks)], None
    mp3 = OUT / 'bt.mp3'; ws = None
    import time
    for att in range(5):
        try: ws = asyncio.run(_narrate(TEXT, mp3)); break
        except Exception as e: print('narration retry', att, str(e)[:120], flush=True); time.sleep(3 + att * 4)
    if ws is None: raise SystemExit('narration failed after retries')
    if len(ws) != len(toks): ws = [{'w': w, 's': i * dur(mp3) / len(toks), 'e': (i + 1) * dur(mp3) / len(toks)} for i, w in enumerate(toks)]
    for a, b in zip(ws, toks): a['w'] = b
    return ws, mp3

WORDS = []; CUE = {}
def clean(w): return re.sub(r"[^\w']", '', w.lower())
def setup(words):
    global WORDS, CUE
    WORDS = words; pos = 0
    def f(key, rx=None, nxt=True):
        nonlocal pos
        rx = rx or key
        for i in range(pos, len(words)):
            if re.fullmatch(rx, clean(words[i]['w'])): CUE[key] = words[i]['s']; CUE[key + '_e'] = words[i]['e']; CUE[key + '_i'] = i; pos = i + 1 if nxt else i; return
        raise SystemExit('cue missing ' + key)
    for k in ['brain', 'deletes', 'inside', 'prefrontal', 'four', 'fifth', 'falls', 'worse', 'ebbinghaus', 'forgot', 'hour', 'sleep', 'night', 'moves', 'hippocampus', 'repeat', 'stored', 'years', 'what']: f(k)
    CUE['end'] = words[-1]['e']

# ---------- camera ----------
HEAD = (0, 0); BR = (20, -70); BS = 0.8
def lobes_world(): return {'front': (-116, -86), 'parietal': (48, -154), 'occip': (184, -74), 'temporal': (12, -2)}
HIPPO = (-2, -12)
def keyframes():
    c = CUE; end = c['end'] + .5
    return [(0, .85, 0, 40), (c['inside'] - .3, .9, 0, 30), (c['inside'] + 1.1, 1.45, 10, -70), (c['prefrontal'] - .2, 1.5, 0, -80), (c['prefrontal'] + .8, 1.95, -95, -90),
            (c['worse'] - .2, 1.95, -95, -90), (c['worse'] + .9, 1.25, 10, -60), (c['sleep'], 1.35, 10, -50), (c['moves'], 1.5, -50, -60), (c['hippocampus'] - .1, 2.15, 0, -22),
            (c['repeat'] - .1, 1.8, 6, -40), (c['stored'] - .1, 1.25, 10, -75), (c['what'] - .2, 1.1, 5, -40), (end, .85, 0, 40)]
def cam(t):
    K_ = keyframes(); ts = [k[0] for k in K_]; i = max(0, bisect.bisect_right(ts, t) - 1)
    if i >= len(K_) - 1: return K_[-1][1:]
    a, b = K_[i], K_[i + 1]; u = ease((t - a[0]) / max(.01, b[0] - a[0]))
    return lerp(a[1], b[1], u), lerp(a[2], b[2], u), lerp(a[3], b[3], u)

# ---------- drawing ----------
def brain_draw(c, S, g, t):
    """S: world->screen function. g: glow dict. Brain local coords (x right, y down), facing left."""
    s = BS * (1 + .015 * math.sin(t * 5))
    def W(x, y): return S(BR[0] + x * s, BR[1] + y * s)
    def e(x, y, rx, ry, fill, out=None, w=0, grow=0):
        X, Y = W(x, y); z = S.z * s
        c.ell(X, Y, (rx + grow) * z, (ry + grow) * z, fill, out, w)
    z = S.z * s; INKW = 6
    # stem + cerebellum
    X, Y = W(110, 170); c.ell(X, Y, 38 * z, 80 * z, INK); c.ell(X, Y, 32 * z, 74 * z, (232, 176, 186))
    e(175, 135, 85, 50, INK, grow=5); e(175, 135, 85, 50, (232, 176, 186))
    CORT = [(-165, -10, 150, 140), (35, -105, 175, 105), (205, -5, 100, 115), (-10, 85, 185, 75), (0, -10, 230, 120)]
    for r in CORT: e(*r, INK, grow=7)
    for r in CORT: e(*r, PINK)
    # lobe glows
    GL = {'front': ((-160, -10, 132, 120), (150, 190, 255)), 'parietal': ((35, -105, 165, 98), (255, 214, 110)), 'occip': ((205, -5, 92, 106), (255, 214, 110)), 'temporal': ((-10, 85, 176, 66), (255, 214, 110))}
    for k, (r, col) in GL.items():
        if g.get(k, 0) > .02: e(*r, mix(PINK, col, g[k]))
    # sulci
    for (x, y, r, a0, a1) in [(-165, 0, 80, 200, 330), (-150, -40, 50, 20, 160), (30, -105, 90, 190, 350), (60, -90, 55, 10, 170), (205, 0, 50, 220, 340), (-10, 85, 100, 20, 160), (-90, 70, 40, 180, 300), (20, -10, 70, 30, 150)]:
        X, Y = W(x, y); c.d.arc([(X - r * z) * K, (Y - r * z) * K, (X + r * z) * K, (Y + r * z) * K], a0, a1, fill=(210, 140, 158), width=max(2, int(3.2 * z * K)))
    # hippocampus (seahorse curve)
    hp = [(-95, 70), (-55, 52), (-12, 58), (22, 84), (30, 118)]
    gh = g.get('hippo', 0)
    if gh > .02:
        for rad in (1.0 + .0, ):
            c.line([W(x, y) for x, y in hp], (20 + 14 * gh) * z, mix((170, 120, 190), (140, 90, 255), gh))
        X, Y = W(*hp[0]); c.ell(X, Y, 14 * z, 14 * z, (140, 90, 255))
    else: c.line([W(x, y) for x, y in hp], 9 * z, (205, 150, 170))

def draw(t, total):
    cz, cx, cy = cam(t)
    for kw in ('brain', 'deletes', 'four', 'fifth', 'worse', 'forgot', 'hour', 'sleep', 'hippocampus', 'repeat', 'stored', 'years', 'what'):
        cz *= 1 + .05 * math.exp(-max(0, t - CUE[kw]) * 7) * (t >= CUE[kw])
    night = ease((t - (CUE['sleep'] - .2)) / .8) * (1 - ease((t - (CUE['what'] - .3)) / .7))
    bgc = mix(PAPER, NIGHT, night)
    c = Cv(bgc)
    class S:  # world->screen
        z = cz
        def __call__(s, x, y): return ((x - cx) * cz + 360, (y - cy) * cz + 560)
    S = S(); S.z = cz
    # parallax dots
    for gx in range(-12, 13):
        for gy in range(-12, 13):
            X, Y = S(gx * 120, gy * 120)
            if -20 < X < 740 and -20 < Y < 1300: c.ell(X, Y, 3 * cz ** .5, 3 * cz ** .5, mix((226, 216, 196), (44, 50, 92), night))
    # night stars
    if night > .02:
        for i in range(24):
            sx = (i * 197) % 720; sy = (i * 331) % 700; tw = .5 + .5 * math.sin(t * 3 + i)
            c.ell(sx, sy, 2 + 2 * tw, 2 + 2 * tw, mix(NIGHT, (255, 244, 200), night * (.4 + .6 * tw)))
    # head
    hx, hy = S(0, 0)
    SK = mix(SKIN, (52, 56, 104), night)
    c.rr(*(S(-90, 300)[0], S(0, 300)[1], S(90, 300)[0], S(0, 520)[1]), 20 * cz, SK, INK, 6 * cz)
    c.ell(hx, hy, 395 * cz, 430 * cz, INK); c.ell(hx, hy, 388 * cz, 423 * cz, SK)
    ex, ey = S(-250, 40); c.ell(ex, ey, 14 * cz, 20 * cz, INK)
    mx, my = S(-290, 215); c.line([(mx, my), (S(-200, 225)[0], S(-200, 225)[1])], 8 * cz, INK)
    nx, ny = S(-390, 90); c.line([(nx, ny), (nx - 28 * cz, ny + 60 * cz), (nx + 10 * cz, ny + 70 * cz)], 8 * cz, INK)
    # glow state
    g = {}
    gf = ease((t - CUE['prefrontal']) / .5) * (1 - ease((t - CUE['worse']) / .6)); g['front'] = gf * (.7 + .3 * math.sin(t * 6))
    gh = ease((t - CUE['hippocampus']) / .5); g['hippo'] = gh
    gs = ease((t - CUE['stored']) / 1.2)
    for k in ('parietal', 'occip', 'temporal'): g[k] = gs * .8
    if t < CUE['inside']: pass
    brain_draw(c, S, g, t)
    L = lobes_world()
    # hook: notes flying out of the head
    if CUE['deletes'] - .1 < t < CUE['deletes'] + 2.4:
        for i, ch in enumerate(['📝', '📖', '💡', '📞', '🧾']):
            u = (t - CUE['deletes'] - i * .18) / 1.8
            if 0 < u < 1:
                x, y = S(-60 + i * 55, -250 - u * 260); c.emo(ch, x, y + 70 * u * u * 3, 70 * (1 - .4 * u), 1 - ease((u - .6) / .4), rot=int(u * 60 * (1 if i % 2 else -1)))
    # label chip helper
    def chip(txt, y, col, k=1.0):
        w = c.tw(txt, 34) + 56; k = back(k)
        c.rr(360 - w / 2 * k, y - 28 * k, 360 + w / 2 * k, y + 28 * k, 28 * k, col, INK, 4)
        if k > .5: c.text(360, y, txt, 34 * min(1, k), PAPER if col != PAPER else INK)
    # top title per beat
    titles = [(0, 'YOUR BRAIN', ACC), (CUE['inside'], 'INSIDE YOUR BRAIN', BLUE), (CUE['prefrontal'], 'PREFRONTAL CORTEX', (60, 110, 220)), (CUE['worse'], 'EBBINGHAUS · 1885', ACC),
              (CUE['sleep'], 'WHILE YOU SLEEP', (90, 70, 190)), (CUE['hippocampus'], 'HIPPOCAMPUS = MEMORY CENTER', (120, 70, 220)), (CUE['stored'], 'STORED FOR YEARS', (200, 140, 20)), (CUE['what'], 'YOUR TURN', ACC)]
    ti = max(i for i, (a, _, _) in enumerate(titles) if t >= a); ta, tt, tc = titles[ti]
    chip(tt, 120, tc, (t - ta) / .35 + .05)
    # working-memory tray
    tray_on = ease((t - CUE['prefrontal'] - .4) / .4) * (1 - ease((t - CUE['worse'] - .2) / .6))
    ems = ['🛒', '📞', '🔑', '💡', '🍕']
    if tray_on > .02:
        ty = 330
        c.rr(40, ty - 90, 680, ty + 90, 26, mix(bgc, (225, 235, 255), tray_on), (60, 110, 220), 4)
        c.text(360, ty - 70, 'WORKING MEMORY  ≈ 4 SLOTS', 24, (60, 110, 220))
        fx, fy = S(*L['front']); c.line([(fx, fy - 40 * cz), (360, ty + 90)], 6, mix(bgc, (110, 170, 255), tray_on))
        for i in range(5):
            if i < 4: tc_ = CUE['four'] + (i - 3) * .28 + .5 * 0 if False else CUE['four_e'] - (3 - i) * .3 - .4
            else: tc_ = CUE['fifth']
            u = back((t - tc_) / .35)
            if u <= 0: continue
            x = 100 + i * 130; y = ty + 20
            if i == 4: x = lerp(760, x, ease((t - tc_) / .4))
            alpha = 1.0; rot = 0
            if i == 0 and t > CUE['falls']:
                fu = t - CUE['falls']; x -= 40 * fu; y += 1100 * fu * fu * .8; rot = int(120 * fu); alpha = 1 - ease(fu / .9)
            if i != 0 and t > CUE['falls'] + .3 and i <= 4: x = lerp(x, x - 130, ease((t - CUE['falls'] - .3) / .4))
            fade = 1 - ease((t - CUE['worse']) / 1.0)
            if alpha <= .02: continue
            c.rr(x - 52 * u, y - 52 * u, x + 52 * u, y + 52 * u, 16, (255, 249, 214), INK, 4)
            c.emo(ems[i], x, y, 66 * u, alpha * max(.0, fade) if t > CUE['worse'] else alpha, rot)
        if CUE['fifth'] <= t < CUE['falls'] + .2: c.text(360, ty + 128, 'FULL!', 30, ACC, stroke=0) if int(t * 6) % 2 == 0 else None
    # forgetting curve panel
    cp = ease((t - CUE['worse'] - .1) / .5) * (1 - ease((t - CUE['sleep'] - .2) / .5))
    if cp > .02:
        x0, y0, x1, y1 = 90, 820, 650, 1090
        c.rr(40, 770, 680, 1120, 24, mix(bgc, (255, 255, 255), cp), INK, 4)
        c.line([(x0, y0 - 10), (x0, y1), (x1, y1)], 5, INK)
        c.text(x0 + 6, y0 - 26, 'memory kept', 22, INK, 'la'); c.text(x1, y1 + 24, 'time →', 22, INK, 'ra')
        p = clamp((t - CUE['forgot']) / max(.5, CUE['hour_e'] - CUE['forgot']))
        pts = []
        for i in range(0, int(p * 60) + 1):
            q = i / 60; R = 42 + 58 * math.exp(-4 * q); pts.append((x0 + q * (x1 - x0 - 20), y0 + (100 - R) / 100 * (y1 - y0 - 10)))
        if len(pts) > 1: c.line(pts, 9, ACC)
        if pts: c.ell(pts[-1][0], pts[-1][1], 13, 13, ACC, INK, 3)
        R = 42 + 58 * math.exp(-4 * p); c.text(520, y0 + 60, '%d%%' % round(R), 96, ACC, stroke=3, scol=(255, 255, 255))
        for q, lab in ((.333, '20 min'), (1.0, '1 hour')):
            if p >= q - .001: X = x0 + q * (x1 - x0 - 20); c.line([(X, y1), (X, y1 - 16)], 4, INK); c.text(X, y1 + 22, lab, 22, INK)
    # sleep: moon + zzz, travelling note
    if night > .2:
        c.emo('🌙', 590, 230 + 6 * math.sin(t * 2), 120 * night, night)
        c.emo('💤', 130, 250 + 10 * math.sin(t * 3 + 1), 80 * night, night)
    a_ = CUE['moves']; b_ = CUE['hippocampus'] + .3
    if a_ < t < b_ + 1.5:
        u = ease((t - a_) / (b_ - a_)); sx, sy = S(*L['front']); ex_, ey_ = S(*HIPPO)
        px = lerp(sx, ex_, u); py = lerp(sy, ey_, u) - 120 * math.sin(u * math.pi) * cz
        trail = [(lerp(sx, ex_, max(0, u - k * .05)), lerp(sy, ey_, max(0, u - k * .05)) - 120 * math.sin(max(0, u - k * .05) * math.pi) * cz) for k in range(6, -1, -1)]
        c.line(trail, 8, (255, 214, 110))
        if u < 1: c.ell(px, py, 26, 26, (255, 214, 110), INK, 3); c.emo('📝', px, py, 34)
    if CUE['hippocampus'] <= t < CUE['repeat'] + 2.5:
        X, Y = S(*HIPPO)
        for r in range(3):
            u = ((t - CUE['repeat'] - r * .55) / 1.2) if t >= CUE['repeat'] else 0
            if 0 < u < 1: c.ell(X, Y, (30 + 110 * u) * cz ** .6, (30 + 110 * u) * cz ** .6, None, (255, 214, 110), 7 * (1 - u) + 1)
        if t >= CUE['repeat']: c.emo('🔁', 590, 1010, 90 * back((t - CUE['repeat']) / .3))
    if t >= CUE['stored']:
        for i, (nm, ch) in enumerate([('front', '⭐'), ('parietal', '⭐'), ('occip', '⭐'), ('temporal', '⭐')]):
            u = back((t - CUE['stored'] - i * .22) / .4)
            if u > 0: X, Y = S(*L[nm]); c.emo(ch, X, Y, 60 * u * (1 + .08 * math.sin(t * 6 + i)))
        if t >= CUE['stored'] + .2: c.emo('🔒', 360, 960, 120 * back((t - CUE['stored'] - .2) / .35))
    if t >= CUE['years']: c.emo('📅', 130, 1020, 110 * back((t - CUE['years']) / .35))
    # final question
    if t >= CUE['what']:
        ft = clamp(1 - (t - total + 1.0) / .8) if t > total - 1.0 else 1
        qx, qy = S(0, -520); c.text(qx, qy, '?', 260 * back((t - CUE['what']) / .4), ACC, stroke=6, scol=(255, 255, 255)) if ft > .05 else None
    # word stickers (emoji pop top-right)
    stick = {'brain': '🧠', 'deletes': '🗑️', 'four': '4️⃣', 'fifth': '5️⃣', 'worse': '📉', 'forgot': '😵', 'hour': '⏰', 'sleep': '😴', 'hippocampus': '📍', 'stored': '🔓' if False else '🔒', 'what': '❓'}
    for kw, ch in stick.items():
        u = t - CUE[kw]
        if 0 <= u < 1.4 and kw not in ('stored',):
            k = back(u / .25) * (1 - ease((u - 1.1) / .3)); c.emo(ch, 610, 215 + (0 if night < .5 else 130), 110 * k, 1.0, int(12 * math.sin(u * 14) * (1 - u / 1.4)))
    # caption (current phrase, current word highlighted)
    wi = max(0, bisect.bisect_right([w['s'] for w in WORDS], t) - 1)
    if t >= WORDS[0]['s']:
        st = wi
        while st > 0 and not re.search(r'[.?!,]$', WORDS[st - 1]['w']) and wi - st < 5: st -= 1
        seg = WORDS[st:wi + 1]; sz = 40
        full = ' '.join(w['w'] for w in seg)
        if c.tw(full, sz) > 640: sz = 40 * 640 / c.tw(full, sz)
        x = 360 - c.tw(full, sz) / 2
        for j, w in enumerate(seg):
            on = (st + j == wi); c.text(x, 1200, w['w'] + ' ', sz, (255, 214, 110) if (on and night > .5) else (ACC if on else (INK if night < .5 else (230, 230, 245))), 'lm', stroke=0); x += c.tw(w['w'] + ' ', sz)
    # progress bar
    c.d.rectangle([40 * K, 1250 * K, (CW - 40) * K, 1258 * K], fill=mix(bgc, (150, 150, 160), .5)); c.d.rectangle([40 * K, 1250 * K, (40 + (CW - 80) * clamp(t / total)) * K, 1258 * K], fill=ACC)
    c.text(40, 60, 'MINDLORE', 30, INK if night < .5 else PAPER, 'lm')
    return c.im.resize((CW, CH), Image.LANCZOS)

def main():
    words, mp3 = get_words(); setup(words); total = CUE['end'] + 1.2
    dump = [float(x) for x in os.environ.get('DUMP', '').split(',') if x]
    for tt in dump: draw(tt, total).save(OUT / ('bt_%05.1f.png' % tt))
    if dump: return
    args = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (CW, CH), '-r', str(FPS), '-i', '-']
    if mp3: args += ['-i', str(mp3)]
    args += ['-vf', 'scale=1080:1920:flags=lanczos', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p'] + (['-c:a', 'aac', '-b:a', '160k', '-shortest'] if mp3 else ['-an']) + [str(OUT / 'mindlore-braintest.mp4')]
    ff = subprocess.Popen(args, stdin=subprocess.PIPE)
    for f in range(int(total * FPS)): ff.stdin.write(draw(f / FPS, total).tobytes())
    ff.stdin.close(); ff.wait(); print('done', total)

if __name__ == '__main__': main()
