"""One-canvas whiteboard renderer (ShelfMade long videos): ONE white canvas, a pen hand draws items on the spoken
word, items stay, and the camera pulls back after each panel so the next idea has room. Free: numpy + OpenCV + Pillow + ffmpeg.

Spec (JSON-able dict):
 {'duration': 120.0,
  'panels': [{'title': 'German Army', 'tag': '1942',
              'items': [{'t': 1.0, 'kind': 'icon', 'name': 'tank', 'label': '100'},
                        {'t': 4.0, 'kind': 'text', 'text': 'Stalingrad', 'color': 'r'},
                        {'t': 7.0, 'kind': 'number', 'text': '$10'},
                        {'t': 9.0, 'kind': 'arrow', 'frm': 0, 'to': 1},
                        {'t': 11.0, 'kind': 'cross', 'target': 0}]}]}
 Items fill slots 0..5 of a panel (3 columns x 2 rows) in order; arrow/cross refer to earlier slot numbers.
"""
import math, subprocess, sys, json
import numpy as np, cv2
from PIL import Image, ImageDraw
from wb_icons import ICONS, LT

W, H, FPS = 1280, 720, 30
COLS = 3
INK = {'k': (35, 35, 40), 'r': (45, 45, 210), 'g': (80, 160, 60), 'b': (200, 120, 50), 'y': (30, 190, 240), 'o': (40, 130, 235)}  # BGR
FONT = cv2.FONT_HERSHEY_SCRIPT_SIMPLEX
SLOTS_PER_PANEL = 6
SC = 3                    # slot columns inside a panel
GEOM = (80, 150, 373, 270, 186, 105)   # x0, y0, cell w, cell h, centre dx, centre dy
MAXW, AM, TITLE_SCALE, HS = 360, (125, 110), 2.2, 0.5
OUT = (1280, 720)         # final video size
BRAND, INTRO, END = 'ShelfMade', 2.0, 2.4   # name written by the pen at the start, small corner mark all video, subscribe card at the end
VERT = False


def configure(vertical=False):
    """vertical=True: portrait Short (world cells 720x1280, 2x3 slots, output 1080x1920)."""
    global W, H, SC, GEOM, MAXW, AM, TITLE_SCALE, HS, OUT, VERT
    VERT = bool(vertical)
    if vertical:
        W, H, SC, GEOM, MAXW, AM, TITLE_SCALE, HS, OUT = 720, 1280, 2, (40, 140, 320, 340, 160, 130), 290, (92, 110), 1.5, 0.42, (1080, 1920)
    else:
        W, H, SC, GEOM, MAXW, AM, TITLE_SCALE, HS, OUT = 1280, 720, 3, (80, 150, 373, 270, 186, 105), 360, (125, 110), 2.2, 0.5, (1280, 720)


def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


def seg_len(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def slot_center(panel_idx, slot):
    px, py = (panel_idx % COLS) * W, (panel_idx // COLS) * H
    c, r = slot % SC, slot // SC
    x0, y0, cw, ch, dx, dy = GEOM
    return px + x0 + cw * c + dx, py + y0 + ch * r + dy


def text_layer(text, scale, thick):
    (tw, th), base = cv2.getTextSize(text, FONT, scale, thick)
    pad = 10
    img = np.full((th + base + 2 * pad, tw + 2 * pad), 255, np.uint8)
    cv2.putText(img, text, (pad, th + pad), FONT, scale, 0, thick, cv2.LINE_AA)
    return img  # 255 background, dark ink


def build_item(panel_idx, slot, it):
    """Return {'parts': [...], 'fills': [...], 'kind':...}; parts are ('s', colour, pts) or ('t', colour, layer, x, y)."""
    kind = it['kind']; cx, cy = slot_center(panel_idx, slot)
    parts, fills = [], []
    if kind == 'icon':
        ic = ICONS.get(it['name'])
        if ic is None and str(it['name']).startswith('emoji:'):
            try:
                import wb_emoji; ic = wb_emoji.icon(it['name'][6:])
            except Exception:
                ic = None
        if ic is None:
            ic = ICONS['paper']
        S = 1.9; ox, oy = cx - 50 * S, cy - 50 * S
        tr = lambda p: [(ox + x * S, oy + y * S) for x, y in p]
        for col, pts in ic['strokes']:
            parts.append(('s', col, tr(pts), 5))
        fills = [(col, tr(pts)) for col, pts in ic['fills']]
        if it.get('label'):
            lay = text_layer(str(it['label']), 1.5, 2)
            if lay.shape[1] > GEOM[2] - 20:
                f = (GEOM[2] - 20) / lay.shape[1]; lay = cv2.resize(lay, (GEOM[2] - 20, max(8, int(lay.shape[0] * f))), interpolation=cv2.INTER_AREA)
            parts.append(('t', it.get('lcolor', 'k'), lay, cx - lay.shape[1] / 2, cy + 105 + 6))
    elif kind in ('text', 'number'):
        lay = text_layer(str(it['text']), 2.3 if kind == 'text' else 3.0, 3 if kind == 'text' else 4)
        h, w = lay.shape
        if w > MAXW:
            f = MAXW / w; lay = cv2.resize(lay, (MAXW, max(10, int(h * f))), interpolation=cv2.INTER_AREA); h, w = lay.shape
        x, y = cx - w / 2, cy - h / 2
        col = it.get('color', 'r' if kind == 'number' else 'k')
        if kind == 'number':
            parts.append(('s', 'r', [(x - 8, y - 4), (x + w + 8, y - 4), (x + w + 8, y + h + 4), (x - 8, y + h + 4), (x - 8, y - 4)], 4))
        parts.append(('t', col, lay, x, y))
    elif kind == 'arrow':
        a = slot_center(panel_idx, it['frm']); b = slot_center(panel_idx, it['to'])
        d = math.dist(a, b) or 1; ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        s = (a[0] + ux * AM[0], a[1] + uy * AM[1] * (1 if abs(uy) > .3 else 0.2)); e = (b[0] - ux * AM[0], b[1] - uy * AM[1] * (1 if abs(uy) > .3 else 0.2))
        parts.append(('s', 'k', [s, e], 6))
        hx, hy = -uy, ux
        parts.append(('s', 'k', [(e[0] - ux * 26 + hx * 16, e[1] - uy * 26 + hy * 16), e, (e[0] - ux * 26 - hx * 16, e[1] - uy * 26 - hy * 16)], 6))
    elif kind == 'cross':
        tx, ty = slot_center(panel_idx, it['target'])
        parts.append(('s', 'r', [(tx - 80, ty - 80), (tx + 80, ty + 80)], 9))
        parts.append(('s', 'r', [(tx + 80, ty - 80), (tx - 80, ty + 80)], 9))
    elif kind == 'title':
        px, py = (panel_idx % COLS) * W, (panel_idx // COLS) * H
        x = px + 60
        if it.get('tag'):
            lay = text_layer(str(it['tag']), TITLE_SCALE, 3); h, w = lay.shape
            parts.append(('s', 'r', [(x - 6, py + 34), (x + w + 6, py + 34), (x + w + 6, py + 34 + h + 6), (x - 6, py + 34 + h + 6), (x - 6, py + 34)], 4))
            parts.append(('t', 'k', lay, x, py + 38)); x += w + 24
        lay = text_layer(str(it['text']), TITLE_SCALE, 3)
        lim = px + W - (270 if VERT else 40)
        if x + lay.shape[1] > lim:
            f = (lim - x) / lay.shape[1]; lay = cv2.resize(lay, (int(lay.shape[1] * f), max(8, int(lay.shape[0] * f))), interpolation=cv2.INTER_AREA)
        parts.append(('t', 'k', lay, x, py + 38))
    elif kind == 'frame':
        px, py = (panel_idx % COLS) * W, (panel_idx // COLS) * H
        parts.append(('s', 'a', [(px + 18, py + 18), (px + W - 18, py + 18), (px + W - 18, py + H - 18), (px + 18, py + H - 18), (px + 18, py + 18)], 9))
    total = 0.0
    for p in parts:
        p_len = seg_len(p[2]) if p[0] == 's' else p[2].shape[1] * 1.6
        total += p_len
    return {'parts': parts, 'fills': fills, 'total': max(total, 1.0), 'kind': kind}


def make_hand(mood='idle'):
    import wb_hand
    return wb_hand.make_hand(mood)


class Renderer:
    def __init__(self, spec):
        self.spec = spec; panels = spec['panels']; self.n = len(panels)
        rows = max(1, math.ceil(self.n / COLS))
        import wb_cover
        cv = spec.get('cover') or {'title': panels[0].get('title', ''), 'emoji': '\U0001F4A1'}
        self.accent = tuple(spec.get('accent') or wb_cover.accent_for(cv['title']))
        INK['a'] = self.accent[::-1]
        self.world = np.empty((rows * H, COLS * W, 3), np.uint8); self.world[:] = wb_cover.BG[::-1]
        rng = np.random.default_rng(3); g = rng.integers(-3, 4, self.world.shape[:2], dtype=np.int16)
        self.world = np.clip(self.world.astype(np.int16) + g[:, :, None], 0, 255).astype(np.uint8)
        tn = np.array(wb_cover.tint(self.accent)[::-1], np.int16)
        for q in range(self.n):
            qx, qy = (q % COLS) * W, (q // COLS) * H
            self.world[qy + 22:qy + H - 22, qx + 22:qx + W - 22] = np.clip(tn + g[qy + 22:qy + H - 22, qx + 22:qx + W - 22, None], 0, 255).astype(np.uint8)
        self.base = self.world.copy()
        self.cover_img = wb_cover.cover(cv['title'], cv['emoji'], self.accent, W, H, VERT)
        self.items = []
        for pi, p in enumerate(panels):
            its = [{'t': p.get('t0', 0.0), 'kind': 'title', 'text': p.get('title', ''), 'tag': p.get('tag')}]
            its[0]['t'] = (max(INTRO, p['items'][0]['t'] - 1.4) if pi == 0 else p['items'][0]['t'] - 1.4) if p.get('items') else 0.0
            for i, it in enumerate(p.get('items', [])[:SLOTS_PER_PANEL]):
                its.append(dict(it, _slot=i))
            self.items += [(pi, it) for it in its]
            last = max(it['t'] for it in its)
            self.items.append((pi, {'t': last + 2.2, 'kind': 'frame', '_last': True}))
        self.sched = []
        self.items.sort(key=lambda x: x[1]['t'])
        prev_end = -1
        built = []
        for pi, it in self.items:
            b = build_item(pi, it.get('_slot', 0), it); b['panel'] = pi; b['t'] = it['t']; b['it'] = it
            built.append(b)
        for i, b in enumerate(built):
            start = max(b['t'], prev_end + 0.05)
            nat = {'icon': 1.5, 'text': 0.9, 'number': 1.1, 'arrow': 0.7, 'cross': 0.5, 'title': 1.2, 'frame': 0.9}[b['kind']]
            if b['kind'] in ('icon', 'text', 'number', 'title'):
                nat = max(nat, b['total'] / 900.0 * 1.2)
            if i + 1 < len(built):
                avail = max(0.35, built[i + 1]['t'] - start - 0.08)
                if b['kind'] in ('icon', 'text', 'number'):
                    nat = min(max(nat, min(avail, 3.5)), avail)     # pen keeps drawing until the next thing is said
                elif b['kind'] in ('arrow', 'cross'):
                    nat = min(max(nat, min(avail, 1.2)), avail)
                else:
                    nat = min(nat, avail)
            b['start'], b['dur'] = start, nat; prev_end = start + nat
            b['drawn'] = 0.0; b['done'] = False
        self.items = built
        self.hands = {m: make_hand(m) for m in ('idle', 'wow', 'happy', 'think')}; self.hand, self.hand_a = self.hands['idle']; self.vis = 0.0; self.tip = (W / 2, H / 2)
        self.moods = sorted((float(a), b) for a, b in spec.get('moods', []))
        self.punches = sorted(float(x) for x in spec.get('punches', []))
        self._caps = self._build_caps(spec.get('captions', [])) if VERT else []
        lg = text_layer(BRAND, 2.0, 3); lw = int(W * (0.30 if VERT else 0.17)); lg = cv2.resize(lg, (lw, max(8, int(lg.shape[0] * lw / lg.shape[1]))), interpolation=cv2.INTER_AREA)
        self.logo = (255 - lg).astype(np.float32) / 255.0 * 0.62
        self.logo_xy = (W - lw - 24, 20) if VERT else (W - lw - 30, 26)
        self._camera_keys()

    def _camera_keys(self):
        first, last = {}, {}
        for b in self.items:
            pi = b['panel']
            first[pi] = min(first.get(pi, 1e9), b['start']); last[pi] = max(last.get(pi, 0), b['start'] + b['dur'])
        keys = []
        def pv(pi): return ((pi % COLS) * W + W / 2, (pi // COLS) * H + H / 2, float(W))
        def ov(k):
            xs0, ys0, xs1, ys1 = 0, 0, 0, 0
            cols = [(q % COLS) for q in range(k + 1)]; rows = [(q // COLS) for q in range(k + 1)]
            x0, x1 = min(cols) * W, (max(cols) + 1) * W; y0, y1 = min(rows) * H, (max(rows) + 1) * H
            bw, bh = (x1 - x0) * 1.08, (y1 - y0) * 1.08
            vw = max(bw, bh * W / H, W * 1.45)
            return ((x0 + x1) / 2, (y0 + y1) / 2, vw)
        keys.append((0.0,) + pv(0))
        tin = max(0.0, first[0] - 0.6)
        for pi in range(self.n):
            tout = last[pi] + 0.15
            keys.append((tin,) + pv(pi)); keys.append((tout,) + pv(pi))
            if pi + 1 < self.n:
                tin = max(tout + 1.2, first[pi + 1] - 0.6)
                keys.append(((tout + tin) / 2,) + ov(pi + 1))
        end = float(self.spec.get('duration', 0))
        if end > keys[-1][0] + 4:
            keys.append((end - 3.0,) + pv(self.n - 1)); keys.append((end - 0.3,) + ov(self.n))
        keys.sort(key=lambda k: k[0]); self.keys = keys

    def camera(self, t):
        k = self.keys
        if t <= k[0][0]: return k[0][1:]
        for a, b in zip(k, k[1:]):
            if a[0] <= t <= b[0]:
                u = smooth((t - a[0]) / max(1e-6, b[0] - a[0]))
                return (a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, math.exp(math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * u))
        return k[-1][1:]

    def advance(self, t):
        active = None
        for b in self.items:
            if t < b['start'] or b['done'] and not (b['start'] <= t <= b['start'] + b['dur'] + 0.2):
                continue
            p = smooth((t - b['start']) / b['dur']) if b['dur'] > 0 else 1.0
            target = p * b['total']
            tip = self._draw_to(b, target)
            if p < 1.0 or t <= b['start'] + b['dur'] + 0.2:
                active = tip or active
            if p >= 1.0 and not b['done']:
                self._finish(b)
        if active:
            self.tip = active
        self.vis += ((1.0 if active else 0.0) - self.vis) * 0.3

    def _draw_to(self, b, target):
        pos, tip = 0.0, None
        for part in b['parts']:
            ln = seg_len(part[2]) if part[0] == 's' else part[2].shape[1] * 1.6
            lo, hi = pos, pos + ln
            if b['drawn'] < hi and target > lo:
                a = max(b['drawn'], lo) - lo; z = min(target, hi) - lo
                if part[0] == 's':
                    tip = self._stroke(part, a, z) or tip
                else:
                    tip = self._text(part, a / ln, z / ln) or tip
            pos = hi
        b['drawn'] = max(b['drawn'], target)
        return tip

    def _stroke(self, part, a, z):
        col, pts, th = INK[part[1]], part[2], part[3]
        acc, tip = 0.0, None
        for i in range(len(pts) - 1):
            L = math.dist(pts[i], pts[i + 1])
            if acc + L <= a: acc += L; continue
            s = max(0.0, (a - acc) / L) if L else 0; e = min(1.0, (z - acc) / L) if L else 1
            if e > s:
                p0 = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * s, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * s)
                p1 = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * e, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * e)
                cv2.line(self.world, (int(round(p0[0])), int(round(p0[1]))), (int(round(p1[0])), int(round(p1[1]))), col, th, cv2.LINE_AA)
                tip = p1
            acc += L
            if acc >= z: break
        return tip

    def _text(self, part, u0, u1):
        col, lay, x, y = INK[part[1]], part[2], int(part[3]), int(part[4])
        h, w = lay.shape; c0, c1 = int(u0 * w), max(int(u0 * w) + 1, int(u1 * w))
        c1 = min(c1, w)
        y0, y1 = max(0, y), min(self.world.shape[0], y + h); x0, x1 = max(0, x + c0), min(self.world.shape[1], x + c1)
        if y1 <= y0 or x1 <= x0: return None
        sub = lay[y0 - y: y1 - y, x0 - x: x1 - x].astype(np.float32) / 255.0
        reg = self.world[y0:y1, x0:x1].astype(np.float32)
        colv = np.array(col, np.float32)[None, None, :]
        self.world[y0:y1, x0:x1] = np.minimum(reg, sub[:, :, None] * 255 + (1 - sub[:, :, None]) * colv).astype(np.uint8)
        return (x + c1, y + h * 0.55)

    def _finish(self, b):
        b['done'] = True
        if b['fills']:
            layer = np.zeros_like(self.world); mask = np.zeros(self.world.shape[:2], np.uint8)
            for col, pts in b['fills']:
                rgb = col if isinstance(col, tuple) else LT.get(col, (230, 230, 230)); cv2.fillPoly(layer, [np.array(pts, np.int32)], rgb[::-1]); cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
            white = (np.abs(self.world.astype(np.int16) - self.base.astype(np.int16)).sum(axis=2) < 30) & (mask > 0)
            self.world[white] = layer[white]

    def _build_caps(self, caps):
        """caps = [{'t0','t1','words':[w,..]}]: each chunk is pre-drawn once per highlighted word (white text, dark outline, current word in yellow)."""
        from PIL import ImageFont
        import wb_cover
        font = next((ImageFont.truetype(f, 54) for f in wb_cover.FONTS if __import__('os').path.exists(f)), ImageFont.load_default())
        out = []
        for cp in caps:
            words = cp['words']; variants = []
            for hi in range(len(words)):
                im = Image.new('RGBA', (W, 96), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
                total = sum(d.textlength(w + ' ', font=font) for w in words); x = (W - total) / 2
                for j, w in enumerate(words):
                    d.text((x, 14), w, font=font, fill=(255, 214, 0, 255) if j == hi else (255, 255, 255, 255), stroke_width=6, stroke_fill=(30, 30, 35, 255)); x += d.textlength(w + ' ', font=font)
                a = np.array(im); variants.append((a[:, :, :3][:, :, ::-1].astype(np.float32), a[:, :, 3:4].astype(np.float32) / 255.0))
            out.append((cp['t0'], cp['t1'], cp['times'], variants))
        return out

    def _caption(self, out, t):
        for t0, t1, times, var in self._caps:
            if t0 <= t < t1:
                hi = max(j for j, tt in enumerate(times) if tt <= t + 1e-6) if any(tt <= t for tt in times) else 0
                bgr, al = var[hi]; y = H - 140
                reg = out[y:y + 96].astype(np.float32); out[y:y + 96] = (reg * (1 - al) + bgr * al).astype(np.uint8)
                return

    def _mood(self, t):
        m = 'idle'
        for tt, mo in self.moods:
            if tt <= t: m = mo
            else: break
        return m

    def _punch(self, t):
        p = 0.0
        for te in self.punches:
            if te > t: break
            u = (t - te) / 0.42
            if 0 <= u <= 1: p = max(p, 0.05 * math.sin(math.pi * u))
        return p

    def _pencil(self, out, tx, ty, hs):
        self.hand, self.hand_a = self.hands.get(self._mood(self._t), self.hands['idle'])
        hand = cv2.resize(self.hand, None, fx=hs, fy=hs, interpolation=cv2.INTER_AREA); ha = cv2.resize(self.hand_a, None, fx=hs, fy=hs, interpolation=cv2.INTER_AREA)
        ox, oy = int(tx - 34 * hs), int(ty - 34 * hs)
        hh, hw = hand.shape[:2]
        ya0, xa0 = max(0, oy), max(0, ox); ya1, xa1 = min(H, oy + hh), min(W, ox + hw)
        if ya1 > ya0 and xa1 > xa0:
            a = ha[ya0 - oy: ya1 - oy, xa0 - ox: xa1 - ox, None]
            out[ya0:ya1, xa0:xa1] = (out[ya0:ya1, xa0:xa1] * (1 - a) + hand[ya0 - oy: ya1 - oy, xa0 - ox: xa1 - ox] * a).astype(np.uint8)

    def _card(self, t, lines, t0, per, cover=False):
        import wb_cover
        """White card; each (text, colour, width fraction) line is written left to right by the pencil, one after another."""
        out = (self.cover_img.copy() if cover else np.full((H, W, 3), 255, np.uint8) + 0); n = len(lines); tip = None
        if not cover: out[:] = self.base[:H, :W][:, :, :] if False else np.array((250, 246, 234)[::-1], np.uint8)
        for k, (txt, col, wf) in enumerate(lines):
            lay = text_layer(txt, 4.0, 6); lw = int(W * wf); lay = cv2.resize(lay, (lw, max(8, int(lay.shape[0] * lw / lay.shape[1]))), interpolation=cv2.INTER_AREA)
            h, w = lay.shape; x = (W - w) // 2; y = int(H / 2 + (k - (n - 1) / 2) * (h + 70) - h / 2)
            if cover:
                px0, py0, px1, py1 = wb_cover.pill(VERT); lay = cv2.resize(lay, (int((px1 - px0) * 0.78), max(8, int(lay.shape[0] * (px1 - px0) * 0.78 / lay.shape[1]))), interpolation=cv2.INTER_AREA); h, w = lay.shape
                x = px0 + ((px1 - px0) - w) // 2; y = py0 + ((py1 - py0) - h) // 2
            u = smooth((t - t0 - k * per) / per)
            if u <= 0: continue
            c1 = max(1, int(u * w)); sub = lay[:, :c1].astype(np.float32) / 255.0
            reg = out[y:y + h, x:x + c1].astype(np.float32); colv = np.array(INK[col] if not cover else INK['k'], np.float32)[None, None, :]
            out[y:y + h, x:x + c1] = np.minimum(reg, sub[:, :, None] * 255 + (1 - sub[:, :, None]) * colv).astype(np.uint8)
            if u < 1.0 or k == n - 1: tip = (x + c1, y + h * 0.55)
        if tip: self._pencil(out, tip[0], tip[1], HS)
        return out

    def frame(self, t):
        self._t = t
        self.advance(t)
        D = float(self.spec.get('duration', 0))
        if t < INTRO:
            return self._card(t, [(BRAND, 'k', 0.30 if not VERT else 0.56)], 0.2, 1.5, cover=True)
        if t >= D:
            return self._card(t, [('Subscribe', 'k', 0.52 if not VERT else 0.66), ('to ' + BRAND, 'a', 0.74 if not VERT else 0.88)], D + 0.1, 0.95)
        cx, cy, vw = self.camera(t); vh = vw * H / W
        x0, y0 = int(round(cx - vw / 2)), int(round(cy - vh / 2)); w, h = int(round(vw)), int(round(vh))
        x0 = max(0, min(self.world.shape[1] - w, x0)) if w <= self.world.shape[1] else 0
        y0 = max(0, min(self.world.shape[0] - h, y0)) if h <= self.world.shape[0] else 0
        crop = self.world[y0:y0 + h, x0:x0 + w]
        out = cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA if w > W else cv2.INTER_LINEAR)
        if self.vis > 0.03:
            sc = W / vw; tx, ty = (self.tip[0] - x0) * sc, (self.tip[1] - y0) * sc
            off = (1 - smooth(self.vis)) * 320
            self._pencil(out, tx + off, ty + off, HS)
        pz = self._punch(t)
        if pz > 0.002:
            ww, hh = int(W / (1 + pz)), int(H / (1 + pz)); xx0, yy0 = (W - ww) // 2, (H - hh) // 2
            out = cv2.resize(out[yy0:yy0 + hh, xx0:xx0 + ww], (W, H), interpolation=cv2.INTER_LINEAR)
        if self._caps: self._caption(out, t)
        lx, ly = self.logo_xy; lh, lw = self.logo.shape
        reg = out[ly:ly + lh, lx:lx + lw].astype(np.float32); a = self.logo[:, :, None]
        out[ly:ly + lh, lx:lx + lw] = (reg * (1 - a) + np.array(INK['k'], np.float32) * a).astype(np.uint8)
        return out


def render(spec, out_mp4, audio=None, fps=FPS, progress=None, vertical=False):
    configure(vertical); r = Renderer(spec); dur = float(spec['duration']) + END
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(fps), '-i', '-']
    if audio: cmd += ['-i', str(audio)]
    if OUT != (W, H): cmd += ['-vf', 'scale=%d:%d:flags=lanczos' % OUT]
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']
    if audio: cmd += ['-af', 'apad', '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += [str(out_mp4)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(dur * fps)
    try:
        for i in range(n):
            p.stdin.write(r.frame(i / fps).tobytes())
            if progress and i % 300 == 0: progress(i, n)
    finally:
        p.stdin.close(); p.wait()
    if p.returncode: raise RuntimeError('ffmpeg failed')
    return out_mp4


if __name__ == '__main__':
    spec = json.loads(open(sys.argv[1]).read()); render(spec, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
