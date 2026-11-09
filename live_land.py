"""Native WIDE (1280x720) scene drawers for full-length MindLore videos: full-screen scenes, no split, no slide look.
Same beat dict format as live_demo.py; drawer signature f(c, b, lt, T, bg, acc, ink). Canvas is 1280x720 (Cv(bg,(1280,720)))."""
import math, random, re
import live_demo as D
from brain_demo import mix, ease, back, lerp, clamp, K, INK
from live_demo import ctext, emo, wrap, mascot, MOOD, _s, _l
CX, CY = 640, 300
def rays(c, bg, acc, lt, cx=CX, cy=CY):
    for i in range(18):
        a = i / 18 * 2 * math.pi + lt * .35
        c.d.polygon([(cx * K, cy * K), ((cx + 1500 * math.cos(a - .07)) * K, (cy + 1500 * math.sin(a - .07)) * K), ((cx + 1500 * math.cos(a + .07)) * K, (cy + 1500 * math.sin(a + .07)) * K)], fill=mix(bg, acc, .16) if i % 2 else mix(bg, acc, .07))
def l_title(c, b, lt, T, bg, acc, ink):
    rays(c, bg, acc, lt, 330, 320); emo(c, b.get('emoji'), 330 + 6 * math.sin(lt * 20), 320 + 8 * math.sin(lt * 6), 430 * back(lt / .3), 1, int(6 * math.sin(lt * 4)))
    ws = _s(b.get('text'), 40).upper().split() or ['WAIT']; lines = [' '.join(ws[i:i + 2]) for i in range(0, len(ws), 2)][:3]
    for i, l in enumerate(lines):
        u = back((lt - i * .16) / .22)
        if u > 0:
            sz = 130
            while c.tw(l, sz) > 640 and sz > 40: sz -= 6
            c.text(930 + 5 * math.sin(lt * 30) * (1 - ease(lt / .5)), 320 + (i - (len(lines) - 1) / 2) * 150, l, sz * u, acc if i % 2 == 0 else ink, 'mm', 6, bg)
def l_icon(c, b, lt, T, bg, acc, ink):
    rays(c, bg, acc, lt); emo(c, b.get('emoji'), CX, CY + 10 * math.sin(lt * 4), 400 * back(lt / .3), 1, int(8 * math.sin(lt * 5)))
    for i in range(5): a = lt * 1.4 + i * 1.256; emo(c, b.get('emoji'), CX + 420 * math.cos(a), CY + 190 * math.sin(a), 100 * ease(lt / .5), .8)
    ctext(c, CX, 560, _s(b.get('text'), 40).upper(), 76 * back((lt - .1) / .25), acc, 1100, 6, bg)
def l_counter(c, b, lt, T, bg, acc, ink):
    v0 = float(b.get('start') or 0); v1 = float(b.get('value') or 0); tt = min(1.4, T * .65); v = lerp(v0, v1, ease(lt / tt)); unit = b.get('unit') or ''
    s = ('%d' % round(v)) if abs(v1 - round(v1)) < 1e-6 else ('%.1f' % v); big = 1 + .1 * math.exp(-max(0, lt - tt) * 8) * (lt > tt)
    emo(c, b.get('emoji'), 250, 300 + 10 * math.sin(lt * 5), 330 * back(lt / .3)); c.text(800, 270, s + unit, min(300, 900 / max(1, len(s + unit)) * 1.5) * big, acc, 'mm', 7, bg)
    ctext(c, 800, 470, _s(b.get('text'), 60).upper(), 52, ink, 640)
def l_flow(c, b, lt, T, bg, acc, ink):
    A, Bp = (200, 300), (1080, 300); tt = max(.7, T * .55); u = ease((lt - .35) / tt); arr = ease((lt - .2) / .3)
    c.line([A, (A[0] + (Bp[0] - A[0]) * arr, A[1])], 10, mix(bg, acc, .5))
    emo(c, b.get('a'), A[0], A[1], 260 * back(lt / .3)); emo(c, b.get('b'), Bp[0], Bp[1], 260 * back((lt - .1) / .3) * (1 + .15 * math.exp(-max(0, lt - .35 - tt) * 7) * (u >= 1)))
    c.text(A[0], 470, _s(b.get('la'), 24).upper(), 36, ink); c.text(Bp[0], 470, _s(b.get('lb'), 24).upper(), 36, ink)
    if lt >= .35:
        for k in range(6, 0, -1):
            uu = max(0, u - k * .035); c.ell(lerp(A[0] + 120, Bp[0] - 120, uu), 300 - 110 * math.sin(uu * math.pi), 10, 10, mix(bg, acc, .6))
        px = lerp(A[0] + 120, Bp[0] - 120, u); py = 300 - 110 * math.sin(u * math.pi)
        if u < 1: c.ell(px, py, 44, 44, acc, INK, 3); emo(c, b.get('dot') or '✨', px, py, 56)
        else: r = (lt - .35 - tt) * 3; c.ell(Bp[0], Bp[1], 150 + 90 * r, 150 + 90 * r, None, acc, max(1, 8 - 6 * clamp(r)))
    ctext(c, CX, 570, _s(b.get('text'), 70).upper(), 44, ink, 1100)
def l_versus(c, b, lt, T, bg, acc, ink):
    win = b.get('win', 'a'); tw_ = .9
    for side, x in (('a', 320), ('b', 960)):
        w = side == win; k = ease((lt - tw_) / .4); s = 330 * back((lt - (0 if side == 'a' else .15)) / .3) * (1 + .3 * k if w else 1 - .3 * k)
        emo(c, b.get(side), x, 290, s, 1.0 if w else 1 - .55 * k); ctext(c, x, 500, _s(b.get('l' + side), 24).upper(), 44, ink, 500)
        if w and k > 0: emo(c, '👑', x, 80 + 10 * (1 - k), 120 * k)
    if lt > .35: c.text(CX, 290, 'VS', 120 * back((lt - .35) / .25) * (1 - .6 * ease((lt - tw_) / .3)), acc, 'mm', 6, bg)
    ctext(c, CX, 580, _s(b.get('text'), 70).upper(), 44, ink, 1100)
def l_meter(c, b, lt, T, bg, acc, ink):
    f, t_ = float(b.get('frm') or 0), float(b.get('to') or 1); v = lerp(f, t_, ease((lt - .2) / max(.7, T * .6)))
    c.rr(120, 300, 1160, 400, 50, mix(bg, (255, 255, 255), .3), ink, 5); w = max(10, 1020 * v); c.rr(130, 310, 130 + w, 390, 40, mix((230, 70, 60), (70, 200, 110), v), None, 0)
    emo(c, b.get('emoji'), 130 + w, 200 - 20 * abs(math.sin(lt * 6)), 190 * back(lt / .3))
    if not b.get('hide'): c.text(CX, 490, '%d%%' % round(v * 100), 120, acc, 'mm', 6, bg)
    ctext(c, CX, 590, _s(b.get('text'), 60).upper(), 46, ink, 1100)
def l_react(c, b, lt, T, bg, acc, ink):
    mood = MOOD.get(b.get('emoji') or '😳', 'shock'); mascot(c, 330 + 10 * math.sin(lt * 35) * (1 - ease(lt / 1.2)), 330, 1.7 * back(lt / .25), mood, lt)
    if lt > .25:
        k = back((lt - .25) / .25); c.rr(660, 190 + 120 * (1 - k), 660 + 560 * k, 430, 44, (255, 255, 255), INK, 5)
        if k > .7: ctext(c, 940, 310, _s(b.get('text'), 60), 60, INK, 500)
def l_search(c, b, lt, T, bg, acc, ink):
    q = _s(b.get('text') or 'why do we do this', 48); k = back(lt / .3); tt = max(.9, T * .5); n = int(clamp(lt / tt) * len(q)); sz = 52
    while c.tw(q, sz) > 820 and sz > 24: sz -= 2
    c.rr(140, 90 + 20 * (1 - k), 1140, 220 + 20 * (1 - k), 64, (255, 255, 255), INK, 6); emo(c, '🔍', 214, 155, 80 * k); c.text(280, 158, q[:n] + ('|' if int(lt * 3) % 2 == 0 and n < len(q) + 1 else ''), sz, INK, 'lm')
    for i in range(3):
        u = back((lt - tt - .15 - i * .2) / .25)
        if u <= 0: continue
        x = 140 + i * 350; hot = i == 0; c.rr(x, 300 + 150 * (1 - u), x + 320, 570 + 150 * (1 - u), 30, acc if hot else (255, 255, 255), INK, 4)
        if u > .6:
            emo(c, (b.get('emoji') or '💡') if hot else ['📄', '📰'][i - 1], x + 160, 400, 120 * u); c.rr(x + 30, 490, x + 290, 506, 8, (255, 255, 255) if hot else (205, 205, 210)); c.rr(x + 30, 525, x + 220, 541, 8, mix(acc if hot else (205, 205, 210), (255, 255, 255), .5))
def l_chat(c, b, lt, T, bg, acc, ink):
    ms = _l(b.get('msgs') or b.get('items') or ['wait', 'really?'], 4, 50); y = 90
    for i, m in enumerate(ms):
        u = back((lt - .15 - i * .75) / .3); left = i % 2 == 0; sz = 44; ls = wrap(c, m, sz, 700); h = len(ls) * 54 + 40; w = max(c.tw(l, sz) for l in ls) + 60
        if u > 0:
            x0 = 230 if left else 1050 - w; cy = y + h / 2; c.rr(x0, cy - h / 2 * u, x0 + w, cy + h / 2 * u, 40, (255, 255, 255) if left else acc, INK, 4)
            if u > .7:
                for j, l in enumerate(ls): c.text(x0 + w / 2, cy + (j - (len(ls) - 1) / 2) * 54, l, sz, INK if left else (bg if sum(acc) > 450 else (255, 255, 255)))
            emo(c, b.get('emoji') or '🙂', 150 if left else 1130, cy, 90 * u)
        y += h + 26
def l_headline(c, b, lt, T, bg, acc, ink):
    k = back(lt / .3); P = (250, 244, 228); c.rr(170, 100 + 30 * (1 - k), 1110, 615, 16, P, INK, 5); c.text(CX, 150, 'THE DAILY MIND', 48 * k, INK); c.line([(210, 188), (1070, 188)], 5, INK)
    emo(c, b.get('emoji'), 350, 395, 250 * back((lt - .1) / .3)); ctext(c, 790, 385, _s(b.get('text'), 70).upper(), 62 * back((lt - .25) / .25), INK, 520)
    for i in range(2): c.rr(560, 535 + i * 30, 1060 - i * 140, 547 + i * 30, 6, (200, 195, 185))
    s = back((lt - .6) / .25)
    if s > 0: c.text(CX, 52, 'BREAKING', 66 * s, (214, 40, 40), 'mm', 5, bg)
def l_countdown(c, b, lt, T, bg, acc, ink):
    n = 3 - int(lt / .55)
    if n > 0: ph = (lt % .55) / .55; c.ell(CX, CY, 220 + 70 * ph, 220 + 70 * ph, None, acc, max(1, 10 - 8 * ph)); c.text(CX, CY, str(n), 460 * back(ph / .5), acc, 'mm', 8, bg)
    else: u = back((lt - 1.65) / .25); emo(c, b.get('emoji'), 330, 300, 340 * u); ctext(c, 880, 300, _s(b.get('text') or 'GO', 30).upper(), 130 * u, acc, 520, 6, bg)
def l_timeline(c, b, lt, T, bg, acc, ink):
    it = _l(b.get('items'), 4, 4) or ['⏳']; lb = _l(b.get('labels'), 4, 22); n = len(it); x0, x1 = 170, 1110; ctext(c, CX, 70, _s(b.get('text'), 50).upper(), 46, ink, 1000)
    c.line([(x0, 320), (x0 + (x1 - x0) * ease(lt / (n * .6 + .3)), 320)], 12, mix(bg, acc, .6))
    for i, e in enumerate(it):
        u = back((lt - .2 - i * .6) / .3); x = x0 + (x1 - x0) * (i / max(1, n - 1)) if n > 1 else CX
        if u > 0:
            c.ell(x, 320, 36 * u, 36 * u, acc, INK, 4); emo(c, e, x, 200 - 10 * (1 - u), 170 * u)
            if i < len(lb): ctext(c, x, 430, lb[i].upper(), 42 * u, ink, 280)
def l_scale(c, b, lt, T, bg, acc, ink):
    heavy = 1 if b.get('heavy', 'b') == 'b' else -1; a = .22 * heavy * ease((lt - .5) / .7) + .03 * math.sin(lt * 5) * (1 - ease((lt - .5) / .7)); pv = (CX, 190)
    c.d.polygon([(pv[0] - 80) * K, 560 * K, (pv[0] + 80) * K, 560 * K, pv[0] * K, pv[1] * K], fill=mix(bg, ink, .5)); Lg = 420
    Lp = (pv[0] - Lg * math.cos(a), pv[1] - Lg * math.sin(a)); Rp = (pv[0] + Lg * math.cos(a), pv[1] + Lg * math.sin(a)); c.line([Lp, Rp], 16, ink)
    for side, P_, key in ((0, Lp, 'a'), (1, Rp, 'b')):
        u = back((lt - side * .15) / .3); c.line([P_, (P_[0], P_[1] + 150)], 5, ink); c.ell(P_[0], P_[1] + 160, 130, 30, acc, INK, 4)
        emo(c, b.get(key), P_[0], P_[1] + 80 - 20 * (1 - u), 170 * u); ctext(c, P_[0], P_[1] + 235, _s(b.get('l' + key), 22).upper(), 36, ink, 320)
    c.ell(pv[0], pv[1], 24, 24, acc, INK, 4); ctext(c, CX, 40, _s(b.get('text'), 60).upper(), 42, ink, 1000)
def l_crowd(c, b, lt, T, bg, acc, ink):
    cols, rows = 9, 4; e = b.get('emoji') or '🧍'; pk = b.get('pick') or '🤩'; sel = random.Random(int(b.get('_seed', 1))).randrange(cols * rows)
    for r in range(rows):
        for q in range(cols):
            i = r * cols + q; u = back((lt - i * .03) / .25)
            if u <= 0: continue
            x = 160 + q * 120; y = 110 + r * 120; hot = i == sel and lt > 1.0
            if hot: k = back((lt - 1.0) / .3); c.ell(x, y, 62 * k, 62 * k, acc, INK, 4); emo(c, pk, x, y, 120 * k)
            else: emo(c, e, x, y, 90 * u, .55 if lt > 1.0 else 1)
    ctext(c, CX, 590, _s(b.get('text'), 60).upper(), 46, ink, 1100)
def l_checklist(c, b, lt, T, bg, acc, ink):
    it = _l(b.get('items') or ['one', 'two'], 4, 30); ctext(c, CX, 60, _s(b.get('text'), 40).upper(), 46, ink, 1000)
    for i, s_ in enumerate(it):
        u = back((lt - .1 - i * .7) / .3); y = 170 + i * 125
        if u <= 0: continue
        c.rr(220, y - 50 * u, 1060, y + 50 * u, 28, (255, 255, 255), INK, 4)
        if u > .6:
            c.rr(250, y - 34, 318, y + 34, 12, None, INK, 5); ctext(c, 700, y, s_.upper(), 46, INK, 700); k = ease((lt - .3 - i * .7) / .25)
            if k > 0: c.line([(262, y), (282, y + 22 * k), (282 + 36 * k, y - 26 * k)] if k > .5 else [(262, y), (262 + 40 * k, y + 44 * k)], 12, (60, 170, 90))
def l_before_after(c, b, lt, T, bg, acc, ink):
    k = ease((lt - .7) / .5); c.rr(90, 70, 1190, 560, 36, mix(bg, (120, 120, 130), .25), INK, 5); xr = lerp(1190, 640, k); c.rr(xr, 70, 1190, 560, 36, mix(bg, acc, .35), INK, 5)
    emo(c, b.get('a'), 365, 270, 270 * back(lt / .3) * (1 - .3 * k)); ctext(c, 365, 470, _s(b.get('la') or 'BEFORE', 18).upper(), 48, ink, 400)
    if k > 0: emo(c, b.get('b'), 915, 270, 300 * k); ctext(c, 915, 470, _s(b.get('lb') or 'AFTER', 18).upper(), 48, ink, 400)
    ctext(c, CX, 625, _s(b.get('text'), 70).upper(), 42, ink, 1100)
def l_notif(c, b, lt, T, bg, acc, ink):
    it = _l(b.get('items') or ['new message'], 4, 44)
    for i, s_ in enumerate(it):
        u = ease((lt - .1 - i * .55) / .25)
        if u <= 0: continue
        y = 110 + i * 130 - 120 * (1 - u); sh = 5 * math.sin(lt * 40) * (1 - ease((lt - i * .55 - .35) / .3)) if lt > i * .55 + .1 else 0
        c.rr(210 + sh, y - 55, 1070 + sh, y + 55, 32, (255, 255, 255), INK, 4); emo(c, b.get('emoji') or '🔔', 285 + sh, y, 80); ctext(c, 700 + sh, y, s_, 42, INK, 700)
    c.ell(1090, 70, 30 * back(lt / .3), 30 * back(lt / .3), (230, 50, 50), INK, 3)
def l_zoom(c, b, lt, T, bg, acc, ink):
    z = 1.7 - .7 * ease(lt / .7); lb = _l(b.get('labels'), 4, 18); emo(c, b.get('emoji'), CX, 300, 400 * z * (1 + .03 * math.sin(lt * 5))); pts = [(220, 120), (1060, 130), (220, 500), (1060, 480)]
    for i, s_ in enumerate(lb):
        u = back((lt - .6 - i * .3) / .3)
        if u <= 0: continue
        x, y = pts[i]; c.line([(CX + (x - CX) * .3, 300 + (y - 300) * .3), (x, y)], 6, acc); c.rr(x - 150 * u, y - 40 * u, x + 150 * u, y + 40 * u, 24, (255, 255, 255), INK, 4)
        if u > .6: ctext(c, x, y, s_.upper(), 32, INK, 270)
    ctext(c, CX, 600, _s(b.get('text'), 60).upper(), 44, ink, 1100)
def l_clock(c, b, lt, T, bg, acc, ink):
    cx, cy, r = 330, 310, 250; c.ell(cx, cy, r, r, (255, 255, 255), INK, 8)
    for i in range(12): a = i / 12 * 2 * math.pi; c.line([(cx + (r - 32) * math.sin(a), cy - (r - 32) * math.cos(a)), (cx + (r - 8) * math.sin(a), cy - (r - 8) * math.cos(a))], 6, INK)
    a = (ease(lt / 2.5) * 14 + lt) * 2 * math.pi; c.line([(cx, cy), (cx + 185 * math.sin(a), cy - 185 * math.cos(a))], 10, acc); c.line([(cx, cy), (cx + 120 * math.sin(a / 12), cy - 120 * math.cos(a / 12))], 15, INK); c.ell(cx, cy, 16, 16, INK)
    emo(c, b.get('emoji') or '⏰', 880, 200 + 8 * math.sin(lt * 9), 200 * back(lt / .3), 1, int(14 * math.sin(lt * 18))); ctext(c, 880, 410, _s(b.get('text'), 50).upper(), 64, ink, 560)
LDRAW = {'title_slam': l_title, 'icon_burst': l_icon, 'counter': l_counter, 'flow': l_flow, 'versus': l_versus, 'meter': l_meter, 'reaction': l_react, 'search': l_search, 'chat': l_chat, 'headline': l_headline, 'countdown': l_countdown,
         'timeline': l_timeline, 'scale': l_scale, 'crowd': l_crowd, 'checklist': l_checklist, 'before_after': l_before_after, 'notif': l_notif, 'zoom': l_zoom, 'clock': l_clock}
FALLBACK = {'slots': 'icon_burst', 'chart': 'icon_burst', 'brain': 'zoom'}
