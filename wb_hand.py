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
    S = SS
    im = Image.new('RGBA', (SZ * S, SZ * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    k = lambda pts: [(x * S, y * S) for x, y in pts]
    skin, shade, hi, edge = (244, 196, 162, 255), (222, 165, 130, 255), (255, 224, 198, 255), (110, 66, 50, 255)
    nail = (252, 226, 214, 255)
    # sleeve (cuff) + forearm leaving the corner
    sleeve = [(330, 520), (430, 400), (560, 470), (560, 560), (430, 560)]
    wrist = [(300, 330), (380, 290), (470, 380), (440, 470), (360, 450)]
    d.polygon(k(wrist), fill=skin, outline=edge)
    d.polygon(k([(380, 430), (470, 380), (580, 470), (580, 580), (440, 580)]), fill=(72, 98, 132, 255), outline=(40, 56, 82, 255))
    d.line(k([(420, 455), (520, 520)]), fill=(52, 74, 104, 255), width=3 * S)
    d.line(k([(396, 478), (470, 560)]), fill=(52, 74, 104, 255), width=3 * S)
    # fingers curled UNDER the pen (middle, ring, pinky) - drawn first
    _cap(d, k(_bez((350, 330), (320, 330), (290, 310), (262, 292))), 34 * S, shade, edge, 5 * S)
    _cap(d, k(_bez((370, 360), (340, 365), (310, 350), (290, 335))), 30 * S, shade, edge, 5 * S)
    _cap(d, k(_bez((385, 385), (360, 392), (335, 380), (318, 368))), 26 * S, shade, edge, 5 * S)
    # pen
    pen = [(TIP[0], TIP[1]), (TIP[0] + 330, TIP[1] + 330)]
    ang = math.atan2(1, 1); nx, ny = -math.sin(ang), math.cos(ang)
    def band(t0, t1, w, col, out=None):
        a = (TIP[0] + (t1 - t0) * 0 + t0 * math.cos(ang), TIP[1] + t0 * math.sin(ang)); b = (TIP[0] + t1 * math.cos(ang), TIP[1] + t1 * math.sin(ang))
        poly = [(a[0] + nx * w, a[1] + ny * w), (b[0] + nx * w, b[1] + ny * w), (b[0] - nx * w, b[1] - ny * w), (a[0] - nx * w, a[1] - ny * w)]
        d.polygon(k(poly), fill=col, outline=out)
    # tapered tip
    tipa = (TIP[0], TIP[1]); tb = (TIP[0] + 46 * math.cos(ang), TIP[1] + 46 * math.sin(ang))
    d.polygon(k([tipa, (tb[0] + nx * 11, tb[1] + ny * 11), (tb[0] - nx * 11, tb[1] - ny * 11)]), fill=(40, 40, 46, 255), outline=(15, 15, 18, 255))
    band(46, 120, 13, (232, 62, 62, 255), (120, 20, 20, 255))
    band(120, 440, 13, (52, 54, 62, 255), (20, 20, 26, 255))
    band(120, 440, 4, (112, 116, 128, 255))
    band(120, 128, 14, (190, 190, 200, 255))
    # thumb (left of the pen, pinching)
    _cap(d, k(_bez((330, 345), (292, 330), (262, 300), (222, 262))), 36 * S, skin, edge, 5 * S)
    d.ellipse(k([(200, 244), (238, 282)])[0] + k([(200, 244), (238, 282)])[1], fill=skin, outline=edge)
    _cap(d, k([(214, 252), (228, 266)]), 14 * S, nail, None)
    # index finger over the pen toward the tip
    idx = _bez((400, 300), (350, 255), (290, 240), (206, 196))
    _cap(d, k(idx), 34 * S, skin, edge, 5 * S)
    _cap(d, k(idx[2:-2]), 10 * S, hi, None)
    _cap(d, k([(196, 188), (214, 204)]), 15 * S, nail, None)
    # back of the hand
    d.ellipse(k([(335, 255), (505, 440)])[0] + k([(335, 255), (505, 440)])[1], fill=skin, outline=edge, width=4 * S)
    d.ellipse(k([(372, 276), (452, 350)])[0] + k([(372, 276), (452, 350)])[1], fill=hi)
    for a, b in [((400, 300), (418, 352)), ((430, 288), (452, 340))]:
        d.line(k([a, b]), fill=shade, width=3 * S)
    im = im.filter(ImageFilter.GaussianBlur(0.4 * S)).resize((SZ, SZ), Image.LANCZOS)
    a = np.array(im)
    yy, xx = np.mgrid[0:SZ, 0:SZ]
    fade = np.clip(np.minimum(SZ - xx, SZ - yy) / 90.0, 0, 1)
    a[:, :, 3] = (a[:, :, 3] * fade).astype(np.uint8)
    return a[:, :, :3][:, :, ::-1].copy(), a[:, :, 3].astype(np.float32) / 255.0


if __name__ == '__main__':
    bgr, al = make_hand(); bg = np.full(bgr.shape, 255, np.uint8)
    out = (bg * (1 - al[:, :, None]) + bgr * al[:, :, None]).astype(np.uint8)
    cv2.circle(out, TIP, 4, (0, 0, 255), -1); cv2.imwrite('/tmp/wb/hand.png', out)
