"""TEST ONLY (never posted): one MindLore explainer Short with word-by-word sticky captions.
Each spoken word pops on screen exactly when said; numbers/names get big accent styling; a fact card
appears when a researcher is named. Output: out/mindlore-wordtest.mp4"""
import asyncio, json, re, subprocess, sys, os, glob, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts

W, H, FPS = 1080, 1920, 30
OUT = Path('out'); OUT.mkdir(exist_ok=True)
FONTS = ['/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
STOP = set('a an the and or but of to in on at is are was were be been it its that this you your we our they their for with as by from so then than that\'s i if do does did not no'.split())
PAL = [((20, 24, 60), (90, 40, 140), (255, 205, 70)), ((10, 40, 60), (20, 110, 130), (255, 130, 110)),
       ((40, 18, 50), (150, 50, 100), (120, 230, 255)), ((16, 36, 30), (40, 120, 90), (255, 220, 100))]
_f = {}
def font(sz):
    sz = int(round(sz / 4) * 4)
    if sz not in _f:
        for p in FONTS:
            if os.path.exists(p): _f[sz] = ImageFont.truetype(p, sz); break
    return _f[sz]

def pick():
    fs = sorted(glob.glob('story-shorts/mindlore/*.json'))
    for f in fs:
        d = json.load(open(f))
        if d.get('sections') and d.get('claims'): return d
    raise SystemExit('no story')

async def narrate(text, mp3):
    try: com = edge_tts.Communicate(text, 'en-US-AndrewNeural', rate='+8%', boundary='WordBoundary')
    except TypeError: com = edge_tts.Communicate(text, 'en-US-AndrewNeural', rate='+8%')
    words = []; audio = bytearray()
    async for c in com.stream():
        if c['type'] == 'audio': audio += c['data']
        elif c['type'] == 'WordBoundary': words.append({'t': c['text'], 's': c['offset'] / 1e7, 'e': (c['offset'] + c['duration']) / 1e7})
    mp3.write_bytes(bytes(audio)); return words

def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)], capture_output=True, text=True).stdout)

def bg(scene, t):
    a, b, _ = PAL[scene % len(PAL)]
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    ph = 0.5 + 0.5 * math.sin(t * 0.6)
    g = np.clip(y * 0.8 + x * 0.2 * ph, 0, 1)
    img = (np.array(a)[None, None, :] * (1 - g) + np.array(b)[None, None, :] * g)
    cy, cx = 0.45 + 0.05 * math.sin(t * 0.5), 0.5 + 0.1 * math.cos(t * 0.4)
    r = np.sqrt((y - cy) ** 2 * 0.6 + (x - cx) ** 2)
    img = img + 40 * np.clip(1 - r * 2.2, 0, 1)
    return Image.fromarray(np.clip(img, 0, 255).astype('uint8'))

def tw(d, s, f): return d.textlength(s, font=f)

def main():
    d = pick(); text = ' '.join(s['narration'] for s in d['sections']).replace('‑', '-')
    mp3 = OUT / 'wt.mp3'; words = asyncio.run(narrate(text, mp3)); total = dur(mp3)
    if not words:  # fallback: even spread
        toks = text.split(); step = total / len(toks); words = [{'t': w, 's': i * step, 'e': (i + 1) * step} for i, w in enumerate(toks)]
    # scenes = sentences
    scene_of = []; sc = 0
    for w in words:
        scene_of.append(sc)
        if re.search(r'[.?!]$', w['t']): sc += 1
    claims = d.get('claims', [])
    # fact cards: when the researcher's last name is spoken
    cards = []
    for c in claims:
        last = c['who'].split()[-1].lower()
        for i, w in enumerate(words):
            if last in w['t'].lower():
                cards.append((w['s'], w['s'] + 5.0, c)); break
    n = int((total + 0.6) * FPS)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
                           '-i', str(mp3), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', str(OUT / 'mindlore-wordtest.mp4')], stdin=subprocess.PIPE)
    wi = 0
    for fr in range(n):
        t = fr / FPS
        while wi + 1 < len(words) and words[wi + 1]['s'] <= t: wi += 1
        cur = words[wi] if t >= words[0]['s'] else None
        sc = scene_of[wi]
        img = bg(sc, t); dr = ImageDraw.Draw(img); acc = PAL[sc % len(PAL)][2]
        # top bar
        dr.text((60, 70), 'MINDLORE', font=font(44), fill=(255, 255, 255))
        dr.rectangle((60, 140, W - 60, 150), fill=(255, 255, 255, 60) if False else (90, 90, 110))
        dr.rectangle((60, 140, 60 + int((W - 120) * min(1, t / total)), 150), fill=acc)
        # context line: words of this sentence so far (last 7), current highlighted
        if cur:
            ctx = [i for i in range(len(words)) if scene_of[i] == sc and i <= wi][-7:]
            f = font(54); line = [(words[i]['t'], i == wi) for i in ctx]
            x = W // 2 - int(sum(tw(dr, s + ' ', f) for s, _ in line) / 2)
            # wrap-safe: shrink if too wide
            tot = sum(tw(dr, s + ' ', f) for s, _ in line)
            if tot > W - 100: f = font(54 * (W - 100) / tot); x = 50
            for s, on in line:
                dr.text((x, 1180), s, font=f, fill=acc if on else (200, 200, 220)); x += tw(dr, s + ' ', f)
            # BIG current word with pop
            raw = cur['t']; clean = re.sub(r'^[^\w%$]+|[^\w%$]+$', '', raw)
            key = clean.lower() not in STOP; num = bool(re.search(r'\d', clean))
            age = t - cur['s']; pop = 1 + 0.28 * max(0, 1 - age / 0.14)
            base = 250 if num else (190 if key else 130)
            if len(clean) > 7: base *= 7.5 / len(clean) ** 0.98 if len(clean) > 9 else 0.9
            f = font(base * pop); wd = tw(dr, clean, f)
            while wd > W - 80: base *= 0.9; f = font(base * pop); wd = tw(dr, clean, f)
            col = acc if (key or num) else (255, 255, 255)
            cx, cy = W // 2, 800
            dr.text((cx + 6, cy + 6), clean, font=f, fill=(0, 0, 0), anchor='mm')
            dr.text((cx, cy), clean, font=f, fill=col, anchor='mm')
        # fact card
        for s0, s1, c in cards:
            if s0 <= t <= s1:
                k = min(1, (t - s0) / 0.3, (s1 - t) / 0.3); off = int((1 - k) * 260)
                y0 = 1420 + off
                dr.rounded_rectangle((70, y0, W - 70, y0 + 330), 36, fill=(10, 10, 25), outline=acc, width=5)
                dr.text((110, y0 + 28), '%s  ·  %s' % (c['year'], c['place']), font=font(46), fill=acc)
                dr.text((110, y0 + 100), c['who'], font=font(58), fill=(255, 255, 255))
                claim = c['claim']; f = font(40); lines = []; cur_l = ''
                for w_ in claim.split():
                    if tw(dr, cur_l + ' ' + w_, f) > W - 260: lines.append(cur_l); cur_l = w_
                    else: cur_l = (cur_l + ' ' + w_).strip()
                lines.append(cur_l)
                for j, l in enumerate(lines[:3]): dr.text((110, y0 + 190 + j * 50), l, font=f, fill=(220, 220, 235))
                break
        ff.stdin.write(img.tobytes())
    ff.stdin.close(); ff.wait()
    (OUT / 'wordtest.json').write_text(json.dumps({'title': d.get('public_title'), 'seconds': round(total, 1), 'words': len(words)}))
    print('done', total, len(words))

if __name__ == '__main__': main()
