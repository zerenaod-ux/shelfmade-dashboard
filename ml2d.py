"""MindLore 2D EXPLAINER engine: turns a checked MindLore script (cinematic-scripts-mindlore/*.json) into a faceless 2D animated explainer video.
Style v4: a living stick-man world. Joint-angle narrator (walk, run, point, think, laugh, sleep...), scene backdrops, props that match the words, everything timed to the spoken words.
Everything is drawn in code (PIL) and encoded with ffmpeg: free, fully automatic, no stock footage, no AI image service.
  python ml2d.py <script id or path> <out folder>          (ML2D_FAKE=1 uses silent timing for tests)
Output folder: ml2d_LONGFORM.mp4, THUMBNAIL.jpg, POST_THIS.txt (same shape the review step already reads)."""
import os, sys, json, re, math, random, subprocess, wave, bisect, datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
BASE = Path(__file__).resolve().parent
SM = os.environ.get('BRAND') == 'shelfmade'   # ShelfMade look: bookish narrator, library worlds
BRAND_NAME = 'ShelfMade' if SM else 'MindLore'
W, H, FPS, K = 1280, 720, 15, 2
PAPER = (247, 240, 225); INK = (34, 34, 42); ACC = (224, 86, 60); BLUE = (52, 110, 190); GOLD = (244, 186, 52); GREEN = (56, 150, 108); SOFT = (228, 217, 192); WHITE = (255, 253, 247); PINK = (250, 184, 196)
_FONTS = {}
def font(size, bold=True, italic=False):
    key = (int(size * K), bold, italic)
    if key in _FONTS: return _FONTS[key]
    names = (['DejaVuSans-BoldOblique.ttf', 'LiberationSans-BoldItalic.ttf'] if bold and italic else ['DejaVuSans-Oblique.ttf', 'LiberationSans-Italic.ttf'] if italic else ['DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf'] if bold else ['DejaVuSans.ttf', 'LiberationSans-Regular.ttf'])
    for d in ('/usr/share/fonts/truetype/dejavu/', '/usr/share/fonts/truetype/liberation/', '/usr/share/fonts/truetype/liberation2/', '/System/Library/Fonts/Supplemental/'):
        for n in names:
            try:
                f = ImageFont.truetype(d + n, int(size * K)); _FONTS[key] = f; return f
            except Exception: pass
    f = ImageFont.load_default(); _FONTS[key] = f; return f
def tw(t, size, bold=True, italic=False): return font(size, bold, italic).getlength(t) / K
def wrap(t, size, maxw, bold=True, italic=False):
    out, cur = [], ''
    for w in t.split():
        c = (cur + ' ' + w).strip()
        if tw(c, size, bold, italic) <= maxw or not cur: cur = c
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def back(x):
    x = clamp(x); c1 = 1.70158; x -= 1; return 1 + (c1 + 1) * x ** 3 + c1 * x ** 2
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def pop(lt, t0, dur=.45): return back((lt - t0) / dur) if lt > t0 else 0.0

class Cv:
    def __init__(s, base=None): s.im = base.copy() if base is not None else Image.new('RGB', (W * K, H * K), PAPER); s.d = ImageDraw.Draw(s.im)
    def P(s, pts): return [(x * K, y * K) for x, y in pts]
    def line(s, pts, w=7, col=INK):
        P = s.P(pts); s.d.line(P, fill=col, width=max(1, int(w * K)), joint='curve'); r = w * K / 2
        for x, y in (P[0], P[-1]): s.d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    def circ(s, x, y, r, fill=None, out=INK, w=6):
        if r <= 0: return
        s.d.ellipse([(x - r) * K, (y - r) * K, (x + r) * K, (y + r) * K], fill=fill, outline=out, width=int(w * K) if out else 0)
    def ell(s, x0, y0, x1, y1, fill=None, out=INK, w=6): s.d.ellipse([x0 * K, y0 * K, x1 * K, y1 * K], fill=fill, outline=out, width=int(w * K) if out else 0)
    def rr(s, x0, y0, x1, y1, rad=14, fill=None, out=INK, w=5): s.d.rounded_rectangle([x0 * K, y0 * K, x1 * K, y1 * K], radius=rad * K, fill=fill, outline=out, width=int(w * K) if out else 0)
    def poly(s, pts, fill=None, out=INK, w=5):
        s.d.polygon(s.P(pts), fill=fill)
        if out: s.line(list(pts) + [pts[0]], w, out)
    def arc(s, x0, y0, x1, y1, a0, a1, w=6, col=INK): s.d.arc([x0 * K, y0 * K, x1 * K, y1 * K], a0, a1, fill=col, width=int(w * K))
    def text(s, xy, t, size, col=INK, anchor='la', bold=True, italic=False, stroke=0, scol=WHITE):
        s.d.text((xy[0] * K, xy[1] * K), t, font=font(size, bold, italic), fill=col, anchor=anchor, stroke_width=int(stroke * K), stroke_fill=scol)
    def out(s): return s.im.resize((W, H), Image.LANCZOS)

def wob(i, now, a=1.4): return math.sin(now * 8 + i * 1.9) * a

# ---------------- icons ----------------
def icon(c, name, cx, cy, r, now=0.0):
    if r < 4: return
    u = r / 100.0
    if name == 'brain':
        c.ell(cx - 95 * u, cy - 60 * u, cx + 5 * u, cy + 60 * u, PINK, INK, 6); c.ell(cx - 5 * u, cy - 60 * u, cx + 95 * u, cy + 60 * u, PINK, INK, 6)
        c.line([(cx, cy - 55 * u), (cx, cy + 55 * u)], 5)
        for dx, dy in ((-55, -20), (-40, 20), (50, -20), (40, 22)): c.arc(cx + (dx - 18) * u, cy + (dy - 14) * u, cx + (dx + 18) * u, cy + (dy + 14) * u, 200, 340, 5)
    elif name == 'clock':
        c.circ(cx, cy, 82 * u, WHITE, INK, 7)
        for i in range(12): a = i * math.pi / 6; c.line([(cx + math.sin(a) * 66 * u, cy - math.cos(a) * 66 * u), (cx + math.sin(a) * 76 * u, cy - math.cos(a) * 76 * u)], 4)
        a = now * 0.9; c.line([(cx, cy), (cx + math.sin(a) * 50 * u, cy - math.cos(a) * 50 * u)], 6, ACC); a2 = now * 0.075; c.line([(cx, cy), (cx + math.sin(a2) * 34 * u, cy - math.cos(a2) * 34 * u)], 7)
    elif name == 'book':
        c.poly([(cx - 90 * u, cy - 55 * u), (cx - 5 * u, cy - 40 * u), (cx - 5 * u, cy + 60 * u), (cx - 90 * u, cy + 45 * u)], BLUE, INK, 6)
        c.poly([(cx + 90 * u, cy - 55 * u), (cx + 5 * u, cy - 40 * u), (cx + 5 * u, cy + 60 * u), (cx + 90 * u, cy + 45 * u)], WHITE, INK, 6)
        for i in range(4): c.line([(cx + 20 * u, cy - 20 * u + i * 20 * u), (cx + 75 * u, cy - 28 * u + i * 20 * u)], 3)
    elif name == 'phone':
        c.rr(cx - 45 * u, cy - 80 * u, cx + 45 * u, cy + 80 * u, 14 * u, INK, INK, 4); c.rr(cx - 36 * u, cy - 64 * u, cx + 36 * u, cy + 60 * u, 6 * u, (170, 214, 240), None, 0)
        c.circ(cx + 26 * u, cy - 58 * u, 11 * u + 3 * math.sin(now * 6) * u, ACC, None, 0)
        for i in range(3): c.line([(cx - 24 * u, cy - 28 * u + i * 22 * u), (cx + 20 * u, cy - 28 * u + i * 22 * u)], 4, WHITE)
    elif name == 'house':
        c.rr(cx - 70 * u, cy - 10 * u, cx + 70 * u, cy + 75 * u, 4, SOFT, INK, 6); c.poly([(cx - 85 * u, cy - 8 * u), (cx, cy - 78 * u), (cx + 85 * u, cy - 8 * u)], ACC, INK, 6)
        c.rr(cx - 16 * u, cy + 20 * u, cx + 16 * u, cy + 75 * u, 3, BLUE, INK, 5)
    elif name == 'eye':
        c.ell(cx - 90 * u, cy - 45 * u, cx + 90 * u, cy + 45 * u, WHITE, INK, 7); c.circ(cx, cy, 30 * u, BLUE, INK, 5); c.circ(cx + 4 * u, cy - 3 * u, 13 * u, INK, None, 0); c.circ(cx + 12 * u, cy - 11 * u, 5 * u, WHITE, None, 0)
    elif name == 'heart':
        s = 1 + 0.06 * math.sin(now * 7); c.circ(cx - 32 * u * s, cy - 18 * u * s, 38 * u * s, ACC, INK, 6); c.circ(cx + 32 * u * s, cy - 18 * u * s, 38 * u * s, ACC, INK, 6)
        c.poly([(cx - 66 * u * s, cy - 2 * u * s), (cx + 66 * u * s, cy - 2 * u * s), (cx, cy + 72 * u * s)], ACC, None, 0); c.line([(cx - 64 * u * s, cy + 6 * u * s), (cx, cy + 72 * u * s), (cx + 64 * u * s, cy + 6 * u * s)], 6)
    elif name == 'moon':
        c.circ(cx, cy, 70 * u, GOLD, INK, 6); c.circ(cx + 32 * u, cy - 14 * u, 58 * u, PAPER, None, 0)
        for dx, dy, s in ((60, -60, 9), (80, 10, 6), (30, 65, 7)): c.circ(cx + dx * u, cy + dy * u, s * u * (1 + .2 * math.sin(now * 5 + dx)), GOLD, None, 0)
    elif name == 'sun':
        for i in range(10): a = i * math.pi / 5 + now * .4; c.line([(cx + math.cos(a) * 72 * u, cy + math.sin(a) * 72 * u), (cx + math.cos(a) * 95 * u, cy + math.sin(a) * 95 * u)], 6, GOLD)
        c.circ(cx, cy, 55 * u, GOLD, INK, 6)
    elif name == 'crowd':
        for dx, col in ((-62, BLUE), (0, ACC), (62, GREEN)):
            b = wob(dx, now, 3) * u; c.circ(cx + dx * u, cy - 38 * u + b, 24 * u, WHITE, INK, 5); c.rr(cx + (dx - 28) * u, cy - 8 * u + b, cx + (dx + 28) * u, cy + 66 * u, 16 * u, col, INK, 5)
    elif name == 'chart':
        c.line([(cx - 85 * u, cy - 70 * u), (cx - 85 * u, cy + 70 * u), (cx + 90 * u, cy + 70 * u)], 6)
        for i, (hh, col) in enumerate(((50, BLUE), (100, GOLD), (75, ACC))):
            g = ease((now * 1.2 - i * .25) % 3 / 1.0 if False else 1); c.rr(cx - 62 * u + i * 54 * u, cy + 66 * u - hh * u * g, cx - 24 * u + i * 54 * u, cy + 66 * u, 3, col, INK, 4)
    elif name == 'face':
        c.circ(cx, cy, 78 * u, GOLD, INK, 6); c.circ(cx - 26 * u, cy - 14 * u, 8 * u, INK, None, 0); c.circ(cx + 26 * u, cy - 14 * u, 8 * u, INK, None, 0); c.arc(cx - 40 * u, cy - 10 * u, cx + 40 * u, cy + 50 * u, 20, 160, 6)
    elif name == 'lock':
        c.arc(cx - 40 * u, cy - 90 * u, cx + 40 * u, cy + 10 * u, 180, 360, 9); c.rr(cx - 62 * u, cy - 20 * u, cx + 62 * u, cy + 70 * u, 10, GOLD, INK, 6); c.circ(cx, cy + 22 * u, 10 * u, INK, None, 0)
    elif name == 'scroll':
        c.rr(cx - 62 * u, cy - 74 * u, cx + 62 * u, cy + 74 * u, 8, (236, 220, 180), INK, 6); c.ell(cx - 72 * u, cy - 84 * u, cx + 72 * u, cy - 62 * u, (214, 190, 140), INK, 5); c.ell(cx - 72 * u, cy + 62 * u, cx + 72 * u, cy + 84 * u, (214, 190, 140), INK, 5)
        for i in range(5): c.line([(cx - 40 * u, cy - 44 * u + i * 20 * u), (cx + 40 * u - (i % 2) * 20 * u, cy - 44 * u + i * 20 * u)], 3)
    elif name == 'question':
        c.text((cx, cy), '?', 190 * u, ACC, 'mm', stroke=4)
    else:   # bulb
        for i in range(8): a = -math.pi / 2 + (i - 3.5) * math.pi / 5; c.line([(cx + math.cos(a) * 80 * u, cy - 15 * u + math.sin(a) * 80 * u), (cx + math.cos(a) * (100 + 6 * math.sin(now * 6 + i)) * u, cy - 15 * u + math.sin(a) * (100 + 6 * math.sin(now * 6 + i)) * u)], 5, GOLD)
        c.circ(cx, cy - 15 * u, 56 * u, (255, 232, 130), INK, 6); c.rr(cx - 26 * u, cy + 38 * u, cx + 26 * u, cy + 72 * u, 6, SOFT, INK, 5); c.line([(cx - 14 * u, cy + 4 * u), (cx - 5 * u, cy + 24 * u), (cx + 5 * u, cy + 4 * u), (cx + 14 * u, cy + 24 * u)], 4)

# ---------------- v4: the stick-man rig (joint angles, so every action can move) ----------------
GROUND = 585
def lerp(a, b, t): return a + (b - a) * t
def limb(a0, a1, L1=56, L2=56):
    r0, r1 = math.radians(a0), math.radians(a0 + a1)
    p1 = (math.sin(r0) * L1, math.cos(r0) * L1)
    return p1, (p1[0] + math.sin(r1) * L2, p1[1] + math.cos(r1) * L2)

BASE_A = dict(lean=0, tilt=0, la=-26, le=14, ra=28, re=16, ll=5, lk=0, rl=-5, rk=0, dy=0, rot=0, sit=0, expr='n')
ACTS = ['idle', 'explain', 'point', 'think', 'shrug', 'cheer', 'wave', 'walk', 'run', 'sit', 'sleep', 'surprised', 'laugh', 'sad', 'read', 'phone', 'lookup', 'dance', 'no', 'jump']
def acts(name, t, tc=0.0, ph=0.0, aim=100.0):
    """Joint angles for an action. t = seconds into the beat, tc = seconds relative to the key word (negative = before it is spoken), ph = walking phase, aim = pointing angle."""
    e = 0.4 + 0.6 * ease((tc + .15) / .35); s = math.sin; a = dict(BASE_A)
    if name == 'idle': a.update(la=-30 + 6 * s(t * 2.1), ra=32 + 6 * s(t * 2.1 + 1.5), re=22 + 6 * s(t * 1.7), le=18)
    elif name == 'explain': a.update(ra=55 + 30 * e * s(t * 4.2), re=-35 + 25 * e * s(t * 4.2 + 1.2), la=-18 + 8 * s(t * 2.5), le=20 + 10 * s(t * 3), lean=3 + 2 * s(t * 2))
    elif name == 'point': k = ease((tc + .1) / .3); a.update(ra=lerp(45, aim, k), re=lerp(35, 0, k), la=-12, le=10, lean=3 * k)
    elif name == 'think': a.update(ra=20, re=168, la=-12, le=10, tilt=-6 + 4 * s(t * 1.5), expr='think')
    elif name == 'shrug': k = ease(t / .3) * e; a.update(ra=lerp(8, 48, k), re=lerp(8, 100, k), la=-lerp(8, 48, k), le=-lerp(8, 100, k), dy=-3 * k, tilt=8 * s(t * 2))
    elif name == 'cheer': a.update(ra=138 + 10 * s(t * 8), re=22, la=-138 - 10 * s(t * 8), le=-22, dy=18 * abs(s(t * 6)) * e, expr='happy')
    elif name == 'wave': a.update(ra=150, re=-25 + 30 * s(t * 9), la=-8, le=8, expr='happy')
    elif name == 'walk': a.update(ll=32 * s(ph), rl=-32 * s(ph), lk=-42 * max(0, s(ph + 1.3)), rk=-42 * max(0, -s(ph + 1.3)), la=-28 * s(ph), ra=28 * s(ph), le=10, re=10, dy=4 * abs(s(ph)), lean=4)
    elif name == 'run': a.update(ll=55 * s(ph), rl=-55 * s(ph), lk=-80 * max(0, s(ph + 1.3)), rk=-80 * max(0, -s(ph + 1.3)), la=-50 * s(ph), ra=50 * s(ph), le=-85, re=-85, dy=10 * abs(s(ph)), lean=14)
    elif name == 'sit': a.update(sit=1, ll=88, lk=-88, rl=88, rk=-88, ra=30, re=60, la=-10, le=20)
    elif name == 'sleep': a.update(rot=88, sit=2, ra=4, la=-4, expr='sleep')
    elif name == 'surprised':
        st = ease(tc / .2) if tc > 0 else 0.0
        a.update(lean=-14 * st, ra=lerp(8, 75, st), re=lerp(8, 35, st), la=-lerp(8, 75, st), le=-lerp(8, 35, st), dy=22 * max(0, 1 - tc * 4) if tc > 0 else 0, expr='surp' if tc > -.1 else 'n')
    elif name == 'laugh': a.update(lean=-8, tilt=-10, dy=5 * abs(s(t * 16)), ra=35, re=100, la=-10, le=10, expr='laugh')
    elif name == 'sad': a.update(lean=12, tilt=22, ra=4, la=-4, expr='sad')
    elif name == 'read': a.update(ra=62, re=85, la=-30, le=70, tilt=14)
    elif name == 'phone': a.update(ra=75, re=80, la=-20, le=10, tilt=16)
    elif name == 'lookup': a.update(tilt=-18, ra=150, re=130, la=-10, le=8)
    elif name == 'dance': a.update(ra=120 + 30 * s(t * 6), re=20, la=-(120 + 30 * s(t * 6 + 3)), le=-20, dy=14 * abs(s(t * 6)), ll=12 * s(t * 6), rl=-12 * s(t * 6), expr='happy')
    elif name == 'no': a.update(ra=100, re=80, la=-10, le=10, tilt=14 * s(t * 8), lean=-3)
    elif name == 'jump': a.update(ra=125, re=20, la=-125, le=-20, dy=48 * abs(s(t * 5)) * e, expr='happy')
    else: a.update(ra=8, la=-8)
    return a
def mix_a(a, b, k):
    out = {}
    for key in a:
        out[key] = lerp(a[key], b[key], k) if key != 'expr' else (b[key] if k > .5 else a[key])
    return out

def rig(c, x, ground, s, a, now, talk, d=1, mouth=0.0, blink=False):
    """Draws the stick narrator. a = joint angles. Returns key points (hands, head) for props and emotes."""
    hipy = ground - 104 * s - a['dy'] * s
    if a['sit'] == 1: hipy = ground - 56 * s
    elif a['sit'] == 2: hipy = ground - 24 * s
    rot = math.radians(a['rot']); cr, sr = math.cos(rot), math.sin(rot)
    def T(p):
        px = p[0] * d; return (x + (px * cr - p[1] * sr) * s, hipy + (px * sr + p[1] * cr) * s)
    lean = math.radians(a['lean']); sh = (math.sin(lean) * 88, -math.cos(lean) * 88)
    hd = math.radians(a['lean'] + a['tilt']); hc = (sh[0] + math.sin(hd) * 54, sh[1] - math.cos(hd) * 54)
    def chain(origin, a0, a1):
        p1, p2 = limb(a0, a1); return [origin, (origin[0] + p1[0], origin[1] + p1[1]), (origin[0] + p2[0], origin[1] + p2[1])]
    legL = chain((0, 0), a['ll'], a['lk']); legR = chain((0, 0), a['rl'], a['rk']); armL = chain(sh, a['la'], a['le']); armR = chain(sh, a['ra'], a['re'])
    sw = 8 * s
    def draw(ch, foot=False):
        pts = [T(p) for p in ch]; c.line(pts, sw / s * s, INK)
        if foot: e = ch[-1]; c.line([T(e), T((e[0] + 15, e[1]))], sw / s * s, INK)
    draw(legL, True); draw(armL); draw(legR, True)
    c.line([T((0, 0)), T(sh)], sw, INK)
    draw(armR)
    for ch in (armL, armR): hx, hy = T(ch[-1]); c.circ(hx, hy, 5.5 * s, INK, None, 0)
    H0 = T(hc); c.circ(H0[0], H0[1], 44 * s, WHITE, INK, sw)
    tuft = [T((hc[0] + dx, hc[1] - 44 - dy)) for dx, dy in ((-16, -2), (-6, 12), (4, 3), (14, 14))]; c.line(tuft, sw * .7, INK)
    ex = [(hc[0] + 8, hc[1] - 6), (hc[0] + 30, hc[1] - 6)]; ex = [T(p) for p in ex]
    expr = a['expr']; closed = blink or expr == 'sleep'
    for p in ex:
        c.circ(p[0], p[1], 13 * s, None, INK, 3.5 * s)
        if closed: c.line([(p[0] - 8 * s, p[1]), (p[0] + 8 * s, p[1])], 3.5 * s, INK)
        else: c.circ(p[0] + 2 * s * d, p[1] + (3 * s if expr == 'sad' else 0), 4.2 * s, INK, None, 0)
    c.line([(ex[0][0] + 13 * s * d, ex[0][1]), (ex[1][0] - 13 * s * d, ex[1][1])], 3 * s, INK)
    if expr in ('surp', 'think', 'sad'):   # eyebrows
        for i, p in enumerate(ex):
            up = 16 if expr == 'surp' else 13; sl = (-5 if expr == 'think' and i == 1 else 5 if expr == 'sad' else 0)
            c.line([(p[0] - 10 * s, p[1] - up * s + sl * s * (1 if i == 0 else -1)), (p[0] + 10 * s, p[1] - up * s - sl * s * (1 if i == 0 else -1))], 3 * s, INK)
    if SM:   # bookish narrator: bow tie and a little cap
        bt = T((sh[0] * .98, sh[1] * .98 + 4)); c.poly([(bt[0] - 20 * s, bt[1] - 9 * s), (bt[0], bt[1]), (bt[0] - 20 * s, bt[1] + 9 * s)], ACC, INK, 3); c.poly([(bt[0] + 20 * s, bt[1] - 9 * s), (bt[0], bt[1]), (bt[0] + 20 * s, bt[1] + 9 * s)], ACC, INK, 3); c.circ(bt[0], bt[1], 4 * s, INK, None, 0)
        cap = T((hc[0], hc[1] - 40)); c.rr(cap[0] - 34 * s, cap[1] - 14 * s, cap[0] + 34 * s, cap[1] + 4 * s, 6 * s, (60, 90, 70), INK, 3)
    m = T((hc[0] + 20, hc[1] + 24))
    if expr == 'surp': c.ell(m[0] - 8 * s, m[1] - 10 * s, m[0] + 8 * s, m[1] + 10 * s, INK, INK, 2)
    elif expr == 'sad': c.arc(m[0] - 12 * s, m[1] - 2 * s, m[0] + 12 * s, m[1] + 16 * s, 200, 340, 3.5 * s)
    elif expr == 'sleep': c.line([(m[0] - 8 * s, m[1]), (m[0] + 8 * s, m[1])], 3.5 * s)
    elif talk or expr == 'laugh':
        h = (3 + 11 * mouth) * s; c.ell(m[0] - 9 * s, m[1] - h / 2, m[0] + 9 * s, m[1] + h / 2, INK, INK, 2)
    elif expr == 'happy': c.arc(m[0] - 13 * s, m[1] - 10 * s, m[0] + 13 * s, m[1] + 8 * s, 20, 160, 3.5 * s)
    else: c.line([(m[0] - 10 * s, m[1]), (m[0] + 10 * s, m[1] - 1 * s)], 3.5 * s)
    return {'hand_r': T(armR[-1]), 'hand_l': T(armL[-1]), 'head': (H0[0], H0[1] - 66 * s), 'chest': T((sh[0] * .5, sh[1] * .5)), 'sh': T(sh), 'foot': (x, ground)}

def figure(c, x, y, s, pose, now, talking=True):
    """Compatibility wrapper (thumbnail): draws the narrator standing with a named pose."""
    name = {'point': 'point', 'think': 'think', 'shrug': 'shrug', 'cheer': 'cheer'}.get(pose, 'idle')
    rig(c, x, y, s * 1.0, acts(name, now, 1.0), now, talking, 1, .5)

# ---------------- v4: backdrops (drawn once, cached) ----------------
SKYC = (190, 224, 242); GRASSC = (148, 198, 118); SANDC = (240, 208, 146); DARK = (28, 36, 74)
def _sky(c, col=SKYC, hz=585): c.d.rectangle([0, 0, W * K, hz * K], fill=col)
def _ground(c, col, y=GROUND):
    c.d.rectangle([0, y * K, W * K, H * K], fill=col); c.line([(0, y), (W, y)], 4, INK)
def _tree(c, x, y, u=1.0, col=(96, 168, 92)):
    c.rr(x - 10 * u, y - 90 * u, x + 10 * u, y, 3, (140, 98, 60), INK, 4)
    for dx, dy, r in ((0, -130, 52), (-34, -100, 36), (34, -100, 36)): c.circ(x + dx * u, y + dy * u, r * u, col, INK, 4)
def bg_plain(c): _ground(c, SOFT)
def bg_park(c):
    _sky(c); c.ell(-200, 440, 700, 760, (170, 214, 140), INK, 4); c.ell(500, 470, 1500, 800, (160, 206, 130), INK, 4); _ground(c, GRASSC); _tree(c, 150, 585, 1.5); _tree(c, 1140, 585, 1.2)
    c.circ(1000, 120, 48, (255, 226, 120), INK, 5)
def bg_desert(c):
    _sky(c, (252, 226, 178)); c.circ(980, 150, 70, (255, 214, 120), INK, 5)
    c.poly([(150, 480), (260, 330), (370, 480)], (226, 188, 120), INK, 4); c.poly([(300, 480), (380, 390), (460, 480)], (214, 176, 110), INK, 4)
    c.ell(-250, 430, 600, 800, (236, 200, 134), INK, 4); c.ell(450, 400, 1500, 820, (228, 190, 122), INK, 4); _ground(c, SANDC)
    c.rr(1130, 470, 1150, 585, 8, (90, 160, 90), INK, 4); c.rr(1105, 500, 1130, 515, 6, (90, 160, 90), INK, 3); c.rr(1105, 500, 1117, 540, 6, (90, 160, 90), INK, 3)
def bg_city(c):
    _sky(c, (200, 220, 236)); import random as _r; r = _r.Random(4); x = 0
    while x < W:
        w = r.randint(90, 170); h = r.randint(180, 400); col = r.choice([(150, 160, 190), (170, 150, 170), (140, 170, 180), (182, 170, 150)])
        c.rr(x, 585 - h, x + w, 585, 2, col, INK, 4)
        for yy in range(585 - h + 20, 560, 38):
            for xx in range(x + 14, x + w - 20, 32): c.rr(xx, yy, xx + 16, yy + 22, 2, (255, 236, 160) if r.random() < .5 else (120, 140, 170), None, 0)
        x += w
    _ground(c, (120, 124, 136))
    for xx in range(40, W, 140): c.line([(xx, 650), (xx + 60, 650)], 6, (240, 240, 230))
def bg_home(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(238, 224, 198)); c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(196, 152, 112)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    c.rr(120, 90, 360, 330, 6, SKYC, INK, 8); c.line([(240, 90), (240, 330)], 5); c.line([(120, 210), (360, 210)], 5)
    c.rr(520, 120, 700, 240, 4, (250, 236, 200), INK, 6); c.circ(610, 180, 30, GREEN, INK, 4); c.rr(940, 330, 1180, 380, 8, (160, 110, 80), INK, 5); c.rr(1010, 380, 1030, 585, 3, (160, 110, 80), INK, 4)
    c.ell(480, 610, 800, 700, (200, 100, 100), INK, 4)
def bg_bedroom(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(66, 70, 128)); c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(92, 76, 100)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    c.rr(900, 90, 1160, 330, 6, (30, 36, 84), INK, 8); c.circ(1060, 190, 42, GOLD, INK, 4); c.circ(1080, 176, 36, (30, 36, 84), None, 0)
    for xx, yy in ((930, 130), (1000, 290), (1120, 120), (940, 250)): c.circ(xx, yy, 3, WHITE, None, 0)
    c.rr(130, 330, 190, 420, 4, (120, 100, 140), INK, 4)
def bg_ocean(c):
    _sky(c, SKYC, 400); c.d.rectangle([0, 380 * K, W * K, 540 * K], fill=(84, 164, 214)); c.line([(0, 380), (W, 380)], 4, INK)
    c.circ(220, 140, 52, (255, 226, 120), INK, 5); c.d.rectangle([0, 540 * K, W * K, H * K], fill=SANDC); c.line([(0, 540), (W, 540)], 4, INK)
def bg_space(c):
    import random as _r; r = _r.Random(8); c.d.rectangle([0, 0, W * K, H * K], fill=(14, 16, 44))
    for _ in range(90): c.circ(r.randint(0, W), r.randint(0, 540), r.choice([1.5, 2, 2.5]), WHITE, None, 0)
    c.circ(1000, 170, 70, (210, 120, 90), INK, 5); c.ell(900, 150, 1100, 190, None, (240, 200, 150), 5); c.circ(250, 140, 40, (120, 150, 220), INK, 4)
    c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(110, 112, 130)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    for xx, yy, rr_ in ((200, 640, 30), (700, 660, 22), (1050, 630, 36)): c.ell(xx - rr_, yy - rr_ / 2, xx + rr_, yy + rr_ / 2, (90, 92, 110), INK, 3)
def bg_brain(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(236, 228, 248)); import random as _r; r = _r.Random(6); pts = [(r.randint(40, W - 40), r.randint(40, 540)) for _ in range(26)]
    for i, p in enumerate(pts):
        for q in pts[i + 1:i + 4]: c.line([p, q], 2.5, (196, 180, 226))
    for p in pts: c.circ(p[0], p[1], 9, (206, 190, 236), (170, 150, 210), 3)
    _ground(c, (216, 204, 236))
def bg_night(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=DARK); import random as _r; r = _r.Random(2)
    for _ in range(60): c.circ(r.randint(0, W), r.randint(0, 400), 2, WHITE, None, 0)
    c.circ(1020, 130, 52, (250, 236, 170), INK, 4); c.circ(1044, 118, 46, DARK, None, 0)
    for x0, h in ((100, 150), (330, 190), (760, 170)): c.rr(x0, 585 - h, x0 + 150, 585, 2, (46, 52, 96), INK, 4); c.poly([(x0 - 10, 585 - h), (x0 + 75, 585 - h - 60), (x0 + 160, 585 - h)], (60, 44, 80), INK, 4); c.rr(x0 + 55, 585 - h + 40, x0 + 95, 585 - h + 90, 2, (255, 224, 130), None, 0)
    _ground(c, (36, 62, 70))
def bg_forest(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(176, 212, 170))
    for x0, u in ((60, 1.9), (330, 1.5), (600, 1.8), (880, 1.5), (1150, 1.9)): _tree(c, x0, 585, u, (72, 140, 82))
    _ground(c, (110, 160, 90))
def bg_mountain(c):
    _sky(c); c.poly([(-50, 585), (260, 230), (560, 585)], (150, 156, 170), INK, 4); c.poly([(380, 585), (720, 150), (1100, 585)], (138, 144, 160), INK, 4); c.poly([(900, 585), (1150, 300), (1400, 585)], (156, 162, 176), INK, 4)
    c.poly([(640, 235), (720, 150), (800, 235), (760, 220), (720, 245), (680, 220)], WHITE, INK, 3); c.poly([(222, 290), (260, 230), (298, 290), (260, 280)], WHITE, INK, 3); _ground(c, GRASSC)
def bg_office(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(214, 224, 232)); c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(150, 150, 160)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    c.rr(80, 80, 420, 330, 6, SKYC, INK, 8); c.line([(250, 80), (250, 330)], 5); c.rr(780, 110, 1000, 230, 4, WHITE, INK, 5)
    for i in range(3): c.line([(810, 140 + i * 30), (960 - i * 30, 140 + i * 30)], 4, BLUE)
    c.rr(1040, 470, 1240, 585, 4, (160, 120, 90), INK, 5)
def bg_school(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(232, 222, 196)); c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(184, 148, 108)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    c.rr(300, 70, 980, 360, 8, (52, 96, 80), (140, 100, 60), 10)
    c.line([(350, 130), (520, 130)], 4, WHITE); c.line([(350, 170), (700, 170)], 4, WHITE); c.circ(860, 200, 40, None, WHITE, 4); c.line([(380, 250), (460, 300), (560, 240), (660, 310)], 4, WHITE)
def bg_stage(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(120, 40, 56))
    for x0 in range(0, W, 120): c.line([(x0, 0), (x0 + 30, 585)], 8, (150, 56, 72))
    c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(176, 130, 86)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    c.poly([(560, 0), (720, 0), (900, 585), (380, 585)], (255, 236, 170), None, 0)
def bg_history(c):
    _sky(c, (244, 222, 190))
    for x0 in (120, 300, 980, 1140):
        c.rr(x0, 150, x0 + 60, 585, 2, (232, 220, 200), INK, 4); c.rr(x0 - 12, 120, x0 + 72, 152, 2, (220, 206, 184), INK, 4)
    c.poly([(60, 120), (640, 40), (1220, 120)], (226, 210, 186), INK, 4); _ground(c, (206, 190, 160))
BGS = {'plain': bg_plain, 'park': bg_park, 'desert': bg_desert, 'city': bg_city, 'home': bg_home, 'bedroom': bg_bedroom, 'ocean': bg_ocean, 'space': bg_space, 'brain': bg_brain, 'night': bg_night,
       'forest': bg_forest, 'mountain': bg_mountain, 'office': bg_office, 'school': bg_school, 'stage': bg_stage, 'history': bg_history}

def bg_library(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(120, 84, 60)); c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(92, 62, 44)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    import random as _r; r = _r.Random(11)
    for sx in (40, 700):
        c.rr(sx, 70, sx + 540, 585, 4, (96, 64, 44), INK, 5)
        for row in range(4):
            y0 = 90 + row * 120; c.line([(sx + 10, y0 + 100), (sx + 530, y0 + 100)], 6, (70, 46, 32)); x = sx + 18
            while x < sx + 500:
                w = r.randint(16, 30); h = r.randint(60, 96); c.rr(x, y0 + 100 - h, x + w, y0 + 100, 2, r.choice([ACC, BLUE, GREEN, GOLD, (150, 90, 130), (90, 140, 150)]), INK, 3); x += w + 2
def bg_study(c):
    c.d.rectangle([0, 0, W * K, H * K], fill=(214, 190, 150)); c.d.rectangle([0, GROUND * K, W * K, H * K], fill=(130, 96, 66)); c.line([(0, GROUND), (W, GROUND)], 4, INK)
    c.rr(90, 80, 330, 330, 6, (250, 222, 150), INK, 8); c.circ(210, 205, 70, (255, 240, 190), None, 0); c.line([(210, 80), (210, 330)], 5); c.line([(90, 205), (330, 205)], 5)
    c.rr(800, 340, 1220, 380, 8, (120, 84, 56), INK, 5); c.rr(840, 380, 870, 585, 3, (120, 84, 56), INK, 4); c.rr(1150, 380, 1180, 585, 3, (120, 84, 56), INK, 4)
    c.rr(520, 90, 700, 230, 4, (170, 130, 96), INK, 6); c.line([(540, 130), (680, 130)], 4, INK); c.line([(540, 170), (650, 170)], 4, INK)
def bg_bookshop(c):
    _sky(c, (232, 214, 188)); c.d.rectangle([0, 0, W * K, 120 * K], fill=(52, 96, 80)); c.text((640, 60), 'BOOKS', 70, GOLD, 'mm', stroke=0)
    c.rr(60, 160, 360, 585, 4, (150, 100, 70), INK, 5); c.rr(920, 160, 1220, 585, 4, (150, 100, 70), INK, 5); c.rr(430, 170, 850, 540, 6, (186, 224, 236), INK, 6)
    for xx in range(90, 340, 40): c.rr(xx, 200, xx + 28, 300, 2, (ACC, BLUE, GREEN, GOLD)[(xx // 40) % 4], INK, 3)
    _ground(c, (176, 150, 122))
BGS.update({'library': bg_library, 'study': bg_study, 'bookshop': bg_bookshop})

SKYBG = {'park', 'desert', 'city', 'ocean', 'mountain', 'history'}
def bg_anim(c, name, now):
    if name in SKYBG:
        for i, (x0, y0, sc) in enumerate(((100, 100, 1.0), (560, 70, 1.3), (900, 160, .8))):
            x = (x0 + now * (8 + 4 * i)) % (W + 300) - 150
            for dx, dy, r in ((0, 0, 30), (30, -10, 36), (62, 4, 28)): c.circ(x + dx * sc, y0 + dy * sc, r * sc, WHITE, None, 0)
    if name == 'ocean':
        for row in range(3):
            for x0 in range(-80, W + 80, 120): c.arc(x0 + ((now * 30 + row * 40) % 120), 410 + row * 45, x0 + 90 + ((now * 30 + row * 40) % 120), 440 + row * 45, 190, 350, 5, WHITE)
    if name in ('night', 'space', 'bedroom'):
        for i in range(6):
            sx = (i * 211 + 60) % W; sy = (i * 97 + 40) % 300; r = 3 + 2 * math.sin(now * 3 + i); c.circ(sx, sy, r, WHITE, None, 0)
    if name == 'brain':
        for i in range(5):
            a = now * .6 + i * 1.3; c.circ(640 + math.cos(a) * (200 + 90 * i), 280 + math.sin(a * 1.2) * (110 + 20 * i), 7, (150, 120, 210), None, 0)

# ---------------- v4: props (things the story is about) ----------------
def P_dog(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u); col = (205, 150, 92)
    for lx in (-38, -18, 22, 40): c.line([S(lx, -34), S(lx + 3 * math.sin(now * 9 + lx), 0)], 8 * u, INK)
    c.line([S(-58, -58), S(-86, -86 + 12 * math.sin(now * 14))], 7 * u, INK)
    c.ell(*S(-62, -80), *S(48, -30), col, INK, 5); c.circ(*S(58, -80), 27 * u, col, INK, 5)
    c.poly([S(40, -100), S(30, -62), S(52, -76)], (150, 100, 60), INK, 4); c.ell(*S(60, -82), *S(92, -58), (230, 200, 160), INK, 4)
    c.circ(*S(94, -72), 5 * u, INK, None, 0); c.circ(*S(62, -90), 4 * u, INK, None, 0)
def P_cat(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u); col = (150, 150, 160)
    c.line([S(-52, -40), S(-90, -50), S(-100, -100 + 6 * math.sin(now * 4))], 7 * u, INK)
    c.ell(*S(-56, -74), *S(40, -26), col, INK, 5)
    for lx in (-34, 24): c.line([S(lx, -32), S(lx, 0)], 8 * u, INK)
    c.circ(*S(52, -80), 26 * u, col, INK, 5); c.poly([S(32, -98), S(36, -128), S(52, -102)], col, INK, 4); c.poly([S(56, -102), S(72, -128), S(76, -96)], col, INK, 4)
    for dx in (46, 62): c.circ(*S(dx, -84), 3.5 * u, INK, None, 0)
    for dy in (-70, -64): c.line([S(60, dy), S(92, dy - 6)], 2 * u); c.line([S(60, dy), S(92, dy + 6)], 2 * u)
def P_bird(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u + 6 * math.sin(now * 5) * u); f = math.sin(now * 12) * 22
    c.poly([S(-12, -4), S(-60, -30 + f), S(10, -26)], (140, 180, 230), INK, 4); c.ell(*S(-40, -26), *S(34, 20), (110, 160, 220), INK, 5); c.circ(*S(36, -20), 20 * u, (110, 160, 220), INK, 5)
    c.poly([S(52, -22), S(78, -14), S(52, -8)], GOLD, INK, 3); c.circ(*S(40, -26), 3.5 * u, INK, None, 0); c.poly([S(-38, 0), S(-80, 16), S(-36, 14)], (140, 180, 230), INK, 3)
def P_fish(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u + 5 * math.sin(now * 3) * u)
    c.poly([S(-40, 0), S(-82, -26 + 6 * math.sin(now * 9)), S(-82, 26 - 6 * math.sin(now * 9))], ACC, INK, 4); c.ell(*S(-56, -32), *S(50, 32), (250, 150, 90), INK, 5); c.circ(*S(28, -8), 5 * u, INK, None, 0)
def P_tree(c, x, y, u, now): _tree(c, x, y, u * 1.2)
def P_car(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u)
    c.rr(*S(-90, -62), *S(90, -22), 12 * u, ACC, INK, 5); c.poly([S(-50, -62), S(-30, -98), S(36, -98), S(62, -62)], (240, 120, 100), INK, 5); c.poly([S(-38, -66), S(-24, -92), S(2, -92), S(2, -66)], SKYC, INK, 3)
    for wx in (-52, 52): c.circ(*S(wx, -18), 22 * u, INK, INK, 3); c.circ(*S(wx, -18), 9 * u, SOFT, None, 0)
def P_ball(c, x, y, u, now):
    yy = abs(math.sin(now * 4.5)) * 70 * u; c.ell(x - 26 * u, y - 52 * u - yy, x + 26 * u, y - yy, ACC, INK, 5); c.line([(x - 26 * u, y - 26 * u - yy), (x + 26 * u, y - 26 * u - yy)], 4)
def P_apple(c, x, y, u, now):
    c.circ(x, y, 44 * u, ACC, INK, 5); c.line([(x, y - 44 * u), (x + 6 * u, y - 66 * u)], 5 * u); c.poly([(x + 6 * u, y - 60 * u), (x + 40 * u, y - 74 * u), (x + 24 * u, y - 50 * u)], GREEN, INK, 3)
def P_cup(c, x, y, u, now):
    c.rr(x - 40 * u, y - 40 * u, x + 30 * u, y + 40 * u, 8 * u, WHITE, INK, 5); c.arc(x + 14 * u, y - 24 * u, x + 60 * u, y + 20 * u, 270, 90, 6)
    for i in range(3): xx = x - 20 * u + i * 20 * u; c.line([(xx, y - 52 * u), (xx + 6 * u * math.sin(now * 3 + i), y - 70 * u), (xx, y - 88 * u)], 3.5 * u, (160, 160, 170))
def P_bed(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u)
    c.rr(*S(-110, -70), *S(110, -30), 6 * u, (190, 140, 100), INK, 5); c.rr(*S(-110, -100), *S(-92, 0), 3, (150, 100, 70), INK, 4); c.rr(*S(92, -60), *S(110, 0), 3, (150, 100, 70), INK, 4)
    c.rr(*S(-100, -84), *S(-50, -66), 8 * u, WHITE, INK, 4); c.rr(*S(-40, -80), *S(100, -62), 6 * u, BLUE, INK, 4)
def P_cloud(c, x, y, u, now):
    for dx, dy, r in ((-40, 6, 34), (0, -12, 44), (44, 6, 34)): c.circ(x + dx * u, y + dy * u, r * u, (216, 224, 236), INK, 4)
    for i in range(4): c.line([(x - 40 * u + i * 26 * u, y + 50 * u + (now * 90 + i * 30) % 40), (x - 46 * u + i * 26 * u, y + 66 * u + (now * 90 + i * 30) % 40)], 3.5, BLUE)
def P_money(c, x, y, u, now):
    sq = abs(math.cos(now * 3)); c.ell(x - 46 * u * (.15 + .85 * sq), y - 46 * u, x + 46 * u * (.15 + .85 * sq), y + 46 * u, GOLD, INK, 5)
    if sq > .5: c.text((x, y), '$', 56 * u, INK, 'mm')
def P_mirror(c, x, y, u, now):
    c.line([(x, y + 50 * u), (x, y + 112 * u)], 10 * u, (150, 100, 60)); c.ell(x - 62 * u, y - 86 * u, x + 62 * u, y + 56 * u, (206, 230, 244), (190, 150, 70), 9)
    c.circ(x, y - 14 * u, 28 * u, WHITE, INK, 4); c.circ(x - 10 * u, y - 20 * u, 3.5 * u, INK, None, 0); c.circ(x + 10 * u, y - 20 * u, 3.5 * u, INK, None, 0); c.arc(x - 12 * u, y - 14 * u, x + 12 * u, y + 2 * u, 20, 160, 3)
def P_camera(c, x, y, u, now):
    c.rr(x - 62 * u, y - 36 * u, x + 62 * u, y + 40 * u, 10 * u, (90, 96, 110), INK, 5); c.rr(x - 20 * u, y - 52 * u, x + 20 * u, y - 36 * u, 4, (90, 96, 110), INK, 4); c.circ(x, y + 2 * u, 26 * u, (160, 200, 230), INK, 5)
    if int(now * 2) % 2 == 0: c.circ(x + 46 * u, y - 22 * u, 5 * u, ACC, None, 0)
def P_pyramid(c, x, y, u, now): c.poly([(x - 110 * u, y), (x, y - 150 * u), (x + 110 * u, y)], (232, 196, 120), INK, 5); c.line([(x, y - 150 * u), (x - 20 * u, y)], 3, INK)
def P_camel(c, x, y, u, now):
    S = lambda dx, dy: (x + dx * u, y + dy * u + 4 * abs(math.sin(now * 4)) * u); col = (214, 170, 100)
    for lx in (-50, -26, 30, 54): c.line([S(lx, -50), S(lx + 6 * math.sin(now * 5 + lx), 0)], 8 * u, INK)
    c.ell(*S(-70, -110), *S(70, -42), col, INK, 5); c.circ(*S(-28, -118), 24 * u, col, INK, 5); c.circ(*S(22, -118), 24 * u, col, INK, 5)
    c.line([S(66, -90), S(90, -150)], 16 * u, col); c.line([S(66, -90), S(90, -150)], 4, INK); c.ell(*S(80, -170), *S(122, -142), col, INK, 5); c.circ(*S(108, -158), 3.5 * u, INK, None, 0)
def P_mountain(c, x, y, u, now):
    c.poly([(x - 130 * u, y), (x, y - 190 * u), (x + 130 * u, y)], (150, 156, 172), INK, 5); c.poly([(x - 36 * u, y - 140 * u), (x, y - 190 * u), (x + 36 * u, y - 140 * u), (x + 10 * u, y - 150 * u), (x - 10 * u, y - 134 * u)], WHITE, INK, 3)
def P_flag(c, x, y, u, now):
    c.line([(x, y), (x, y - 190 * u)], 7 * u)
    pts = [(x + i * 8 * u, y - 190 * u + 6 * u * math.sin(now * 5 + i * .7)) for i in range(11)]; pts2 = [(p[0], p[1] + 80 * u) for p in reversed(pts)]; c.poly(pts + pts2, ACC, INK, 4)
def P_star(c, x, y, u, now):
    pts = []
    for i in range(10): a = -math.pi / 2 + i * math.pi / 5 + now * .8; r = (50 if i % 2 == 0 else 22) * u; pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
    c.poly(pts, GOLD, INK, 5)
def P_laptop(c, x, y, u, now):
    c.rr(x - 60 * u, y - 70 * u, x + 60 * u, y + 10 * u, 6, (60, 66, 84), INK, 5); c.rr(x - 50 * u, y - 60 * u, x + 50 * u, y, 3, (170, 214, 240), None, 0)
    c.poly([(x - 80 * u, y + 40 * u), (x - 60 * u, y + 10 * u), (x + 60 * u, y + 10 * u), (x + 80 * u, y + 40 * u)], (150, 154, 168), INK, 4)
    for i in range(3): c.line([(x - 36 * u, y - 44 * u + i * 16 * u), (x + 30 * u - i * 12 * u, y - 44 * u + i * 16 * u)], 3.5, BLUE)
def P_door(c, x, y, u, now):
    k = .5 + .5 * math.sin(now * 1.6); c.rr(x - 50 * u, y - 150 * u, x + 50 * u, y, 4, (40, 40, 60), INK, 5); c.poly([(x - 50 * u, y - 150 * u), (x - 50 * u + 70 * u * (.3 + k * .4), y - 140 * u), (x - 50 * u + 70 * u * (.3 + k * .4), y - 10 * u), (x - 50 * u, y)], (176, 126, 84), INK, 4)
def P_fire(c, x, y, u, now):
    for i, (w, h, col) in enumerate(((46, 110, ACC), (32, 80, GOLD), (16, 50, (255, 240, 170)))):
        hh = h * (1 + .12 * math.sin(now * 11 + i * 2)); c.poly([(x - w * u, y), (x - w * .5 * u, y - hh * .6 * u), (x, y - hh * u), (x + w * .5 * u, y - hh * .6 * u), (x + w * u, y)], col, INK if i == 0 else None, 4)
def P_battery(c, x, y, u, now):
    lv = 0.12 + .88 * (.5 + .5 * math.cos(now * 1.3)); c.rr(x - 66 * u, y - 36 * u, x + 60 * u, y + 36 * u, 8 * u, WHITE, INK, 6); c.rr(x + 60 * u, y - 14 * u, x + 76 * u, y + 14 * u, 3, INK, INK, 2)
    c.rr(x - 58 * u, y - 28 * u, x - 58 * u + 110 * u * lv, y + 28 * u, 4, GREEN if lv > .3 else ACC, None, 0)
def P_zzz(c, x, y, u, now):
    for i in range(3):
        k = (now * .6 + i / 3) % 1; c.text((x + 16 * i * u + 10 * k, y - k * 120 * u), 'Z', (30 + 14 * i) * u, BLUE, 'mm', stroke=2)
def P_bang(c, x, y, u, now): c.text((x, y), '!', 190 * u, ACC, 'mm', stroke=4)
def P_sign(c, x, y, u, now, text=''):
    c.line([(x, y), (x, y - 160 * u)], 9 * u, (140, 98, 60)); lines = wrap(text, 34, 330)[:3] or ['']; hh = 24 + 40 * len(lines)
    c.rr(x - 190, y - 190 * u - hh + 40, x + 190, y - 150 * u + 40, 10, (240, 214, 160), (140, 98, 60), 6)
    for i, ln in enumerate(lines): c.text((x, y - 190 * u - hh + 60 + i * 40), ln, 32, INK, 'ma')
def P_num(c, x, y, u, now, text=''):
    s = 1 + .05 * math.sin(now * 6); t = text[:9]; hw = max(150, 40 * len(t) + 50) * u * s; c.rr(x - hw, y - 70 * u * s, x + hw, y + 70 * u * s, 26, WHITE, ACC, 7); c.text((x, y), t, 92 * u * s, ACC, 'mm')

def P_stack(c, x, y, u, now):
    for i, (w, col) in enumerate(((120, ACC), (100, BLUE), (110, GREEN), (90, GOLD))): c.rr(x - w / 2 * u, y - (i + 1) * 26 * u, x + w / 2 * u, y - i * 26 * u, 3, col, INK, 4)
def P_quill(c, x, y, u, now):
    r = math.sin(now * 2) * 4; c.poly([(x - 60 * u, y + 60 * u), (x + 50 * u, y - 70 * u + r), (x + 70 * u, y - 40 * u + r), (x - 40 * u, y + 70 * u)], (240, 240, 232), INK, 4); c.line([(x - 60 * u, y + 60 * u), (x - 86 * u, y + 92 * u)], 4)
def P_lamp(c, x, y, u, now):
    c.line([(x, y), (x, y - 90 * u)], 8 * u); c.poly([(x - 50 * u, y - 90 * u), (x + 50 * u, y - 90 * u), (x + 24 * u, y - 140 * u), (x - 24 * u, y - 140 * u)], GOLD, INK, 5); c.rr(x - 40 * u, y - 10 * u, x + 40 * u, y, 4, INK, INK, 2)
def P_globe(c, x, y, u, now):
    c.circ(x, y - 70 * u, 60 * u, (110, 170, 220), INK, 5)
    for k in range(3): xx = x + math.sin(now * 1.2 + k * 2.1) * 40 * u; c.ell(xx - 18 * u, y - 100 * u + k * 22 * u, xx + 18 * u, y - 80 * u + k * 22 * u, GREEN, None, 0)
    c.line([(x, y), (x, y - 12 * u)], 8 * u); c.rr(x - 30 * u, y - 12 * u, x + 30 * u, y, 3, (140, 98, 60), INK, 4)

ICON_NAMES = {'brain', 'clock', 'book', 'phone', 'house', 'eye', 'heart', 'moon', 'sun', 'crowd', 'chart', 'face', 'lock', 'scroll', 'question', 'bulb'}
PROPS = {'dog': (P_dog, 'g'), 'cat': (P_cat, 'g'), 'bird': (P_bird, 'f'), 'fish': (P_fish, 'f'), 'tree': (P_tree, 'g'), 'car': (P_car, 'g'), 'ball': (P_ball, 'g'), 'apple': (P_apple, 'f'), 'cup': (P_cup, 'f'),
         'bed': (P_bed, 'g'), 'cloud': (P_cloud, 'f'), 'money': (P_money, 'f'), 'mirror': (P_mirror, 'f'), 'camera': (P_camera, 'f'), 'pyramid': (P_pyramid, 'g'), 'camel': (P_camel, 'g'), 'mountain': (P_mountain, 'g'),
         'flag': (P_flag, 'g'), 'star': (P_star, 'f'), 'laptop': (P_laptop, 'f'), 'door': (P_door, 'g'), 'fire': (P_fire, 'g'), 'battery': (P_battery, 'f'), 'zzz': (P_zzz, 'f'), 'bang': (P_bang, 'f'), 'sign': (P_sign, 'g'), 'num': (P_num, 'f'), 'stack': (P_stack, 'g'), 'quill': (P_quill, 'f'), 'lamp': (P_lamp, 'g'), 'globe': (P_globe, 'g')}
for _n in ICON_NAMES: PROPS[_n] = (None, 'f')
def draw_prop(c, k, x, tc, now, text='', out=1.0):
    """tc = seconds since the prop was first spoken about. It pops in (spring), then idles."""
    pp = pop(tc, 0, .5) * out
    if pp <= 0: return
    fn, kind = PROPS[k]
    if k in ICON_NAMES: icon(c, k, x, 330 + 8 * math.sin(now * 2 + x), 112 * pp, now)
    elif kind == 'g': fn(c, x, GROUND, 1.25 * pp, now) if k not in ('sign', 'num') else fn(c, x, GROUND, 1.0 * pp, now, text)
    else: (fn(c, x, 330 + 7 * math.sin(now * 2 + x), (1.0 if G.get('vert') else 1.6) * pp, now, text) if k == 'num' else fn(c, x, 340 + 7 * math.sin(now * 2 + x), 1.5 * pp, now))

# ---------------- v4: the director (decides what happens on screen for every few words) ----------------
PROP_KW = [('stack', r'books|library|libraries|shelf|shelves|volumes?'), ('quill', r'wrote|writing|writes|letters?|essays?|manuscripts?|pen'), ('lamp', r'candle|lamp|evening|reading|study'), ('globe', r'world|globe|countries|travel\w*|voyage|explor\w*'), ('dog', r'dogs?|puppy|puppies|wolf|wolves'), ('cat', r'cats?|kitten'), ('bird', r'birds?|eagles?|pigeons?|owls?'), ('fish', r'fish|sharks?'), ('tree', r'trees?|leaf|leaves|plants?'), ('car', r'cars?|driving|drives?|driver|traffic'),
    ('ball', r'ball|sports?|games?|playing'), ('apple', r'food|eat|eating|ate|hungry|apples?|meals?|diet|sugar'), ('cup', r'coffee|tea|drink\w*|cups?'), ('bed', r'bed|sleep\w*|nap|insomnia|dream\w*'), ('cloud', r'clouds?|weather|rain|storm'),
    ('money', r'money|rich|poor|pay|paid|price|cost|buy|wealth|profit|salary'), ('mirror', r'mirrors?|reflect\w*|faces?|expressions?|appearance|looks'), ('camera', r'camera|photos?|photograph\w*|film|recorded|footage'),
    ('pyramid', r'pyramids?|egypt\w*|pharaohs?'), ('camel', r'camels?|sahara|nomads?|caravan'), ('mountain', r'mountains?|climb\w*|summit|everest|hik\w+'), ('flag', r'countr\w+|nations?|flag|war|army|government|politic\w*'),
    ('star', r'stars?|famous|celebrit\w*|fame|winner|champion'), ('laptop', r'computers?|laptop|office|emails?|internet|job|jobs|career'), ('door', r'door|doors|enter\w*|exit|opportunit\w*'), ('fire', r'fire|burn\w*|anger|angry|rage'),
    ('battery', r'energy|tired|exhaust\w*|fatigue|drain\w*|burnout|willpower'),
    ('brain', r'brains?|neurons?|mind|minds|mental|psycholog\w*|conscious\w*|subconscious|memory|memories|thought\w*|thinking'), ('clock', r'clock|hours?|minutes?|years?|decades?|centur\w+|time'), ('book', r'books?|wrote|writes|author|essay|chapter|pages?'),
    ('phone', r'phones?|screens?|apps?|scroll\w*|notification\w*|social media|online'), ('house', r'home|house|room|family|kitchen'), ('eye', r'eyes?|saw|watch\w*|notice\w*|stare\w*|gaze|observ\w*'), ('heart', r'love|loved|heart|emotion\w*|feelings?|fear|grief|joy'),
    ('moon', r'moon|night|midnight'), ('sun', r'sun|morning|dawn|sunrise|alarm'), ('crowd', r'people|crowd|others|social|group|society|friends?|everyone|strangers?'), ('chart', r'percent|study|studies|research\w*|data|evidence|experiments?|survey|scientists?'),
    ('lock', r'habits?|stuck|trap\w*|secret|hidden|locked'), ('scroll', r'ancient|history|century|empire|philosopher'), ('bulb', r'idea|insight|realiz\w+|understand\w*|discover\w*|answer|learn\w*'), ('question', r'why|how come|mystery|puzzle|wonder\w*|question')]
BG_KW = [('library', r'librar\w*|shelf|shelves|bookcase|manuscripts?'), ('bookshop', r'bookshop|bookstore|publisher|printed|printing|sold'), ('study', r'study|desk|wrote|writing|letters?|essays?|diary|candle'), ('desert', r'desert|sahara|kalahari|savanna|dunes?|sand|camels?|egypt\w*|africa\w*|tanzania'), ('ocean', r'ocean|sea|beach|waves?|swim\w*|island|water'), ('space', r'space|planets?|universe|galaxy|cosmos|astronaut|stars'), ('mountain', r'mountains?|climb\w*|summit|cliffs?|hik\w+'),
    ('forest', r'forest|woods|jungle|wild|hunt\w*|gatherers?|foraging|foragers?|ancestors?|survival|caves?'), ('history', r'ancient|history|centur\w+|empire|rome|roman|greek|greece|kings?|philosopher\w*|medieval|castle|pharaoh'), ('city', r'cities|city|street|traffic|urban|downtown|commut\w*|strangers?|crowds?'),
    ('bedroom', r'bed|sleep\w*|dream\w*|insomnia|tired|midnight'), ('night', r'night|dark|moon'), ('office', r'office|job|jobs|work|boss|career|meeting|desk|emails?|computer'), ('school', r'school|class\w*|teacher|students?|exam|lab|experiments?|research\w*|scientists?|studies|study'),
    ('stage', r'audience|speech|perform\w*|stage|speaking|applause'), ('home', r'home|house|room|kitchen|family|apartment|couch'), ('park', r'park|walk\w*|garden|grass|picnic|outdoor\w*|dog|dogs'), ('brain', r'brain|neurons?|mind|memory|memories|thought\w*|conscious\w*|psycholog\w*|habits?|emotion\w*')]
ACT_KW = [('run', r'run|running|chas\w+|flee\w*|rush\w*|sprint\w*|escap\w*|hurry'), ('sleep', r'asleep|fall asleep|sleeping|nap|snor\w+|bed'), ('walk', r'walk\w*|travel\w*|journey|wander\w*|march\w*|explor\w*'), ('jump', r'jump\w*|leap\w*|bounce\w*|spike|surge|boost'),
    ('surprised', r'shock\w*|surpris\w*|suddenly|unexpected\w*|startl\w*|wow|incredibl\w*|turns out|sudden|bizarre|strange|weird|astonish\w*'), ('laugh', r'laugh\w*|funny|humou?r\w*|joke\w*|giggl\w*'), ('sad', r'sad\w*|cry\w*|griev\w*|lone\w*|depress\w*|loss|lose|lost|fail\w*|regret\w*|hurt\w*|pain\w*|mourn\w*'),
    ('cheer', r'win|won|success\w*|celebrat\w*|triumph\w*|amazing|best|achiev\w*|victory|happy|joy\w*|great'), ('read', r'read\w*|book|wrote|writes|written|author|essay|chapter|pages?'), ('phone', r'phones?|scroll\w*|app|apps|notification\w*|social media|texting'),
    ('lookup', r'look\w*|watch\w*|see|saw|notice\w*|stare\w*|gaze|observ\w*|eyes?'), ('think', r'think\w*|wonder\w*|imagine|ponder\w*|why|how|maybe|perhaps|mystery|curious|puzzl\w*|decid\w*|choose|choice|question\w*'),
    ('no', r'never|myth|wrong|false|not true|stop|nothing|cannot|avoid|ignore|don.t|can.t'), ('shrug', r'but|however|yet|although|though|unclear|unknown|not sure|depends|maybe'), ('sit', r'sit\w*|rest\w*|relax\w*|calm|wait\w*|quiet|stay\w*'), ('point', r'first|second|third|next|then|here|this|these|that|those|example|called|named')]
AHA = re.compile(r'\b(realiz\w+|insight|idea|discover\w*|aha|understand\w*|figured|solution|answer)\b', re.I)
def _learn():
    try: return json.loads((BASE / ('data/story-learn-%s.json' % ('shelfmade' if SM else 'mindlore'))).read_text())
    except Exception: return {}
LEARN = _learn()
def pref(items, kind):
    """Order choices by what our viewers watched (data/story-learn.json), with 30% exploration so new ideas still get tried."""
    w = (LEARN.get(kind) or {})
    if not w or random.random() < .3: return list(items)
    return sorted(items, key=lambda k: -float(w.get(k, 0)))
ROT_BG = ['library', 'study', 'bookshop', 'city', 'park', 'history', 'home'] if SM else ['home', 'park', 'city', 'brain', 'office', 'night', 'school']
def _words_re(rx): return re.compile(r'^(?:' + rx + r')$', re.I)
PROP_RE = {n: _words_re(r) for n, r in PROP_KW}; PROP_RX = {n: re.compile(r'\b(?:' + r + r')\b', re.I) for n, r in PROP_KW}
BG_RX = [(n, re.compile(r'\b(?:' + r + r')\b', re.I)) for n, r in BG_KW]; ACT_RX = [(n, re.compile(r'\b(?:' + r + r')\b', re.I)) for n, r in ACT_KW]

def split_beats(ws, vert=False):
    out, cur = [], []
    A, Bv, C = (1.5, 2.4, 3.6) if vert else (2.2, 3.4, 5.6)
    for w in ws:
        cur.append(w); dur = w['e'] - cur[0]['s']
        if (re.search(r'[.!?]["”]?$', w['w']) and dur >= A) or (re.search(r'[,;:—–]$', w['w']) and dur >= Bv) or dur >= C: out.append(cur); cur = []
    if cur:
        if out and cur[-1]['e'] - cur[0]['s'] < 1.3: out[-1].extend(cur)
        else: out.append(cur)
    return out
def cue_time(name, ws):
    rx = PROP_RE.get(name)
    if rx:
        for w in ws:
            if rx.match(re.sub(r'[^\w]', '', w['w'])): return max(ws[0]['s'], w['s'] - .12)
    return ws[0]['s'] + .35
def plan_world(script, secs, words, journeys, vert=False):
    beats = []; N = len(secs); cur_bg = 'library' if SM else 'brain'; bg_t = -99.0; last_act = ''; rot = 0; n_empty = 0
    for si, sec in enumerate(secs):
        ws = [w for w in words if w['sec'] == si]
        if not ws: continue
        groups = split_beats(ws, vert); sb = []
        for gi, g in enumerate(groups):
            txt = ' '.join(w['w'] for w in g); low = txt.lower(); start = sec['start'] if gi == 0 else g[0]['s']
            b = {'start': start, 'end': g[-1]['e'] + .4, 'sec': si, 'text': txt, 'ws': g, 'props': [], 'journey': False}
            # backdrop
            hit = next((n for n, rx in BG_RX if rx.search(low) and (n != 'brain' or gi == 0)), None)
            if (si == 0 and gi == 0): hit = 'library' if SM else 'brain'
            if hit and hit != cur_bg and (start - bg_t >= (3.0 if vert else 5.0) or gi == 0): cur_bg = hit; bg_t = start
            elif gi == 0 and not hit:
                rot += 1; pool = pref(ROT_BG, 'bg'); nxt = pool[rot % len(pool)]
                if nxt == cur_bg: rot += 1; nxt = pool[rot % len(pool)]
                cur_bg = nxt; bg_t = start
            b['bg'] = cur_bg
            # props: specific things first, then symbols
            found = []
            for n, rx in PROP_RX.items():
                m = rx.search(low)
                if m: found.append((n in ICON_NAMES, m.start(), n))
            found.sort(); names = [n for _, _, n in found][:(3 if vert else 2)]
            m = re.search(r'\b(\d[\d,\.]*(?:s\b)?\s?(?:%|percent|per cent)?)', txt)
            if m and re.search(r'\d', m.group(1)) and len(m.group(1).strip()) <= 8:
                names = names[:1]; b['num'] = m.group(1).strip(' .,').replace(' percent', '%')
            if si == 0 and gi == 0: names = ['question'] + [n for n in names if n not in ICON_NAMES][:1]
            if not names and n_empty % 3 == 2 and not vert: names = [['bulb', 'eye', 'brain', 'clock'][(si + gi) % 4]]
            n_empty = n_empty + 1 if not names else 0
            b['props'] = [{'k': n, 'cue': cue_time(n, g)} for n in names]
            if b.get('num'): b['props'].append({'k': 'num', 'cue': g[0]['s'] + .6, 'text': b['num']})
            # action
            act = next((n for n, rx in ACT_RX if rx.search(low)), None)
            if txt.rstrip().endswith('?') and act not in ('run', 'surprised', 'sad'): act = 'think'
            if si == 0 and gi == 0: act = 'think'
            if act == 'point' and not b['props']: act = None
            if act and act == last_act and act not in ('walk', 'run'): act = None
            if not act: act = ['explain', pref(['idle', 'shrug', 'lookup', 'think'], 'act')[0], 'explain', 'point' if b['props'] else pref(['shrug', 'lookup', 'no'], 'act')[0], 'explain'][len(beats) % 5]
            if si == N - 1 and gi == len(groups) - 1 and not vert: act = 'wave'
            b['act'] = act; last_act = act
            b['cue'] = (b['props'][0]['cue'] if b['props'] else g[0]['s'] + .5)
            b['aha'] = bool(AHA.search(txt)); sb.append(b)
        beats.extend(sb)
    if len(beats) > 1:
        for i in range(len(beats) - 1):
            if beats[i]['sec'] == beats[i + 1]['sec']: beats[i]['end'] = beats[i + 1]['start']
    # journeys between sections: the narrator walks through to the next scene while the music plays
    allb = list(beats)
    for j in journeys:
        nxt = next((b for b in beats if b['sec'] == j['sec']), None); prev = [b for b in beats if b['sec'] == j['sec'] - 1]
        if prev: prev[-1]['end'] = j['start']
        allb.append({'start': j['start'], 'end': j['end'], 'sec': j['sec'], 'text': '', 'ws': [], 'bg': nxt['bg'] if nxt else cur_bg, 'act': 'walk', 'journey': True, 'cue': j['start'], 'aha': False,
                     'props': [{'k': 'sign', 'cue': j['start'] + .3, 'text': secs[j['sec']].get('title', '')[:60]}]})
    allb.sort(key=lambda b: b['start'])
    return allb
def llm_direct(script, beats):
    """Optional: the free LLM re-directs scene / action / props per beat (never the narration). Validated; anything odd keeps the heuristic plan."""
    try:
        import llm
        if not llm.available(): return
        props_ok = sorted(PROPS); bgs = sorted(BGS)
        items = [{'i': i, 'text': b['text'][:220], 'bg': b['bg'], 'act': b['act'], 'props': [p['k'] for p in b['props']]} for i, b in enumerate(beats) if not b['journey']]
        for k in range(0, len(items), 36):
            chunk = items[k:k + 36]
            prompt = ('You direct a 2D stick-figure explainer. For each narration beat choose a SCENE (bg), an ACTION for the stick man, and 0-2 PROPS that literally illustrate what is said (a dog if dogs are mentioned, a desert if the Sahara is). '
                      'Make it creative and varied; avoid repeating the same action twice in a row; actions must match the meaning. Allowed bg: %s. Allowed act: %s. Allowed props: %s (never use sign or num). '
                      'Return JSON {"beats":[{"i":N,"bg":"..","act":"..","props":["..",".."]}]} for exactly these beats.\n%s' % (', '.join(bgs), ', '.join(ACTS), ', '.join(p for p in props_ok if p not in ('sign', 'num')), json.dumps(chunk)))
            r = llm.json_call('You are a visual director. Reply with JSON only.', prompt)
            for o in (r.get('beats') or []):
                i = o.get('i')
                if not isinstance(i, int) or not (0 <= i < len(beats)) or beats[i]['journey']: continue
                b = beats[i]
                ac = o.get('act')
                if ac in ACTS and (ac not in ('sit', 'sleep') or re.search(r'sleep|bed|rest|nap|calm|quiet|dream|tired', b['text'], re.I)): b['act'] = ac
                if o.get('bg') in BGS: b['bg'] = o['bg']
                ps = [p for p in (o.get('props') or []) if p in PROPS and p not in ('sign', 'num')][:2]
                if ps and not b.get('num'): b['props'] = [{'k': p, 'cue': cue_time(p, b['ws'])} for p in ps]
        # a scene must not flicker: keep at least 4.5 s between backdrop changes inside a section
        last = None; lt = -99; prev_sec = -1
        for b in beats:
            if b['journey']: continue
            if last and b['bg'] != last and b['start'] - lt < 4.5 and b['sec'] == prev_sec: b['bg'] = last
            if b['bg'] != last: last = b['bg']; lt = b['start']
            prev_sec = b['sec']
    except Exception as e:
        print('ml2d: llm director skipped:', str(e)[:100], flush=True)
def layout(beats, vert=False):
    """Walks the narrator across the stage, picks facing, places props on the open side, computes where to point."""
    x = 300.0; d = 1; still = 0; ph = 0.0
    for i, b in enumerate(beats):
        L = max(.5, b['end'] - b['start']); act = b['act']
        if b['journey']: act = 'walk'
        elif act in ('idle', 'explain', 'point', 'shrug') and still >= 3 and L >= 2.8 and not vert: act = 'walk'
        if act == 'point' and not b['props']: act = 'explain'
        b['act'] = act; b['x0'] = x; b['ph0'] = ph
        if act in ('walk', 'run'):
            v = 170.0 if act == 'walk' else 330.0; lo_x, hi_x = (330.0, 950.0) if vert else (270.0, 1010.0); target = hi_x if x < 640 else lo_x; dist = abs(target - x)
            if dist < 120: target = lo_x if target > 640 else hi_x; dist = abs(target - x)
            dd = 1 if target > x else -1; trav = min(dist, v * L * .92); b['x1'] = x + dd * trav; b['arrive'] = trav / v; b['v'] = v; d = dd; still = 0
        else: b['x1'] = x; b['arrive'] = 0; b['v'] = 0; still += 1
        x = b['x1']; side_right = x <= 640
        slots = ([x + 340, x + 500, x + 190] if side_right else [x - 340, x - 500, x - 190]) if vert else ([890, 1060, 760] if side_right else [390, 220, 520])
        for k, p in enumerate(b['props']): p['x'] = slots[k % 3] if p['k'] != 'sign' else (b['x1'] + (260 if side_right else -260))
        if act not in ('walk', 'run') and b['props']: d = 1 if b['props'][0]['x'] > x else -1
        if act == 'sleep':
            for p in b['props']:
                if p['k'] == 'bed': p['x'] = x + 40; d = 1
        b['d'] = d
        pxs = [p['x'] for p in b['props']] or [x + (200 if d > 0 else -200)]; b['cam1'] = max(418.0, min(862.0, (x + sum(pxs) / len(pxs)) / 2)); b['cam0'] = beats[i - 1]['cam1'] if i else b['cam1']
        if b['props']:
            p = b['props'][0]; vx = (p['x'] - x) * d; vy = (480 if PROPS[p['k']][1] == 'g' else 340) - 393
            b['aim'] = max(20.0, min(170.0, math.degrees(math.atan2(vx, vy))))
        else: b['aim'] = 100.0
    return beats

# ---------------- audio / timing (v4: journeys between chapters, tempo so the video lands at 8-10 minutes) ----------------
TR = 3.2
def make_voice(script, work):
    jobs = []
    for i, s in enumerate(script['sections']): jobs.append({'text': s['narration'], 'wav': str(work / ('sec%02d.wav' % i)), 'timing': str(work / ('sec%02d.json' % i))})
    if os.environ.get('ML2D_FAKE'):
        for j in jobs:
            n = len(j['text'].split()); dur = n / 2.7
            with wave.open(j['wav'], 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\x00\x00' * int(24000 * dur))
            toks = [{'text': t, 'start': k / 2.7, 'end': (k + 1) / 2.7} for k, t in enumerate(j['text'].split())]
            Path(j['timing']).write_text(json.dumps({'tokens': toks, 'duration': dur}))
    else:
        sys.path.insert(0, str(BASE)); os.environ.setdefault('CE_VOICE_ENGINE', 'edge')
        import local_voice
        local_voice.edge_run(jobs)
    return jobs
def assemble(script, jobs, work, journey=True):
    """Narration timeline: sections separated by a short walking-journey gap. Returns (secs, words, total, narration_path, journeys)."""
    t = 0.0; secs = []; words = []; frames = []; journeys = []; rate = 24000
    for si, j in enumerate(jobs):
        tm = json.loads(Path(j['timing']).read_text()); toks = tm.get('tokens') or []; dur = tm['duration']
        with wave.open(j['wav']) as w: frames.append(w.readframes(w.getnframes())); rate = w.getframerate()
        text = script['sections'][si]['narration']; allw = text.split(); ratio = (len(toks) / max(1, len(allw))) if toks else 0
        for q, wd in enumerate(allw):
            if toks:
                a = toks[min(len(toks) - 1, int(q * ratio))]; b2 = toks[min(len(toks) - 1, max(int(q * ratio), int((q + 1) * ratio) - 1))]; s0, e0 = a['start'], b2['end']
            else: s0, e0 = (q / max(1, len(allw))) * dur, ((q + 1) / max(1, len(allw))) * dur
            words.append({'w': wd, 's': t + s0, 'e': t + max(e0, s0 + .08), 'sec': si})
        secs.append({'title': script['sections'][si].get('title', ''), 'start': t, 'end': t + dur})
        gap = TR if (journey and si < len(jobs) - 1) else .45
        if journey and si < len(jobs) - 1: journeys.append({'start': t + dur, 'end': t + dur + gap, 'sec': si + 1})
        t += dur + gap; frames.append(b'\x00\x00' * int(rate * gap))
    out = work / 'narration.wav'
    with wave.open(str(out), 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(b''.join(frames))
    return secs, words, t + 1.0, out, journeys
def retime(secs, words, journeys, total, f):
    """Scale every time by f (tempo change of the narration)."""
    for s in secs: s['start'] *= f; s['end'] *= f
    for w in words: w['s'] *= f; w['e'] *= f
    for j in journeys: j['start'] *= f; j['end'] *= f
    return total * f

def caption_chunks(words):
    chunks = []; cur = []
    for wd in words:
        cur.append(wd)
        if len(cur) >= 7 or re.search(r'[.!?]$', wd['w']) or (len(cur) >= 5 and re.search(r'[,;:]$', wd['w'])): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return chunks

# ---------------- frames ----------------
G = {}
def draw_frame(fi):
    now = fi / FPS; beats = G['beats']; i = max(0, bisect.bisect_right(G['bstarts'], now) - 1); b = beats[i]; lt = now - b['start']; L = max(.5, b['end'] - b['start'])
    c = Cv(G['bgimg'][b['bg']]); bg_anim(c, b['bg'], now)
    # who is speaking right now
    wi = bisect.bisect_right(G['wstarts'], now) - 1; talk = False; mouth = 0.0; pulse = 0.0
    if wi >= 0:
        w = G['words'][wi]
        if now <= w['e'] + .04: talk = True; mouth = abs(math.sin((now - w['s']) * 24 + wi))
        pulse = math.exp(-(now - w['s']) * 8)
    # position and pose
    act = b['act']; move = act in ('walk', 'run'); ph = 0.0
    if move:
        trav = min(abs(b['x1'] - b['x0']), b['v'] * lt); x = b['x0'] + (1 if b['x1'] >= b['x0'] else -1) * trav; ph = b['ph0'] + trav / (26.0 if act == 'walk' else 40.0)
        if lt > b['arrive'] + .1 and not b['journey']: act = 'explain'
    else: x = b['x0']
    a = acts(act, lt, now - b['cue'], ph, b['aim'])
    if lt < .3 and i > 0:
        pb = beats[i - 1]; pl = pb['end'] - pb['start']; pa = acts(pb['act'] if pb['act'] not in ('walk', 'run') else 'explain', pl, 1.0, 0.0, pb['aim']); a = mix_a(pa, a, ease(lt / .3))
    if not move and act not in ('sleep',): a['dy'] += 3 * pulse; a['tilt'] += 3 * pulse
    # ground props behind the narrator, float props in front
    out = clamp((b['end'] - now) / .18)
    for p in b['props']:
        if PROPS[p['k']][1] == 'g': draw_prop(c, p['k'], p['x'], (now - p['cue']) , now, p.get('text', ''), out)
    gy = GROUND - 80 if (act == 'sleep' and any(p['k'] == 'bed' for p in b['props'])) else GROUND
    pts = rig(c, x, gy, 1.32, a, now, talk, b['d'], mouth, (now % 3.6) < .12)
    for p in b['props']:
        if PROPS[p['k']][1] != 'g': draw_prop(c, p['k'], p['x'], (now - p['cue']), now, p.get('text', ''), out)
    if act == 'read': icon(c, 'book', pts['hand_r'][0] + 34 * b['d'], pts['hand_r'][1] - 18, 46, now)
    if act == 'phone': icon(c, 'phone', pts['hand_r'][0] + 22 * b['d'], pts['hand_r'][1] - 6, 36, now)
    hx, hy = pts['head']
    if act == 'think' and not b['props'] or (act == 'think' and (b['props'][0]['k'] != 'question')): c.text((hx + 56 * b['d'], hy - 4 + 5 * math.sin(now * 3)), '?', 70, ACC, 'mm', stroke=3)
    if act == 'surprised' and now > b['cue']: c.text((hx + 56 * b['d'], hy - 4), '!', 90 * pop(now - b['cue'], 0, .3), ACC, 'mm', stroke=3)
    if act == 'sleep': P_zzz(c, pts['sh'][0] + 40, pts['sh'][1] - 70, 1.0, now)
    if act in ('cheer', 'dance', 'jump', 'laugh'):
        for k in range(3): ang = now * 3 + k * 2.1; c.text((hx + math.cos(ang) * 78, hy + 20 + math.sin(ang) * 30), '*', 54, GOLD, 'mm', stroke=2)
    if b.get('aha') and now > b['cue']: icon(c, 'bulb', hx + 70 * b['d'], hy - 10, 38 * pop(now - b['cue'], 0, .35), now)
    if act == 'run': 
        for k in range(3): c.line([(x - b['d'] * (70 + k * 22), 400 + k * 55), (x - b['d'] * (130 + k * 22), 400 + k * 55)], 4, (150, 150, 160))
    if G.get('vert'):
        if move: cx = max(418.0, min(862.0, x + 100 * b['d'])); cx = lerp(b['cam0'], cx, ease(lt / .5))
        else: cx = lerp(b['cam0'], b['cam1'], ease(lt / .5))
        zk = 0.0
        if b['props']: zk = math.exp(-max(0.0, now - b['cue']) * 5.0) if now >= b['cue'] else 0.0
        return vframe(c.out(), now, (cx, 1.0 + .12 * zk))
    sec = G['secs'][min(b['sec'], len(G['secs']) - 1)]; chip = '%d  %s' % (b['sec'] + 1, sec['title'][:34])
    cw = tw(chip, 26) + 36; c.rr(24, 22, 24 + cw, 68, 16, INK, INK, 2); c.text((42, 33), chip, 26, WHITE)
    c.text((W - 26, 30), BRAND_NAME, 28, BLUE, 'ra')
    ci = max(0, bisect.bisect_right(G['cstarts'], now) - 1); ch = G['chunks'][ci]
    if now >= ch[0]['s'] - .05 and now <= ch[-1]['e'] + .6:
        txt = ' '.join(x['w'] for x in ch); size = 38; wd = tw(txt, size) + 50
        if wd > 1180: size = 32; wd = tw(txt, size) + 50
        x0 = (W - wd) / 2; c.rr(x0, 618, x0 + wd, 684, 20, INK, INK, 2); xx = x0 + 25
        for wrd in ch:
            on = wrd['s'] <= now; c.text((xx, 626), wrd['w'], size, GOLD if (on and now <= wrd['e'] + .12) else (WHITE if on else (175, 175, 185))); xx += tw(wrd['w'] + ' ', size)
    c.rr(0, H - 5, W * clamp(now / G['total']), H, 0, ACC, None, 0)
    return c.out().tobytes()
def split_sentences(text): return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z“"\'])', text.strip()) if s.strip()]
def f1(px): return font(px / K)
def vframe(img, now, cam=(640, 1.0)):
    """9:16 Short layout: title on top, the 16:9 scene in the middle, big captions below, call to action at the bottom."""
    V = Image.new('RGB', (1080, 1920), PAPER); d = ImageDraw.Draw(V)
    cx, zm = cam; cw, ch_ = 836 / zm, 720 / zm; x0 = max(0, min(W - cw, cx - cw / 2)); y0 = max(0, min(H - ch_, 380 - ch_ / 2))
    V.paste(img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch_))).resize((1080, 930), Image.LANCZOS), (0, 400))   # camera follows the action, punches in on key words
    d.rounded_rectangle([60, 70, 330, 130], radius=16, fill=BLUE, outline=INK, width=4); d.text((195, 100), BRAND_NAME, font=f1(36), fill=WHITE, anchor='mm')
    y = 160
    for ln in wrap(G['vtitle'], 60 / 1.0, 940)[:3]: d.text((540, y), ln, font=f1(60), fill=INK, anchor='ma'); y += 72
    ci = max(0, bisect.bisect_right(G['cstarts'], now) - 1); ch = G['chunks'][ci]
    if now <= ch[-1]['e'] + .6:
        size = 70; lines = []; cur = []
        for w in ch:
            t = ' '.join(x['w'] for x in cur + [w])
            if cur and f1(size).getlength(t) > 900: lines.append(cur); cur = [w]
            else: cur.append(w)
        if cur: lines.append(cur)
        top = 1360; hh = len(lines) * 96 + 40
        d.rounded_rectangle([60, top, 1020, top + hh], radius=30, fill=INK)
        for li, ln in enumerate(lines):
            txt = ' '.join(x['w'] for x in ln); x = 540 - f1(size).getlength(txt) / 2
            for w in ln:
                on = w['s'] <= now; col = GOLD if (on and now <= w['e'] + .12) else (WHITE if on else (175, 175, 185))
                if on and re.search(r'\d', w['w']): col = (255, 120, 90)
                d.text((x, top + 24 + li * 96), w['w'], font=f1(size), fill=col); x += f1(size).getlength(w['w'] + ' ')
    d.text((540, 1830), ('Classic books, explained on ShelfMade' if SM else 'Full video on the MindLore channel'), font=f1(42), fill=BLUE, anchor='mm')
    d.rectangle([0, 1912, int(1080 * clamp(now / G['total'])), 1920], fill=ACC)
    return V.tobytes()
def short_script(script):
    """First ~100-125 words of section 1 (whole sentences) plus a call to action, as a one-section script."""
    if script.get('story_short'): return script   # story Shorts are complete as written (they loop back to their own opening line)
    sents = split_sentences(script['sections'][0]['narration']); out = []; n = 0
    for st in sents:
        out.append(st); n += len(st.split())
        if n >= 100: break
    sc = json.loads(json.dumps(script)); sc['sections'] = [{'title': script['sections'][0].get('title', ''), 'narration': ' '.join(out) + ' Watch the full video on MindLore.'}]
    return sc

def thumbnail(script, path):
    c = Cv()
    for x in range(0, W, 64):
        for y in range(0, H, 64): c.circ(x + 32, y + 32, 1.8, SOFT, None, 0)
    c.rr(0, 0, 36, H, 0, ACC, None, 0)
    head = (script.get('thumbnail_headline') or script.get('public_title', '').split('|')[0]).upper(); size = 110
    lines = wrap(head, size, 700)
    while len(lines) > 3 and size > 70: size -= 8; lines = wrap(head, size, 700)
    y = 150
    for i, ln in enumerate(lines[:3]): c.text((80, y + i * size * 1.08), ln, size, ACC if i == len(lines[:3]) - 1 else INK, 'la', stroke=3)
    figure(c, 1010, 650, 1.35, 'shrug', 0.4, False); icon(c, 'question', 1150, 150, 100, 0)
    c.rr(80, 62, 330, 112, 14, BLUE, INK, 4); c.text((205, 87), 'MindLore', 32, WHITE, 'mm')
    c.out().save(path, quality=92)

def _live_full_on():
    try: return bool(json.loads((BASE / 'publish' / 'guard.json').read_text()).get('mindlore_live_full', True))
    except Exception: return True
def build(sid, out, vert=False):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); work = out / '.work'; work.mkdir(exist_ok=True)
    p = Path(sid) if str(sid).endswith('.json') else BASE / 'cinematic-scripts-mindlore' / (str(sid) + '.json')
    script = json.loads(p.read_text())
    if vert: script = short_script(script)
    jobs = make_voice(script, work); secs, words, total, narr, journeys = assemble(script, jobs, work, journey=not vert)
    tempo = 1.0
    if not vert and not os.environ.get('ML2D_NOTEMPO'):   # land between 8 and 10 minutes: slow the narration a little when the script is short
        if total < 500: tempo = max(.88, total / 515.)
        elif total > 590: tempo = min(1.06, total / 585.)
        if abs(tempo - 1) > .005:
            nt = work / 'narration_t.wav'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(narr), '-filter:a', 'atempo=%.4f' % tempo, str(nt)], check=True); narr = nt
            total = retime(secs, words, journeys, total, 1.0 / tempo)
    print('ml2d: runtime %.0fs (%.1f min), tempo %.2f' % (total, total / 60, tempo), flush=True)
    if os.environ.get('ML2D_MAXSEC'): total = min(total, float(os.environ['ML2D_MAXSEC']))   # tests only
    beats = plan_world(script, secs, words, journeys, vert); llm_direct(script, beats); beats = layout(beats, vert); beats[0]['start'] = 0.0
    bgimg = {}
    for n in {b['bg'] for b in beats}: cv = Cv(); BGS[n](cv); bgimg[n] = cv.im
    G.update(vert=vert, vtitle=(script.get('hook') or script.get('public_title', '')), beats=beats, bstarts=[b['start'] for b in beats], secs=secs, total=total, words=words, wstarts=[w['s'] for w in words], bgimg=bgimg)
    chunks = caption_chunks(words); G['chunks'] = chunks; G['cstarts'] = [ch[0]['s'] for ch in chunks]
    # music bed
    mix = work / 'mix.m4a'; bed = None
    try:
        sys.path.insert(0, str(BASE)); import music_director
        info = music_director.make_bed('shelfmade' if SM else 'mindlore', 'full', json.dumps(script)[:6000], total, work / 'bed.wav', words=len(words), sections=[str(_s.get('narration', '')) for _s in script.get('sections', [])], key=str(script.get('book_id', '')) + '|' + str(script.get('public_title', '')))
        bed = info['path'] if info else None
    except Exception as e: print('ml2d: music skipped:', str(e)[:100], flush=True)
    if bed:
        fc = '[0:a]loudnorm=I=-17:TP=-2:LRA=9,asplit=2[v][sc];[1:a]volume=0.55[m];[m][sc]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=500[d];[v][d]amix=inputs=2:duration=first:normalize=0[a]'
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(narr), '-i', bed, '-filter_complex', fc, '-map', '[a]', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', str(mix)]
    else: cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(narr), '-af', 'loudnorm=I=-16:TP=-2:LRA=9', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', str(mix)]
    subprocess.run(cmd, check=True)
    nf = int(total * FPS); final = out / ('ml2d_SHORT.mp4' if vert else 'ml2d_LONGFORM.mp4')
    live_done = False
    if not vert and not SM and not os.environ.get('ML2D_OLD') and _live_full_on():
        try:   # owner decision 2026-11-09: full MindLore videos use the same LIVE DEMO look as the Shorts (landscape layout); old look is the fallback
            import live_demo
            lw = []
            for w in words:
                c_ = re.sub(r'[^\x20-\x7e]', '', str(w['w']).replace('\u2019', "'").replace('\u2018', "'")) or '.'
                lw.append({'w': c_, 's': w['s'], 'e': w['e']})
            live_demo.render(lw, total, str(mix), final, ' '.join(x['w'] for x in lw), script.get('public_title') or script.get('title', ''), land=True, long=True)
            live_done = True; print('ml2d: LIVE look done', flush=True)
        except BaseException as e: print('ml2d: live look failed, falling back to old look:', str(e)[:300], flush=True)
    if not live_done:
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % ((1080, 1920) if vert else (W, H)), '-r', str(FPS), '-i', '-', '-i', str(mix), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-t', '%.2f' % total, '-movflags', '+faststart', str(final)], stdin=subprocess.PIPE)
        import multiprocessing as mp
        with mp.get_context('fork').Pool(max(1, os.cpu_count() or 2)) as pool:
            for k, b in enumerate(pool.imap(draw_frame, range(nf), chunksize=24)):
                enc.stdin.write(b)
                if k % 600 == 0: print('ml2d: frame %d/%d' % (k, nf), flush=True)
        enc.stdin.close()
        if enc.wait(): raise RuntimeError('video encode failed')
    if not vert: thumbnail(script, out / 'THUMBNAIL.jpg')
    chapters = '\n'.join('%d:%02d %s' % (int(s['start']) // 60, int(s['start']) % 60, s['title']) for s in secs)
    desc = (script.get('hook', '') + '\n\nMindLore explains psychology from the original texts. Original commentary inspired by %s by %s. Modern examples are our interpretations, not author quotations.\n\nChapters:\n%s' % (script.get('title', ''), script.get('author', ''), chapters))
    try:
        sys.path.insert(0, str(BASE)); import ml_series
        desc += ml_series.footer({'public_title': script.get('public_title'), 'book_title': script.get('title'), 'author': script.get('author'), 'source_url': script.get('source_url')})
    except Exception:
        desc += '\n\nSource: ' + str(script.get('source_url', ''))
    try:
        import story_rules; ev = story_rules.evidence_lines(script)
        if ev: desc += '\n\nEvidence mentioned in this video:\n- ' + '\n- '.join(ev)
    except Exception: pass
    try:
        import hashtags; desc += '\n\n' + hashtags.mindlore(script.get('hook', '') + ' ' + script.get('title', ''), 'full')
    except Exception: desc += '\n\n#psychology #MindLore'
    (out / 'POST_THIS.txt').write_text('--- TITLE ---\n' + script.get('public_title', script.get('title', '')) + '\n\n--- DESCRIPTION ---\n' + desc[:4900])
    (out / 'ml2d-plan.json').write_text(json.dumps({'beats': [{k: v for k, v in b.items() if k != 'ws'} for b in beats], 'total': total, 'tempo': tempo, 'style': 'live-demo' if live_done else 'ml2d-v4'}, indent=1))
    print('ml2d: done', final, '%.0fs' % total, flush=True)
    return final

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == 'short')
