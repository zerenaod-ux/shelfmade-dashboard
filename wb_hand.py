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


def make_hand():
    """Pencil only (owner decision 2026-11-22: no hand). Tip at TIP, pencil runs down-right and fades out."""
    S = SS
    im = Image.new('RGBA', (SZ * S, SZ * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    ang = math.atan2(1, 1); ux, uy = math.cos(ang), math.sin(ang); nx, ny = -uy, ux
    k = lambda pts: [(x * S, y * S) for x, y in pts]
    def band(t0, t1, w0, w1, col, out=None):
        a = (TIP[0] + t0 * ux, TIP[1] + t0 * uy); b = (TIP[0] + t1 * ux, TIP[1] + t1 * uy)
        d.polygon(k([(a[0] + nx * w0, a[1] + ny * w0), (b[0] + nx * w1, b[1] + ny * w1), (b[0] - nx * w1, b[1] - ny * w1), (a[0] - nx * w0, a[1] - ny * w0)]), fill=col, outline=out)
    band(0, 60, 1, 17, (236, 200, 150, 255), (120, 80, 40, 255))      # sharpened wood
    band(0, 18, 1, 6, (50, 50, 56, 255))                               # graphite point
    band(60, 380, 17, 17, (246, 196, 46, 255), (150, 110, 10, 255))   # body
    band(60, 380, 5, 5, (255, 232, 140, 255))                          # highlight stripe
    band(380, 410, 17, 17, (190, 190, 200, 255), (110, 110, 120, 255)) # ferrule
    band(410, 520, 17, 17, (240, 130, 140, 255), (150, 60, 70, 255))  # eraser
    im = im.filter(ImageFilter.GaussianBlur(0.4 * S)).resize((SZ, SZ), Image.LANCZOS)
    a = np.array(im)
    yy, xx = np.mgrid[0:SZ, 0:SZ]
    a[:, :, 3] = (a[:, :, 3] * np.clip(np.minimum(SZ - xx, SZ - yy) / 90.0, 0, 1)).astype(np.uint8)
    return a[:, :, :3][:, :, ::-1].copy(), a[:, :, 3].astype(np.float32) / 255.0


if __name__ == '__main__':
    bgr, al = make_hand(); bg = np.full(bgr.shape, 255, np.uint8)
    out = (bg * (1 - al[:, :, None]) + bgr * al[:, :, None]).astype(np.uint8)
    cv2.circle(out, TIP, 4, (0, 0, 255), -1); cv2.imwrite('/tmp/wb/hand.png', out)
