"""Cartoon-realistic drawing hand holding a marker (procedural, free). Tip at TIP; sprite is RGBA numpy (BGR + alpha)."""
import math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter

SZ, SS = 560, 3          # sprite size, supersample
TIP = (34, 34)           # pen tip position in the sprite


def _cap(d, pts, w, fill, outline=None, ow=0):
    """Thick round-capped polyline."""
    if outline:
        for a, b in zip(pts, pts[1:]): d.line([a, b], fill=outline, width=int(w + ow))
        for p in (pts[0], pts[-1]) + tuple(pts[1:-1]): d.ellipse([p[0] - (w + ow) / 2, p[1] - (w + ow) / 2, p[0] + (w + ow) / 2, p[1] + (w + ow) / 2], fill=outline)
    for a, b in zip(pts, pts[1:]): d.line([a, b], fill=fill, width=int(w))
    for p in pts: d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=fill)


def _bez(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0], u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out


def make_hand(mood='idle'):
    """Penny the pencil: a chubby cartoon pencil with a face that reacts (idle, wow, happy, think). Tip at TIP; the body fades out toward the corner."""
    S = SS
    im = Image.new('RGBA', (SZ * S, SZ * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    ang = math.atan2(1, 1); ux, uy = math.cos(ang), math.sin(ang); nx, ny = -uy, ux
    k = lambda pts: [(x * S, y * S) for x, y in pts]
    P = lambda t, o=0: (TIP[0] + t * ux + o * nx, TIP[1] + t * uy + o * ny)
    def band(t0, t1, w0, w1, col, out=None):
        a, b = P(t0), P(t1)
        d.polygon(k([(a[0] + nx * w0, a[1] + ny * w0), (b[0] + nx * w1, b[1] + ny * w1), (b[0] - nx * w1, b[1] - ny * w1), (a[0] - nx * w0, a[1] - ny * w0)]), fill=col, outline=out)
    HW = 31
    band(0, 70, 1, HW, (236, 200, 150, 255), (120, 80, 40, 255))       # sharpened wood
    band(0, 20, 1, 8, (50, 50, 56, 255))                                # graphite point
    band(70, 330, HW, HW, (246, 196, 46, 255), (150, 110, 10, 255))     # chubby body
    band(240, 330, 7, 7, (255, 232, 140, 255))                           # shine
    band(330, 365, HW, HW, (190, 190, 200, 255), (110, 110, 120, 255))  # ferrule
    band(365, 470, HW, HW, (240, 130, 140, 255), (150, 60, 70, 255))    # eraser
    # face on the body
    c0 = 135
    def eye(o, r, pr, dx=0, dy=0):
        cx, cy = P(c0, o); d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=(255, 255, 255, 255), outline=(40, 30, 20, 255), width=2 * S)
        d.ellipse([(cx - pr + dx) * S, (cy - pr + dy) * S, (cx + pr + dx) * S, (cy + pr + dy) * S], fill=(25, 20, 20, 255))
    if mood == 'wow': eye(-15, 14, 4.5); eye(15, 14, 4.5)
    elif mood == 'think': eye(-15, 11, 5, 3, -4); eye(15, 11, 5, 3, -4)
    elif mood == 'happy': eye(-15, 11, 5); eye(15, 11, 5)
    else: eye(-15, 11, 4.8); eye(15, 11, 4.8)
    m = P(c0 + 38)
    if mood == 'wow': d.ellipse([(m[0] - 8) * S, (m[1] - 11) * S, (m[0] + 8) * S, (m[1] + 11) * S], fill=(120, 40, 40, 255), outline=(40, 30, 20, 255), width=2 * S)
    elif mood == 'happy': d.arc([(m[0] - 17) * S, (m[1] - 13) * S, (m[0] + 17) * S, (m[1] + 10) * S], 20, 160, fill=(40, 30, 20, 255), width=4 * S)
    elif mood == 'think': d.line(k([P(c0 + 32, -8), P(c0 + 32, 8)]), fill=(40, 30, 20, 255), width=3 * S)
    else: d.arc([(m[0] - 12) * S, (m[1] - 8) * S, (m[0] + 12) * S, (m[1] + 8) * S], 20, 160, fill=(40, 30, 20, 255), width=3 * S)
    for o in (-25, 25):   # rosy cheeks
        cx, cy = P(c0 + 16, o * 1.0); d.ellipse([(cx - 5) * S, (cy - 3) * S, (cx + 5) * S, (cy + 3) * S], fill=(246, 150, 140, 150))
    im = im.filter(ImageFilter.GaussianBlur(0.4 * S)).resize((SZ, SZ), Image.LANCZOS)
    a = np.array(im)
    yy, xx = np.mgrid[0:SZ, 0:SZ]
    a[:, :, 3] = (a[:, :, 3] * np.clip(np.minimum(SZ - xx, SZ - yy) / 90.0, 0, 1)).astype(np.uint8)
    return a[:, :, :3][:, :, ::-1].copy(), a[:, :, 3].astype(np.float32) / 255.0


if __name__ == '__main__':
    import sys; bgr, al = make_hand(sys.argv[1] if len(sys.argv) > 1 else 'idle'); bg = np.full(bgr.shape, 255, np.uint8)
    out = (bg * (1 - al[:, :, None]) + bgr * al[:, :, None]).astype(np.uint8)
    cv2.circle(out, TIP, 4, (0, 0, 255), -1); cv2.imwrite('/tmp/wb/hand.png', out)
