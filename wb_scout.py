"""Scout: a small explorer who lives in the rooms. Walks to the door at the end of each room and steps through it, then arrives in the next room.
make_scout(frame, accent_rgb) -> (BGR float image, alpha) about 120x170; frames 0-3 = walk cycle, 4 = idle."""
import math
import numpy as np
from PIL import Image, ImageDraw


def make_scout(frame, accent):
    S = 3; w, h = 120, 170
    im = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    k = lambda x, y: (x * S, y * S)
    ink = (35, 35, 40, 255); skin = (246, 205, 170, 255); hat = tuple(accent) + (255,); pack = (150, 100, 60, 255)
    ph = (frame % 4) / 4.0 * 2 * math.pi if frame < 4 else 0.0
    sw = math.sin(ph) * 22 if frame < 4 else 0
    bob = abs(math.cos(ph)) * 4 if frame < 4 else (math.sin(0.0) * 0)
    hip = (60, 100 - bob)
    for sgn, col in ((-1, (70, 80, 110, 255)), (1, (55, 65, 95, 255))):          # legs
        fx = 60 + sgn * sw
        d.line([k(*hip), k(fx, 158)], fill=ink, width=11 * S); d.line([k(*hip), k(fx, 158)], fill=col, width=7 * S)
        d.ellipse([k(fx - 8 + sgn * 3, 154)[0], k(fx, 154)[1], k(fx + 10 + sgn * 3, 166)[0], k(fx, 166)[1]], fill=ink)
    d.rounded_rectangle([k(34, 52 - bob), k(58, 100 - bob)], radius=6 * S, fill=pack, outline=ink, width=2 * S)    # backpack
    d.rounded_rectangle([k(46, 46 - bob), k(78, 102 - bob)], radius=10 * S, fill=hat[:3] + (255,), outline=ink, width=3 * S)  # body (coat in the accent colour)
    for sgn in (-1, 1):                                                          # arms
        ax = 62 + sgn * 16; ay = 58 - bob; hx = ax + sgn * 12 + (-sw * 0.5 * sgn if frame < 4 else 0); hy = ay + 30
        d.line([k(ax, ay), k(hx, hy)], fill=ink, width=9 * S); d.line([k(ax, ay), k(hx, hy)], fill=skin, width=5 * S)
    d.ellipse([k(44, 14 - bob), k(80, 50 - bob)], fill=skin, outline=ink, width=3 * S)                                # head
    d.pieslice([k(38, 4 - bob), k(86, 40 - bob)], 180, 360, fill=hat, outline=ink, width=3 * S)                       # explorer hat
    d.line([k(34, 22 - bob), k(90, 22 - bob)], fill=ink, width=4 * S)
    d.ellipse([k(66, 28 - bob), k(71, 33 - bob)], fill=ink); d.ellipse([k(55, 28 - bob), k(60, 33 - bob)], fill=ink)  # eyes
    d.arc([k(56, 34 - bob), k(72, 46 - bob)], 20, 160, fill=ink, width=2 * S)                                         # smile
    im = im.resize((w, h), Image.LANCZOS); a = np.array(im)
    return a[:, :, :3][:, :, ::-1].astype(np.float32), a[:, :, 3:4].astype(np.float32) / 255.0
