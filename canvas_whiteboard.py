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


def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


def seg_len(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def slot_center(panel_idx, slot):
    px, py = (panel_idx % COLS) * W, (panel_idx // COLS) * H
    c, r = slot % 3, slot // 3
    return px + 80 + 373 * c + 186, py + 150 + 270 * r + 105


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
        if ic is None:
            ic = ICONS['paper']
        S = 1.9; ox, oy = cx - 50 * S, cy - 50 * S
        tr = lambda p: [(ox + x * S, oy + y * S) for x, y in p]
        for col, pts in ic['strokes']:
            parts.append(('s', col, tr(pts), 5))
        fills = [(col, tr(pts)) for col, pts in ic['fills']]
        if it.get('label'):
            lay = text_layer(str(it['label']), 1.5, 2)
            parts.append(('t', it.get('lcolor', 'k'), lay, cx - lay.shape[1] / 2, cy + 105 + 6))
    elif kind in ('text', 'number'):
        lay = text_layer(str(it['text']), 2.3 if kind == 'text' else 3.0, 3 if kind == 'text' else 4)
        h, w = lay.shape
        if w > 360:
            f = 360 / w; lay = cv2.resize(lay, (360, max(10, int(h * f))), interpolation=cv2.INTER_AREA); h, w = lay.shape
        x, y = cx - w / 2, cy - h / 2
        col = it.get('color', 'r' if kind == 'number' else 'k')
        if kind == 'number':
            parts.append(('s', 'r', [(x - 8, y - 4), (x + w + 8, y - 4), (x + w + 8, y + h + 4), (x - 8, y + h + 4), (x - 8, y - 4)], 4))
        parts.append(('t', col, lay, x, y))
    elif kind == 'arrow':
        a = slot_center(panel_idx, it['frm']); b = slot_center(panel_idx, it['to'])
        d = math.dist(a, b) or 1; ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        s = (a[0] + ux * 125, a[1] + uy * 110 * (1 if abs(uy) > .3 else 0.2)); e = (b[0] - ux * 125, b[1] - uy * 110 * (1 if abs(uy) > .3 else 0.2))
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
            lay = text_layer(str(it['tag']), 2.2, 3); h, w = lay.shape
            parts.append(('s', 'r', [(x - 6, py + 34), (x + w + 6, py + 34), (x + w + 6, py + 34 + h + 6), (x - 6, py + 34 + h + 6), (x - 6, py + 34)], 4))
            parts.append(('t', 'k', lay, x, py + 38)); x += w + 24
        lay = text_layer(str(it['text']), 2.2, 3)
        parts.append(('t', 'k', lay, x, py + 38))
    elif kind == 'frame':
        px, py = (panel_idx % COLS) * W, (panel_idx // COLS) * H
        parts.append(('s', 'k', [(px + 18, py + 18), (px + W - 18, py + 18), (px + W - 18, py + H - 18), (px + 18, py + H - 18), (px + 18, py + 18)], 7))
    total = 0.0
    for p in parts:
        p_len = seg_len(p[2]) if p[0] == 's' else p[2].shape[1] * 1.6
        total += p_len
    return {'parts': parts, 'fills': fills, 'total': max(total, 1.0), 'kind': kind}


def make_hand():
    import wb_hand
    return wb_hand.make_hand()


class Renderer:
    def __init__(self, spec):
        self.spec = spec; panels = spec['panels']; self.n = len(panels)
        rows = max(1, math.ceil(self.n / COLS))
        self.world = np.full((rows * H, COLS * W, 3), 255, np.uint8)
        self.items = []
        for pi, p in enumerate(panels):
            its = [{'t': p.get('t0', 0.0), 'kind': 'title', 'text': p.get('title', ''), 'tag': p.get('tag')}]
            its[0]['t'] = p['items'][0]['t'] - 1.4 if p.get('items') else 0.0
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
                nat = min(nat, max(0.35, built[i + 1]['t'] - start - 0.05))
            b['start'], b['dur'] = start, nat; prev_end = start + nat
            b['drawn'] = 0.0; b['done'] = False
        self.items = built
        self.hand, self.hand_a = make_hand(); self.vis = 0.0; self.tip = (W / 2, H / 2)
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
            vw = max(bw, bh * 16 / 9, W * 1.45)
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
                rgb = LT.get(col, (230, 230, 230)); cv2.fillPoly(layer, [np.array(pts, np.int32)], rgb[::-1]); cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
            white = (self.world.min(axis=2) > 235) & (mask > 0)
            self.world[white] = layer[white]

    def frame(self, t):
        self.advance(t)
        cx, cy, vw = self.camera(t); vh = vw * H / W
        x0, y0 = int(round(cx - vw / 2)), int(round(cy - vh / 2)); w, h = int(round(vw)), int(round(vh))
        x0 = max(0, min(self.world.shape[1] - w, x0)) if w <= self.world.shape[1] else 0
        y0 = max(0, min(self.world.shape[0] - h, y0)) if h <= self.world.shape[0] else 0
        crop = self.world[y0:y0 + h, x0:x0 + w]
        out = cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA if w > W else cv2.INTER_LINEAR)
        if self.vis > 0.03:
            sc = W / vw; tx, ty = (self.tip[0] - x0) * sc, (self.tip[1] - y0) * sc
            hs = 0.5
            hand = cv2.resize(self.hand, None, fx=hs, fy=hs, interpolation=cv2.INTER_AREA); ha = cv2.resize(self.hand_a, None, fx=hs, fy=hs, interpolation=cv2.INTER_AREA)
            off = (1 - smooth(self.vis)) * 320
            ox, oy = int(tx - 34 * hs + off), int(ty - 34 * hs + off)
            hh, hw = hand.shape[:2]
            ya0, xa0 = max(0, oy), max(0, ox); ya1, xa1 = min(H, oy + hh), min(W, ox + hw)
            if ya1 > ya0 and xa1 > xa0:
                a = ha[ya0 - oy: ya1 - oy, xa0 - ox: xa1 - ox, None]
                out[ya0:ya1, xa0:xa1] = (out[ya0:ya1, xa0:xa1] * (1 - a) + hand[ya0 - oy: ya1 - oy, xa0 - ox: xa1 - ox] * a).astype(np.uint8)
        return out


def render(spec, out_mp4, audio=None, fps=FPS, progress=None):
    r = Renderer(spec); dur = float(spec['duration'])
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '%dx%d' % (W, H), '-r', str(fps), '-i', '-']
    if audio: cmd += ['-i', str(audio)]
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
