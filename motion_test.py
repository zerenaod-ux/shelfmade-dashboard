"""MOTION TEST (separate from the live pipeline, posts nothing, makes no review Issue).
Takes a finished clean Doodles clip (final.mp4), cuts the characters out with free models (rembg: isnet-anime, birefnet-general-lite, u2net; CPU), builds a background plate
(inpainting), and renders a demo where ONLY the character moves (talk bob, jump + squash, shake, pop) while the wall stays still. Output goes to a pre-release 'motiontest-*'
that the review pipeline ignores. Usage: python motion_test.py final.mp4 outdir"""
import json, subprocess, sys, time
from pathlib import Path
import cv2
import numpy as np

W, H, FPS = 1280, 720, 30


def sh(*a):
    subprocess.run([str(x) for x in a], check=True)


def frames(video, out):
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(video)], capture_output=True, text=True).stdout.strip())
    paths = []
    for i, f in enumerate((0.25, 0.5, 0.75)):
        p = out / f'frame{i}.png'
        sh('ffmpeg', '-v', 'error', '-y', '-ss', f'{d * f:.2f}', '-i', video, '-frames:v', '1', '-vf', f'scale={W}:{H}', p); paths.append(p)
    return paths


def rembg_mask(path, model):
    from rembg import new_session, remove
    from PIL import Image
    s = new_session(model)
    m = remove(Image.open(path).convert('RGB'), session=s, only_mask=True)
    return np.array(m)


def clean(mask):
    m = (mask > 127).astype('uint8') * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 0.004 * W * H: keep[lab == i] = 255
    return keep


def split_two(m):
    """-> (left_mask, right_mask) of the two characters."""
    d = cv2.dilate(m, np.ones((15, 15), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(d)
    comps = sorted(range(1, n), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:2]
    if len(comps) == 2:
        a, b = sorted(comps, key=lambda i: cen[i][0])
        return (m * (lab == a)).astype('uint8'), (m * (lab == b)).astype('uint8')
    xs = np.where(m.any(0))[0]
    if len(xs) < 20: return m, np.zeros_like(m)
    lo, hi = xs[0] + int(0.3 * (xs[-1] - xs[0])), xs[0] + int(0.7 * (xs[-1] - xs[0]))
    col = (m[:, lo:hi] > 0).sum(0); cut = lo + int(np.argmin(col))
    L = m.copy(); L[:, cut:] = 0; R = m.copy(); R[:, :cut] = 0
    return L, R


def plate(frame, m):
    k = cv2.dilate(m, np.ones((31, 31), np.uint8))
    sm = cv2.resize(frame, (W // 2, H // 2)); sk = cv2.resize(k, (W // 2, H // 2), interpolation=cv2.INTER_NEAREST)
    out = cv2.inpaint(sm, sk, 6, cv2.INPAINT_TELEA)
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_CUBIC)


def layer(frame, m):
    a = cv2.GaussianBlur(m, (0, 0), 1.6).astype('float32') / 255.0
    ys, xs = np.where(m > 0)
    if len(xs) == 0: return None
    return {'rgb': frame.astype('float32') * a[..., None], 'a': a, 'pivot': ((xs.min() + xs.max()) / 2.0, float(ys.max())), 'h': float(ys.max() - ys.min())}


def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


def pose(kind, t, h, w=W):
    """-> dx, dy, sx, sy, rot(deg) for time t seconds inside an action."""
    if kind == 'talk':   # lively talk bob
        b = abs(np.sin(2 * np.pi * 2.2 * t)); return 0.004 * w * np.sin(2 * np.pi * 1.1 * t), -0.018 * h * b, 1 - 0.012 * b, 1 + 0.02 * b, 1.6 * np.sin(2 * np.pi * 1.1 * t)
    if kind == 'jump':   # crouch, jump, land with squash
        if t < 0.15: u = t / 0.15; return 0, 0, 1 + 0.06 * u, 1 - 0.10 * u, 0
        if t < 0.75: u = (t - 0.15) / 0.6; return 0, -0.22 * h * 4 * u * (1 - u), 0.96, 1.06, 0
        if t < 0.95: u = (t - 0.75) / 0.2; return 0, 0, 1 + 0.12 * (1 - u), 1 - 0.16 * (1 - u), 0
        return 0, 0, 1, 1, 0
    if kind == 'shake':  # nervous shiver
        a = max(0.0, 1 - t / 1.1); return 0.014 * w * a * np.sin(2 * np.pi * 17 * t), 0.004 * h * a * np.sin(2 * np.pi * 23 * t), 1, 1, 2.2 * a * np.sin(2 * np.pi * 13 * t)
    if kind == 'pop':    # lean in and punch
        u = ease(t / 0.18) - ease((t - 0.5) / 0.4); return 0, 0, 1 + 0.12 * u, 1 + 0.12 * u, -4 * u
    return 0, 0, 1, 1, 0


def draw(bg, lay, kind, t):
    if lay is None: return bg
    dx, dy, sx, sy, rot = pose(kind, t, lay['h'])
    px, py = lay['pivot']
    c, s = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    A = np.array([[c * sx, -s * sy, 0], [s * sx, c * sy, 0]], dtype='float32')
    A[:, 2] = np.array([px, py]) - A[:, :2] @ np.array([px, py]) + np.array([dx, dy])
    rgb = cv2.warpAffine(lay['rgb'], A, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    a = cv2.warpAffine(lay['a'], A, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    return bg * (1 - a[..., None]) + rgb


def render(frame, mask, out_mp4):
    L, R = split_two(mask)
    bg = plate(frame, mask).astype('float32')
    lays = [layer(frame, L), layer(frame, R)]
    seq = [(0, 'talk'), (0, 'jump'), (0, 'shake'), (0, 'pop'), (1, 'talk'), (1, 'jump'), (1, 'shake'), (1, 'pop')]
    dur = {'talk': 1.4, 'jump': 1.1, 'shake': 1.2, 'pop': 0.9}
    tmp = Path(out_mp4).with_suffix('.raw.mp4')
    vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*'mp4v'), FPS, (W, H))
    for who, kind in seq:
        for i in range(int(dur[kind] * FPS)):
            t = i / FPS; img = bg.copy()
            for k in (0, 1):   # the other character stays still; the actor moves
                img = draw(img, lays[k], kind if k == who else 'still', t)
            vw.write(np.clip(img, 0, 255).astype('uint8'))
    vw.release()
    sh('ffmpeg', '-v', 'error', '-y', '-i', tmp, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out_mp4); tmp.unlink()


def preview(frame, mask, p):
    g = np.full_like(frame, 128); a = (mask.astype('float32') / 255.0)[..., None]
    cv2.imwrite(str(p), np.hstack([frame, (frame * a + g * (1 - a)).astype('uint8')]))


def main():
    video, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    fr = frames(video, out); rep = []
    best = None
    for model in ('isnet-anime', 'birefnet-general-lite', 'u2net'):
        try:
            t0 = time.time(); masks = []
            for i, p in enumerate(fr):
                f = cv2.imread(str(p)); m = clean(rembg_mask(p, model)); masks.append(m); preview(f, m, out / f'cutout_{model}_{i}.png')
            dt = time.time() - t0
            cov = [round(100 * float((m > 0).mean()), 1) for m in masks]
            rep.append('%s: ok, %.1fs for 3 frames, character area %% of frame %s' % (model, dt, cov))
            if best is None: best = (model, fr[1], masks[1])
        except Exception as e:
            rep.append('%s: FAILED %s' % (model, str(e)[:150]))
    if best:
        model, p, m = best
        render(cv2.imread(str(p)), m, out / 'demo_only_character_moves.mp4'); rep.append('demo rendered with model ' + model)
    (out / 'report.txt').write_text('\n'.join(rep)); print('\n'.join(rep))


if __name__ == '__main__':
    main()
