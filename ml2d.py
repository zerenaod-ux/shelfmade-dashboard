"""MindLore 2D EXPLAINER engine: turns a checked MindLore script (cinematic-scripts-mindlore/*.json) into a faceless 2D animated explainer video.
Style: warm paper background, hand-drawn stick narrator, icons, THEN-vs-NOW panels, quote cards, big stats, word-by-word captions.
Everything is drawn in code (PIL) and encoded with ffmpeg: free, fully automatic, no stock footage, no AI image service.
  python ml2d.py <script id or path> <out folder>          (ML2D_FAKE=1 uses silent timing for tests)
Output folder: ml2d_LONGFORM.mp4, THUMBNAIL.jpg, POST_THIS.txt (same shape the review step already reads)."""
import os, sys, json, re, math, random, subprocess, wave, bisect, datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
BASE = Path(__file__).resolve().parent
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
    def __init__(s): s.im = Image.new('RGB', (W * K, H * K), PAPER); s.d = ImageDraw.Draw(s.im)
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

# ---------------- the narrator ----------------
def figure(c, x, y, s, pose, now, talking=True):
    col = INK; sw = 8 * s; b = wob(0, now, 2.0) * s
    hx, hy = x, y - 262 * s + b; sh_y = y - 205 * s + b; hip = (x, y - 105 * s + b)
    c.line([(x, sh_y), hip], sw, col); c.line([hip, (x - 38 * s, y)], sw, col); c.line([hip, (x + 38 * s, y)], sw, col)
    sway = math.sin(now * 3) * 10 * s
    if pose == 'point': arms = [[(x, sh_y + 12 * s), (x - 52 * s, y - 120 * s), (x - 70 * s, y - 80 * s + sway)], [(x, sh_y + 12 * s), (x + 70 * s, y - 215 * s), (x + 135 * s, y - 250 * s + sway)]]
    elif pose == 'think': arms = [[(x, sh_y + 12 * s), (x - 52 * s, y - 120 * s), (x - 60 * s, y - 70 * s)], [(x, sh_y + 12 * s), (x + 55 * s, y - 150 * s), (x + 20 * s, y - 232 * s)]]
    elif pose == 'shrug': arms = [[(x, sh_y + 12 * s), (x - 60 * s, y - 150 * s), (x - 80 * s, y - 190 * s + sway)], [(x, sh_y + 12 * s), (x + 60 * s, y - 150 * s), (x + 80 * s, y - 190 * s - sway)]]
    elif pose == 'cheer': arms = [[(x, sh_y + 12 * s), (x - 60 * s, y - 250 * s), (x - 80 * s, y - 330 * s + sway)], [(x, sh_y + 12 * s), (x + 60 * s, y - 250 * s), (x + 80 * s, y - 330 * s - sway)]]
    else: arms = [[(x, sh_y + 12 * s), (x - 55 * s, y - 130 * s), (x - 62 * s, y - 85 * s + sway)], [(x, sh_y + 12 * s), (x + 55 * s, y - 130 * s), (x + 62 * s, y - 85 * s - sway)]]
    for a in arms: c.line(a, sw, col)
    c.circ(hx, hy, 46 * s, WHITE, col, sw)
    c.arc(hx - 22 * s, hy - 62 * s, hx + 22 * s, hy - 36 * s, 200, 340, sw * .8)   # tuft of hair
    for dx in (-18, 18): c.circ(hx + dx * s, hy - 6 * s, 15 * s, None, col, 4 * s)   # glasses
    c.line([(hx - 3 * s, hy - 6 * s), (hx + 3 * s, hy - 6 * s)], 3 * s)
    for dx in (-18, 18): c.circ(hx + dx * s, hy - 6 * s, 4 * s, col, None, 0)
    if talking and int(now * 7) % 2 == 0: c.ell(hx - 11 * s, hy + 16 * s, hx + 11 * s, hy + 34 * s, col, col, 2)
    else: c.line([(hx - 12 * s, hy + 24 * s), (hx + 12 * s, hy + 22 * s)], 4 * s)

# ---------------- scenes ----------------
def typed(t, lt, t0, cps=34): return t[:max(0, int((lt - t0) * cps))]
def center_lines(c, lines, cx, y, size, col=INK, lh=1.2, **kw):
    for i, ln in enumerate(lines): c.text((cx, y + i * size * lh), ln, size, col, 'ma', **kw)
def underline(c, x0, x1, y, lt, t0, col=ACC):
    g = ease((lt - t0) / .5)
    if g > 0: c.line([(x0, y), (x0 + (x1 - x0) * g, y + 3 * math.sin(g * 6))], 8, col)

def scene_figure(c, sp, lt, dur, now):
    figure(c, 290, 585, 1.0, sp.get('pose', 'idle'), now)
    icon(c, sp.get('icon', 'bulb'), 880, 270, 130 * pop(lt, .15), now)
    lines = wrap(sp.get('text', ''), 50, 560)[:3]; shown = typed(sp.get('text', ''), lt, .5, 30)
    y0 = 430
    k = 0
    for i, ln in enumerate(lines):
        part = shown[k:k + len(ln) + 1]; k += len(ln) + 1
        c.text((880, y0 + i * 60), part.strip(), 50, INK, 'ma', stroke=2)
    if lines: underline(c, 880 - min(tw(max(lines, key=len), 50), 560) / 2, 880 + min(tw(max(lines, key=len), 50), 560) / 2, y0 + len(lines) * 60 + 6, lt, 1.2)
def scene_big(c, sp, lt, dur, now):
    icon(c, sp.get('icon', 'bulb'), 640, 185, 105 * pop(lt, .1), now)
    lines = wrap(sp.get('text', ''), 70, 1080)[:3]; k = 0; shown = typed(sp.get('text', ''), lt, .45, 34)
    for i, ln in enumerate(lines):
        part = shown[k:k + len(ln) + 1]; k += len(ln) + 1; c.text((640, 330 + i * 84), part.strip(), 70, INK, 'ma', stroke=2)
    if lines: underline(c, 640 - min(tw(max(lines, key=len), 70), 1080) / 2, 640 + min(tw(max(lines, key=len), 70), 1080) / 2, 330 + len(lines) * 84 + 4, lt, 1.3)
def scene_versus(c, sp, lt, dur, now):
    for side, (x0, x1, head, col, ic, lab, t0) in enumerate(((70, 610, 'THEN', BLUE, sp.get('left_icon', 'scroll'), sp.get('left', ''), .15), (670, 1210, 'NOW', ACC, sp.get('right_icon', 'phone'), sp.get('right', ''), max(.9, dur * .38)))):
        p = pop(lt, t0)
        if p <= 0: continue
        m = (x0 + x1) / 2; yo = (1 - clamp(p)) * 40
        c.rr(x0, 110 + yo, x1, 560 + yo, 26, WHITE, INK, 6); c.rr(m - 90, 90 + yo, m + 90, 150 + yo, 18, col, INK, 5); c.text((m, 120 + yo), head, 38, WHITE, 'mm')
        icon(c, ic, m, 280 + yo, 100 * p, now)
        center_lines(c, wrap(lab, 40, 480)[:3], m, 400 + yo, 40, INK)
    if pop(lt, .6) > 0: c.circ(640, 335, 36 * pop(lt, .6), INK, INK, 3); c.text((640, 335), 'vs', 34 * clamp(pop(lt, .6)), WHITE, 'mm')
def scene_quote(c, sp, lt, dur, now):
    p = pop(lt, .05, .5); yo = (1 - clamp(p)) * 50
    c.rr(130, 100 + yo, 1150, 520 + yo, 28, WHITE, INK, 7); c.text((175, 85 + yo), '“', 150, ACC, 'la', stroke=0)
    t = sp.get('text', ''); lines = wrap(t, 38, 880, False, True)[:7]; shown = typed(t, lt, .4, 40); k = 0
    for i, ln in enumerate(lines):
        part = shown[k:k + len(ln) + 1]; k += len(ln) + 1; c.text((200, 190 + yo + i * 46), part.strip(), 38, INK, 'la', False, True)
    if lt > dur * .6: c.text((1100, 478 + yo), '— ' + sp.get('who', ''), 30, BLUE, 'ra')
def scene_stat(c, sp, lt, dur, now):
    p = pop(lt, .1, .6); sz = 210 * max(.05, p)
    for i in range(10): a = i * math.pi / 5 + .3; r0 = 250 + 8 * math.sin(now * 5 + i); c.line([(640 + math.cos(a) * r0, 300 + math.sin(a) * r0 * .55), (640 + math.cos(a) * (r0 + 40), 300 + math.sin(a) * (r0 + 40) * .55)], 7, GOLD)
    c.text((640, 300), sp.get('big', ''), min(sz, 230), ACC, 'mm', stroke=3)
    center_lines(c, wrap(sp.get('text', ''), 50, 1000)[:2], 640, 445, 50, INK) if lt > .6 else None
def scene_question(c, sp, lt, dur, now):
    figure(c, 1010, 600, .62, 'think', now); c.text((1070, 150 + 8 * math.sin(now * 4)), '?', 120, ACC, 'mm', stroke=3)
    lines = wrap(sp.get('text', ''), 66, 860)[:4]; shown = typed(sp.get('text', ''), lt, .3, 32); k = 0
    for i, ln in enumerate(lines):
        part = shown[k:k + len(ln) + 1]; k += len(ln) + 1; c.text((90, 140 + i * 80), part.strip(), 66, INK, 'la', stroke=2)
def scene_take(c, sp, lt, dur, now):
    figure(c, 250, 585, .95, 'cheer', now); icon(c, 'bulb', 870, 230, 120 * pop(lt, .1), now)
    center_lines(c, wrap(sp.get('text', ''), 54, 600)[:3], 870, 380, 54, INK, stroke=2)
SCENES = {'figure': scene_figure, 'big': scene_big, 'versus': scene_versus, 'quote': scene_quote, 'stat': scene_stat, 'question': scene_question, 'takeaway': scene_take}

# ---------------- planning ----------------
ICONS = [('brain', r'\b(brain|mind|think\w*|thought\w*|psycholog\w*|mental|conscious\w*)\b'), ('moon', r'\b(sleep\w*|dream\w*|night|tired)\b'), ('sun', r'\b(morning|wake\w*|alarm|dawn)\b'),
         ('heart', r'\b(love|feel\w*|emotion\w*|fear|anger|joy|heart|grief|sad)\b'), ('face', r'\b(face|smile\w*|expression\w*|laugh\w*|cry\w*)\b'), ('crowd', r'\b(people|crowd|others|social|group|society|friends?|everyone)\b'),
         ('phone', r'\b(phone|screen|app|modern|today|digital|online|scroll\w*)\b'), ('chart', r'\b(percent|study|studies|research|experiment\w*|data|evidence|found|measured|survey)\b'),
         ('eye', r'\b(see|saw|look\w*|attention|notice\w*|watch\w*|eyes?|observ\w*)\b'), ('lock', r'\b(habit\w*|stuck|trap|control|secret|hidden)\b'), ('house', r'\b(home|house|room|door|family)\b'),
         ('clock', r'\b(time|clock|hours?|minutes?|days?|years?|century)\b'), ('book', r'\b(book|wrote|write|author|text|read\w*|essay|chapter)\b'), ('bulb', r'\b(idea|insight|realize\w*|learn\w*|understand\w*|answer)\b')]
STOP = set('a an the and or but of to in on at for with from by is are was were be been it its this that these those you your we our they their he she his her i me my as if so than then there here do does did not no yes can could would should will just very really also about into over under up down out more most some any all each every one'.split())
def icon_for(t, i):
    low = t.lower()
    for n, p in ICONS:
        if re.search(p, low): return n
    return ['bulb', 'brain', 'book', 'eye', 'clock'][i % 5]
def key_phrase(t):
    t = re.sub(r'["\u201c\u201d]', '', t).strip()
    first = re.split(r'[,;:\u2014]|(?<=[.!?])\s', t)[0]
    ws = first.split()
    if len(ws) > 7:
        ws = ws[:6]
        while len(ws) > 2 and ws[-1].lower().strip('.,!?') in STOP: ws.pop()
    return ' '.join(ws).strip(' .') or t[:40]
def split_sentences(text): return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z“"\'])', text.strip()) if s.strip()]

def plan_scenes(script, secs):
    """secs: list of {'title','sentences':[{'text','start','end'}]}. Returns scene list [{'start','end','sec','type',...}]."""
    quotes = [re.sub(r'\s+', ' ', p.get('excerpt', '')).strip() for p in script.get('source_passages', [])]
    who = script.get('author', '')
    scenes, n = [], 0
    for si, sec in enumerate(secs):
        sents = sec['sentences']; i = 0
        while i < len(sents):
            j = i; a = sents[i]['start']
            while j + 1 < len(sents) and sents[j]['end'] - a < 4.5: j += 1
            txt = ' '.join(s['text'] for s in sents[i:j + 1]); end = sents[j]['end']
            sp = {'start': a, 'sec': si, 'text': key_phrase(txt), 'icon': icon_for(txt, n)}
            low = txt.lower(); typ = 'figure' if n % 2 == 0 else 'big'
            q = next((q for q in quotes if q and len(q) > 25 and q[:40] in re.sub(r'\s+', ' ', txt)), None)
            m = re.search(r'\b(\d[\d,\.]*\s?(?:%|percent|years?|hours?|minutes?|days?)?)', txt)
            if si == 0 and i == 0: typ = 'question'; sp['text'] = script.get('hook') or script.get('public_title', '').split('|')[0].strip()
            elif q: typ = 'quote'; sp['text'] = q[:230]; sp['who'] = who
            elif re.search(r'\b(today|now|modern|nowadays)\b', low) and re.search(r'\b(then|back then|century|centuries|ago|old|once|earlier|past)\b', low):
                typ = 'versus'; parts = re.split(r'(?i)\b(?:today|now|nowadays|modern)\b', txt, 1)
                sp.update({'left': key_phrase(parts[0]) if parts[0].strip() else 'Back then', 'right': key_phrase(parts[1]) if len(parts) > 1 and parts[1].strip() else 'Today', 'left_icon': 'scroll', 'right_icon': 'phone'})
            elif m and len(m.group(1).strip()) <= 12 and re.search(r'\d', m.group(1)): typ = 'stat'; sp['big'] = m.group(1).strip(); sp['text'] = key_phrase(txt.replace(m.group(1), ''))
            elif si == len(secs) - 1 and i + (j - i + 1) >= len(sents): typ = 'takeaway'
            if typ == 'figure': sp['pose'] = ['point', 'idle', 'shrug', 'think'][(n // 2) % 4]
            sp['type'] = typ; sp['end'] = end; scenes.append(sp); n += 1; i = j + 1
    for k in range(len(scenes) - 1): scenes[k]['end'] = scenes[k + 1]['start']
    return scenes

def llm_refine(script, scenes):
    """Optional: let the free LLM improve each scene's short phrase/icon (never the narration). Validated; any problem keeps the heuristic plan."""
    try:
        import llm
        if not llm.available(): return scenes
        items = [{'i': i, 'type': s['type'], 'text': s['text'], 'icon': s['icon']} for i, s in enumerate(scenes) if s['type'] in ('figure', 'big', 'takeaway')]
        allowed = [n for n, _ in ICONS] + ['scroll', 'question']
        for k in range(0, len(items), 40):
            chunk = items[k:k + 40]
            prompt = ('For a 2D animated psychology explainer, improve the on-screen phrase (max 6 words, punchy, plain English, no quotes) and pick the best icon for each scene. '
                      'Icons allowed: %s. Return JSON {"scenes":[{"i":N,"text":"...","icon":"..."}]} for exactly these scenes. The narration is: %s\nScenes: %s' % (', '.join(allowed), json.dumps(script.get('hook', '')), json.dumps(chunk)))
            r = llm.json_call('You write short on-screen captions. Reply with JSON only.', prompt)
            for o in (r.get('scenes') or []):
                i = o.get('i')
                if isinstance(i, int) and 0 <= i < len(scenes) and scenes[i]['type'] in ('figure', 'big', 'takeaway'):
                    t = re.sub(r'\s+', ' ', str(o.get('text', ''))).strip()
                    if 2 <= len(t) <= 48 and '_' not in t: scenes[i]['text'] = t
                    if o.get('icon') in allowed: scenes[i]['icon'] = o['icon']
    except Exception as e:
        print('ml2d: llm refine skipped:', str(e)[:100], flush=True)
    return scenes

# ---------------- audio / timing ----------------
def make_voice(script, work):
    """Per-section narration wav + word timings. Real: edge neural voice. ML2D_FAKE=1: silent wav with even timing (tests)."""
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

def assemble(script, jobs, work):
    """Concatenate section audio with a short gap, build sentence/word timeline. Returns (secs, words, total, narration_path)."""
    GAP = .45; t = 0.0; secs = []; words = []; frames = []
    for si, j in enumerate(jobs):
        tm = json.loads(Path(j['timing']).read_text()); toks = tm.get('tokens') or []; dur = tm['duration']
        with wave.open(j['wav']) as w: frames.append(w.readframes(w.getnframes())); rate = w.getframerate()
        text = script['sections'][si]['narration']; sents = split_sentences(text); allw = text.split(); ratio = (len(toks) / max(1, len(allw))) if toks else 0
        def tok(i, key):
            if toks: tt = toks[min(len(toks) - 1, int(i * ratio))]; return tt[key]
            return (i / max(1, len(allw))) * dur
        k = 0; ss = []
        for s in sents:
            n = len(s.split()); a = t + tok(k, 'start'); b = t + (tok(min(len(allw) - 1, k + n - 1), 'end') if toks else ((k + n) / max(1, len(allw))) * dur)
            for q, wd in enumerate(s.split()): words.append({'w': wd, 's': t + tok(k + q, 'start'), 'e': t + (tok(k + q, 'end') if toks else ((k + q + 1) / max(1, len(allw))) * dur), 'sent': len(words)})
            ss.append({'text': s, 'start': a, 'end': b}); k += n
        if ss: ss[0]['start'] = t
        secs.append({'title': script['sections'][si].get('title', ''), 'sentences': ss, 'start': t, 'end': t + dur})
        t += dur + GAP; frames.append(b'\x00\x00' * int(rate * GAP))
    out = work / 'narration.wav'
    with wave.open(str(out), 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(b''.join(frames))
    return secs, words, t + 1.0, out

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
    now = fi / FPS; c = Cv(); scenes = G['scenes']
    for x in range(0, W, 64):
        for y in range(0, H, 64): c.circ(x + 32, y + 32, 1.6, SOFT, None, 0)
    idx = max(0, bisect.bisect_right(G['starts'], now) - 1); sp = scenes[idx]; lt = now - sp['start']; dur = max(.5, sp['end'] - sp['start'])
    SCENES[sp['type']](c, sp, lt, dur, now)
    sec = G['secs'][sp['sec']]; chip = '%d  %s' % (sp['sec'] + 1, sec['title'][:34])
    cw = tw(chip, 26) + 36; c.rr(24, 22, 24 + cw, 68, 16, INK, INK, 2); c.text((42, 33), chip, 26, WHITE)
    c.text((W - 26, 30), 'MindLore', 28, BLUE, 'ra')
    ci = max(0, bisect.bisect_right(G['cstarts'], now) - 1); ch = G['chunks'][ci]
    if now >= ch[0]['s'] - .05 and now <= ch[-1]['e'] + .6:
        txt = ' '.join(x['w'] for x in ch); size = 38; wd = tw(txt, size) + 50
        if wd > 1180: size = 32; wd = tw(txt, size) + 50
        x0 = (W - wd) / 2; c.rr(x0, 618, x0 + wd, 684, 20, INK, INK, 2); x = x0 + 25
        for wrd in ch:
            on = wrd['s'] <= now; c.text((x, 626), wrd['w'], size, GOLD if (on and now <= wrd['e'] + .12) else (WHITE if on else (175, 175, 185))); x += tw(wrd['w'] + ' ', size)
    c.rr(0, H - 5, W * clamp(now / G['total']), H, 0, ACC, None, 0)
    return c.out().tobytes()

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

def build(sid, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); work = out / '.work'; work.mkdir(exist_ok=True)
    p = Path(sid) if str(sid).endswith('.json') else BASE / 'cinematic-scripts-mindlore' / (str(sid) + '.json')
    script = json.loads(p.read_text())
    jobs = make_voice(script, work); secs, words, total, narr = assemble(script, jobs, work)
    if os.environ.get('ML2D_MAXSEC'): total = min(total, float(os.environ['ML2D_MAXSEC']))   # tests only
    scenes = llm_refine(script, plan_scenes(script, secs))
    G.update(scenes=scenes, starts=[s['start'] for s in scenes], secs=secs, total=total)
    chunks = caption_chunks(words); G['chunks'] = chunks; G['cstarts'] = [ch[0]['s'] for ch in chunks]
    # music bed
    mix = work / 'mix.m4a'; bed = None
    try:
        sys.path.insert(0, str(BASE)); import music_director
        info = music_director.make_bed('mindlore', 'full', json.dumps(script)[:6000], total, work / 'bed.wav', words=len(words), key=str(script.get('book_id', '')) + '|' + str(script.get('public_title', '')))
        bed = info['path'] if info else None
    except Exception as e: print('ml2d: music skipped:', str(e)[:100], flush=True)
    if bed:
        fc = '[0:a]loudnorm=I=-17:TP=-2:LRA=9,asplit=2[v][sc];[1:a]volume=0.55[m];[m][sc]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=500[d];[v][d]amix=inputs=2:duration=first:normalize=0[a]'
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(narr), '-i', bed, '-filter_complex', fc, '-map', '[a]', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', str(mix)]
    else: cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(narr), '-af', 'loudnorm=I=-16:TP=-2:LRA=9', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', str(mix)]
    subprocess.run(cmd, check=True)
    nf = int(total * FPS); final = out / 'ml2d_LONGFORM.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-', '-i', str(mix), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-t', '%.2f' % total, '-movflags', '+faststart', str(final)], stdin=subprocess.PIPE)
    import multiprocessing as mp
    with mp.get_context('fork').Pool(max(1, os.cpu_count() or 2)) as pool:
        for k, b in enumerate(pool.imap(draw_frame, range(nf), chunksize=24)):
            enc.stdin.write(b)
            if k % 600 == 0: print('ml2d: frame %d/%d' % (k, nf), flush=True)
    enc.stdin.close()
    if enc.wait(): raise RuntimeError('video encode failed')
    thumbnail(script, out / 'THUMBNAIL.jpg')
    chapters = '\n'.join('%d:%02d %s' % (int(s['start']) // 60, int(s['start']) % 60, s['title']) for s in secs)
    desc = (script.get('hook', '') + '\n\nMindLore explains psychology from the original texts. Original commentary inspired by %s by %s. Modern examples are our interpretations, not author quotations.\n\nChapters:\n%s' % (script.get('title', ''), script.get('author', ''), chapters))
    try:
        sys.path.insert(0, str(BASE)); import ml_series
        desc += ml_series.footer({'public_title': script.get('public_title'), 'book_title': script.get('title'), 'author': script.get('author'), 'source_url': script.get('source_url')})
    except Exception:
        desc += '\n\nSource: ' + str(script.get('source_url', ''))
    try:
        import hashtags; desc += '\n\n' + hashtags.mindlore(script.get('hook', '') + ' ' + script.get('title', ''), 'full')
    except Exception: desc += '\n\n#psychology #MindLore'
    (out / 'POST_THIS.txt').write_text('--- TITLE ---\n' + script.get('public_title', script.get('title', '')) + '\n\n--- DESCRIPTION ---\n' + desc[:4900])
    (out / 'ml2d-plan.json').write_text(json.dumps({'scenes': scenes, 'total': total, 'style': 'ml2d-v1'}, indent=1))
    print('ml2d: done', final, '%.0fs' % total, flush=True)
    return final

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
