"""GitHub runner: makes ONE AnimationDoodles FULL VIDEO (about 8-9 min, 16:9) with NO Mac.
episode (Gemini, 12 scenes) -> ONE Kaggle GPU session for all 72 shots (voices, pictures, word timing) -> ONE Kaggle LatentSync session -> split per scene
-> CPU render of each scene (the same renderer as the Shorts) -> landscape stitch: blurred backdrop, concept side panel, scene progress bar, chapter cards,
intro + outro cards, one continuous ducked music bed -> out/doodles-full-<id>.zip (final.mp4, thumbnail.png, POST_THIS.txt with chapters).
Usage: python doodles_engine/gh_doodles_episode.py [--test N]   (--test N = only the first N scenes, cheap check of the whole chain)
Env: GEMINI_API_KEY, KAGGLE_API_TOKEN. Posts nothing: review_publish.py opens the review Issue afterwards."""
import json, os, re, shutil, subprocess, sys, time, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent; DATA = ROOT / 'data/doodles'; DATA.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))
POOL = DATA / 'episode_pool.json'; USED = DATA / 'episodes_used.json'; OUT = ROOT / 'out'; OUT.mkdir(exist_ok=True)
W, H, FPS = 1920, 1080, 30
LAND = os.environ.get('EPISODE_LANDSCAPE') == '1'   # true 16:9 pictures (set by the workflow input)
if LAND: os.environ['DOODLES_LANDSCAPE'] = '1'
os.environ.setdefault('DOODLES_MOVE', os.environ.get('EPISODE_MOVE', '1'))   # subtle head/shoulder motion in full videos (render.py)
CLEAN = LAND and os.environ.get('EPISODE_CLEAN', '1') != '0'   # full-screen 16:9, nothing drawn on top: no panel, clock, progress bar, chapter/intro/outro cards
TAGS = '#psychology #mindset #animation #relatable #AnimationDoodles'
FONTS = ['/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
         '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
PAT = re.compile(r'^(shot|line|align|ls|lip|open|closed)_(\d\d)(.*)$')


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def jl(p, d):
    try: return json.loads(Path(p).read_text())
    except (OSError, ValueError): return d
def run(*a, **k): return subprocess.run([sys.executable, *map(str, a)], **k)
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, a)], check=True)


def font(size):
    from PIL import ImageFont
    for f in FONTS:
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()


def wrap(draw, text, fnt, maxw):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if cur and draw.textlength(t, font=fnt) > maxw: lines.append(cur); cur = w
        else: cur = t
    return lines + ([cur] if cur else [])


def card(path, lines, sub=None, big=96, pal=((30, 27, 75), (86, 54, 140)), accent=(255, 214, 10)):
    """Chapter / intro / outro card, 1920x1080."""
    from PIL import Image, ImageDraw
    g = Image.new('RGB', (1, H)); gp = g.load()
    for y in range(H):
        t = y / (H - 1); gp[0, y] = tuple(int(pal[0][i] + (pal[1][i] - pal[0][i]) * t) for i in range(3))
    im = g.resize((W, H)); d = ImageDraw.Draw(im); fb = font(big)
    out = []
    for k, ln in enumerate(lines): out += [(x, k == 0) for x in wrap(d, ln, fb, W - 300)]
    hs = big + 18; fs = font(46); sl = wrap(d, sub, fs, W - 400) if sub else []
    total = len(out) * hs + (30 + len(sl) * 62 if sl else 0); y = (H - total) // 2
    for ln, first in out:
        x = (W - d.textlength(ln, font=fb)) / 2
        d.text((x + 4, y + 5), ln, font=fb, fill=(0, 0, 0)); d.text((x, y), ln, font=fb, fill=accent if first else (255, 255, 255)); y += hs
    y += 30
    for ln in sl:
        d.text(((W - d.textlength(ln, font=fs)) / 2, y), ln, font=fs, fill=(230, 226, 255)); y += 62
    im.save(path)


def panel(path, i, n, concept, clock):
    """Transparent overlay: concept on the left, scene clock top right, progress bar at the bottom."""
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f1 = font(52); f2 = font(40); lx = 70; maxw = 480
    if not LAND:
        d.rounded_rectangle((lx - 24, 300, lx + maxw + 24, 640), 28, fill=(20, 16, 50, 190))
        d.text((lx, 330), "TODAY'S TRAP", font=f2, fill=(255, 214, 10))
        y = 400
        for ln in wrap(d, concept.title(), f1, maxw)[:4]: d.text((lx, y), ln, font=f1, fill=(255, 255, 255)); y += 66
    d.text((W - 70 - d.textlength(clock, font=f2), 80), clock, font=f2, fill=(255, 255, 255))
    bx0, bx1, by = 70, W - 70, H - 46
    d.rounded_rectangle((bx0, by, bx1, by + 12), 6, fill=(255, 255, 255, 70))
    d.rounded_rectangle((bx0, by, bx0 + int((bx1 - bx0) * i / n), by + 12), 6, fill=(255, 214, 10, 255))
    im.save(path)


def pick_episode():
    used = set(jl(USED, []))
    want = int(os.environ.get('EPISODE_SCENES', '4'))
    pool = [e for e in jl(POOL, []) if e['id'] not in used and len(e['scenes']) == want]
    if not pool:
        log('writing a new episode...'); (ROOT / 'data').mkdir(exist_ok=True)
        (ROOT / 'data/secrets.json').write_text(json.dumps({'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY', '')}))
        run(HERE / 'episode_writer.py', 1)
        pool = [e for e in jl(POOL, []) if e['id'] not in used and len(e['scenes']) == want]
    return pool[0] if pool else None


def split(work, sc):
    """Combined work dir -> work/sNN per scene, shot indexes renumbered 0..5."""
    subs = []
    for j, s in enumerate(sc):
        sd = work / f's{j:02d}'; shutil.rmtree(sd, ignore_errors=True); (sd / 'ls_out').mkdir(parents=True); (sd / 'ls_in').mkdir()
        for src in (work, work / 'ls_out'):
            if not src.is_dir(): continue
            for f in src.iterdir():
                m = PAT.match(f.name)
                if not m or not f.is_file(): continue
                si = int(m.group(2))
                if si // 6 != j: continue
                dst = (sd / 'ls_out') if src.name == 'ls_out' else sd
                shutil.copy(f, dst / f'{m.group(1)}_{si % 6:02d}{m.group(3)}')
        jobs = jl(work / 'ls_in/jobs.json', {'jobs': []}); mine = []
        for jb in jobs['jobs']:
            if jb['si'] // 6 == j:
                jb = dict(jb); jb['si'] -= 6 * j; jb['key'] = 'ls_%02d_%02d' % (jb['si'], jb['li']); mine.append(jb)
        (sd / 'ls_in/jobs.json').write_text(json.dumps({**jobs, 'jobs': mine}))
        st = dict(s['story']); st['explain_shot'] = 3; st['concept'] = s['concept']; st['mood'] = st.get('mood', 'curious')
        (sd / 'story.json').write_text(json.dumps(st, indent=1)); subs.append(sd)
    return subs


def probe(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def stitch(work, ep, sc, subs):
    n = len(sc); tmp = work / 'seg'; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
    segs, chapters, t = [], [], 0.0
    A = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2']

    def still(name, img, secs):
        o = tmp / f'{name}.mp4'
        ff('-loop', '1', '-framerate', str(FPS), '-t', secs, '-i', img, '-f', 'lavfi', '-t', secs, '-i', 'anullsrc=r=48000:cl=stereo',
           '-vf', f'scale={W}:{H},fade=t=in:st=0:d=0.4,fade=t=out:st={secs - 0.4}:d=0.4,format=yuv420p', '-shortest', *A, o)
        segs.append(o); return secs
    card(tmp / 'intro.png', [ep['title']], ep['premise'], big=120)
    shutil.copy(tmp / 'intro.png', work / 'thumbnail.png')
    if not CLEAN: chapters.append((t, 'Intro')); t += still('intro', tmp / 'intro.png', 5)
    for j, (s, sd) in enumerate(zip(sc, subs)):
        if CLEAN: chapters.append((t, 'Intro' if j == 0 else '%s (%s)' % (s['concept'].title(), s['time'])))
        else:
            card(tmp / f'c{j}.png', ['%d / %d' % (j + 1, n), s['concept'].title()], '%s - %s' % (s['time'], s['setting']), big=110)
            chapters.append((t, '%s (%s)' % (s['concept'].title(), s['time']))); t += still(f'c{j}', tmp / f'c{j}.png', 2.6)
        silent = sd / 'silent.mp4'; wav = sd / 'voice.wav'; d = probe(silent)
        o = tmp / f'sc{j}.mp4'
        if CLEAN:
            ff('-i', silent, '-i', wav, '-vf', f'scale={W}:{H},format=yuv420p', '-map', '0:v', '-map', '1:a', '-t', f'{d:.3f}', *A, o)
            segs.append(o); t += probe(o); log('stitched scene', j + 1, '/', n); continue
        panel(tmp / f'p{j}.png', j + 1, n, s['concept'], s['time'])
        flt = ('[0:v][1:v]overlay=0:0,format=yuv420p[v]' if LAND else
               f'[0:v]split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:6,eq=brightness=-0.15[bg];'
               f'[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0[m];[m][1:v]overlay=0:0,format=yuv420p[v]')
        ff('-i', silent, '-i', tmp / f'p{j}.png', '-i', wav, '-filter_complex', flt, '-map', '[v]', '-map', '2:a', '-t', f'{d:.3f}', *A, o)
        segs.append(o); t += probe(o)
        log('stitched scene', j + 1, '/', n)
    if not CLEAN:
        card(tmp / 'outro.png', ['Which trap was yours?'], 'Tell Leo and Mia in the comments. New story every week - subscribe so you do not miss the next one.', big=100)
        still('outro', tmp / 'outro.png', 7)
    lst = tmp / 'list.txt'; lst.write_text(''.join("file '%s'\n" % p.resolve() for p in segs))
    plain = work / 'plain.mp4'; ff('-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', plain)
    total = probe(plain); music = None
    try:
        for p in (ROOT, HERE):
            if (p / 'music_lab.py').is_file(): sys.path.insert(0, str(p))
        import music_lab
        mood = {'tense': 'dramatic', 'hopeful': 'warm', 'suspense': 'mysterious', 'sad': 'reflective'}.get(sc[0]['story'].get('mood', 'curious'), sc[0]['story'].get('mood', 'curious'))
        music = music_lab.track(mood); log('music', music)
        try:
            import music_director
            try: _w = sum(len(l['text'].split()) for s in sc for sh in s['story']['shots'] for l in sh['lines'])
            except Exception: _w = None
            _b = music_director.make_bed('doodles', 'full', json.dumps(sc[0]['story'], default=str)[:4000], total, work / 'bed.wav', mood=sc[0]['story'].get('mood'), words=_w, key=str(work.name))
            if _b: music = Path(_b['path']); log('music bed', _b['tracks'])
        except Exception as e: log('music director skipped:', e)
    except Exception as e: log('music unavailable:', e)
    if os.environ.get('DOODLES_SFX', '1') != '0': music = None; log('music off: real action sounds only')
    final = work / 'final.mp4'
    if music:
        flt = ('[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[vo][sc];'
               f'[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.55,afade=t=in:st=0:d=2,afade=t=out:st={total - 4:.2f}:d=4[mu];'
               '[mu][sc]sidechaincompress=threshold=0.03:ratio=4:attack=40:release=600[du];[vo][du]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[a]')
        ff('-i', plain, '-stream_loop', '-1', '-i', music, '-filter_complex', flt, '-map', '0:v', '-map', '[a]', '-t', f'{total:.3f}', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', final)
    else:
        shutil.copy(plain, final)
    return final, chapters, total


def stamp(x): x = int(x); return '%d:%02d' % (x // 60, x % 60)


def main():
    test = int(sys.argv[sys.argv.index('--test') + 1]) if '--test' in sys.argv else 0
    ep = pick_episode()
    if not ep: log('no episode available'); sys.exit(1)
    sc = ep['scenes'][:test] if test else ep['scenes']
    assert all(len(s['story']['shots']) == 6 for s in sc), 'every scene must have 6 shots'
    work = DATA / f"{time.strftime('%Y-%m-%d')}-full-{ep['id']}"; work.mkdir(exist_ok=True)
    shots = [sh for s in sc for sh in s['story']['shots']]
    (work / 'story.json').write_text(json.dumps({'id': ep['id'], 'title': ep['title'], 'concept': '', 'mood': sc[0]['story'].get('mood', 'curious'), 'explain_shot': 99, 'landscape': LAND, 'shots': shots}, indent=1))
    t0 = time.time(); log('EPISODE', ep['id'], len(sc), 'scenes', len(shots), 'shots')
    (ROOT / 'data').mkdir(exist_ok=True)
    if run(HERE / 'kaggle_make.py', work).returncode: log('Kaggle stage 1 failed'); sys.exit(1)
    if run(HERE / 'ls_cloud.py', work).returncode: log('cloud lip-sync incomplete; render falls back to fast mouths'); os.environ['FASTLIP'] = '1'
    subs = split(work, sc)
    for j, sd in enumerate(subs):
        code = "import sys;sys.path.insert(0,%r);import render;render.render(%r)" % (str(HERE), str(sd))
        r = subprocess.run([sys.executable, '-c', code])
        if r.returncode or not (sd / 'silent.mp4').is_file() or not (sd / 'voice.wav').is_file(): log('render failed for scene', j + 1); sys.exit(1)
        log('rendered scene', j + 1, '/', len(subs))
    final, chapters, total = stitch(work, ep, sc, subs)
    ch = '\n'.join('%s %s' % (stamp(a), b) for a, b in chapters)
    try:
        import series as _se; _t = _se.title(ep['id'], ep['title'], 'full')
    except Exception:
        _t = ep['title']
    post = f"{_t}\n\n{ep['description']}\n\nChapters:\n{ch}\n\n{TAGS} #Leo #Mia\n"
    z = OUT / f"doodles-full-{ep['id']}.zip"
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED) as f:
        f.write(final, 'final.mp4'); f.write(work / 'thumbnail.png', 'thumbnail.png'); f.writestr('POST_THIS.txt', post)
        if (work / 'bed.music.json').is_file(): f.write(work / 'bed.music.json', 'MUSIC.json')
    if not test:
        used = jl(USED, []); used.append(ep['id']); USED.write_text(json.dumps(used))
    (OUT / 'made.txt').write_text(ep['id']); log('DONE', ep['id'], stamp(total), 'long,', round((time.time() - t0) / 60), 'min')
    for junk in ('k1_in', 'k1_kernel', 'k1_dl', 'ls_in', 'ls_kernel', 'ls_dl', 'seg', 'plain.mp4'):
        p = work / junk; shutil.rmtree(p, ignore_errors=True) if p.is_dir() else (p.unlink() if p.exists() else None)


if __name__ == '__main__': main()
