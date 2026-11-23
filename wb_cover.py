"""Attractive cover card (first 2 s of every video, and the picture people see before pressing play).
Changes with the topic: accent colour from the title, big flat-colour picture (any emoji, drawn as vector), big title text."""
import hashlib, os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

PALETTE = [(232, 93, 76), (28, 160, 160), (86, 98, 214), (240, 160, 30), (52, 168, 98), (150, 90, 200), (40, 130, 220), (226, 80, 140)]
FONTS = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf']
BG = (250, 246, 234)
INKC = (30, 30, 35)


def accent_for(title):
    return PALETTE[int(hashlib.md5(title.encode()).hexdigest(), 16) % len(PALETTE)]


def tint(acc, k=0.15):
    return tuple(int(a * k + 255 * (1 - k)) for a in acc)


def pill(vertical):
    return (130, 1150, 590, 1250) if vertical else (60, 618, 420, 696)   # x0, y0, x1, y1: white tag where the pencil writes the name


def _font(size):
    for f in FONTS:
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _wrap(d, text, size, maxw):
    f = _font(size); words = text.split(); lines, cur = [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return f, lines


def cover(title, emoji, acc, W, H, vertical):
    img = Image.new('RGB', (W, H), acc); d = ImageDraw.Draw(img)
    lt = tuple(int(c * 0.80 + 255 * 0.20) for c in acc)
    d.ellipse([-W * 0.4, -H * 0.15, W * 0.55, H * 0.45], fill=lt); d.ellipse([W * 0.55, H * 0.62, W * 1.5, H * 1.2], fill=lt)
    if vertical: box = (50, 760, W - 50, 1130); circ = (W // 2, 360, 300)
    else: box = (60, 120, 720, 600); circ = (990, 345, 235)
    d.ellipse([circ[0] - circ[2], circ[1] - circ[2], circ[0] + circ[2], circ[1] + circ[2]], fill=(255, 255, 255))
    size = 130 if vertical else 112
    while True:
        f, lines = _wrap(d, title, size, box[2] - box[0])
        lh = int(size * 1.12)
        if (len(lines) * lh <= box[3] - box[1] and all(d.textlength(l, font=f) <= box[2] - box[0] for l in lines)) or size < 40: break
        size -= 6
    px0, py0, px1, py1 = pill(vertical); d.rounded_rectangle([px0, py0, px1, py1], radius=(py1 - py0) // 2, fill=(255, 255, 255))
    y = box[1] + ((box[3] - box[1]) - len(lines) * lh) // 2
    for l in lines:
        x = box[0] + ((box[2] - box[0]) - d.textlength(l, font=f)) // 2 if vertical else box[0]
        d.text((x, y), l, font=f, fill=(255, 255, 255), stroke_width=max(5, size // 14), stroke_fill=INKC)
        y += lh
    a = np.array(img)[:, :, ::-1].copy()
    try:
        import wb_emoji; ic = wb_emoji.icon(emoji)
    except Exception:
        from wb_icons import ICONS; ic = ICONS['bulb']
    S = circ[2] * 1.45 / 100.0; ox, oy = circ[0] - 50 * S, circ[1] - 50 * S
    tr = lambda pts: np.array([(ox + x * S, oy + y * S) for x, y in pts], np.int32)
    from wb_icons import LT
    for col, pts in ic['fills']:
        rgb = col if isinstance(col, tuple) else LT.get(col, (230, 230, 230)); cv2.fillPoly(a, [tr(pts)], rgb[::-1])
    for col, pts in ic['strokes']:
        cv2.polylines(a, [tr(pts)], False, INKC[::-1], max(6, int(S * 1.6)), cv2.LINE_AA)
    return a
