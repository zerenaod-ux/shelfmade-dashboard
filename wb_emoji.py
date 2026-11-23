"""Any-emoji -> whiteboard icon (outline strokes + flat colour fills), so the pen can draw ANYTHING. Free: Noto Color Emoji font only.
icon(ch) -> {'strokes':[('k',pts)],'fills':[(rgb,pts)]} in the 100x100 box used by wb_icons."""
import os, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

FONTS = ['/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', '/usr/share/fonts/noto/NotoColorEmoji.ttf', '/usr/share/fonts/truetype/noto-color-emoji/NotoColorEmoji.ttf']
_cache = {}


def available():
    return any(os.path.exists(f) for f in FONTS)


def _render(ch):
    f = next(x for x in FONTS if os.path.exists(x))
    font = ImageFont.truetype(f, 109)
    im = Image.new('RGBA', (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=font, embedded_color=True)
    a = np.array(im); ys, xs = np.where(a[:, :, 3] > 40)
    if not len(xs): raise ValueError('empty emoji')
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    s = 90.0 / max(a.shape[:2]); a = cv2.resize(a, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    c = np.zeros((100, 100, 4), np.uint8); h, w = a.shape[:2]; y0, x0 = (100 - h) // 2, (100 - w) // 2
    c[y0:y0 + h, x0:x0 + w] = a
    return c


def _poly(cnt, eps=0.9):
    p = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2).astype(float)
    return [(float(x), float(y)) for x, y in p] + [(float(p[0][0]), float(p[0][1]))]


def icon(ch):
    if ch in _cache: return _cache[ch]
    img = _render(ch); mask = (img[:, :, 3] > 90).astype(np.uint8)
    rgb = img[:, :, :3].reshape(-1, 3).astype(np.float32)
    fg = mask.reshape(-1) > 0
    k = 5; lab = np.zeros(len(rgb), np.int32)
    _, labels, centers = cv2.kmeans(rgb[fg], k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0), 2, cv2.KMEANS_PP_CENTERS)
    lab[fg] = labels.reshape(-1) + 1
    lab = lab.reshape(100, 100)
    fills, strokes = [], []
    for i in range(k):
        m = (lab == i + 1).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        col = tuple(int(min(255, v * 0.55 + 255 * 0.45)) for v in centers[i][::-1])   # lighter, BGR for the renderer
        for c in cs:
            if cv2.contourArea(c) >= 14: fills.append((cv2.contourArea(c), (col[2], col[1], col[0]), _poly(c, 0.8)))
    fills = [(col, pts) for _, col, pts in sorted(fills, key=lambda f: -f[0])]
    cs, _ = cv2.findContours(cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    for c in sorted(cs, key=cv2.contourArea, reverse=True)[:3]:
        if cv2.contourArea(c) >= 30: strokes.append(('k', _poly(c, 0.9)))
    # inner detail: strong colour edges
    edge = cv2.Canny(cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY), 60, 140) * (cv2.erode(mask, np.ones((5, 5), np.uint8)))
    ec, _ = cv2.findContours(edge, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(ec, key=lambda c: cv2.arcLength(c, False), reverse=True)[:6]:
        if cv2.arcLength(c, False) >= 18: strokes.append(('k', [(float(x), float(y)) for x, y in cv2.approxPolyDP(c, 1.0, False).reshape(-1, 2)]))
    _cache[ch] = {'strokes': strokes, 'fills': fills}
    return _cache[ch]


if __name__ == '__main__':
    ic = icon('🍞'); print(len(ic['strokes']), len(ic['fills']))
