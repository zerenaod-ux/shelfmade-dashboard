"""MUSIC STUDIO: generates a large library of ORIGINAL instrumental background tracks (no samples, no licences, no attribution).
Usage: python3 music_studio.py <out_dir> [count_per_style]   -> <out_dir>/<id>.mp3 + <out_dir>/index.json
Each track has metadata the director uses: mood, bpm, energy (0-1), density (0-1 busyness), brands, style.
Needs numpy + ffmpeg."""
import numpy as np, subprocess, json, sys, hashlib
from pathlib import Path
SR = 32000
def hz(n): return 440 * 2 ** ((n - 69) / 12)

# ---------- instruments (all return mono float arrays) ----------
def _env(n, a=0.005, d=1.0):
    t = np.arange(n) / SR; e = np.exp(-t / d); ai = max(1, int(a * SR)); e[:ai] *= np.linspace(0, 1, ai); return e
def pluck(m, dur=1.2, bright=0.5):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m); s = np.zeros(n)
    for h, a in ((1, 1), (2, .5 * bright + .1), (3, .3 * bright), (4, .15 * bright), (5, .08 * bright)): s += a * np.sin(2 * np.pi * f * h * t) * np.exp(-t * (2 + h * 1.5))
    return s * _env(n, .003, dur / 3)
def marimba(m, dur=.6):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    return (np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 25)) * _env(n, .002, dur / 5)
def bell(m, dur=3.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * t) + .4 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 3) + .2 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 5)
    return s * np.exp(-t * 1.6) * np.minimum(1, t * 200)
def epiano(m, dur=1.6):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 2) + .15 * np.sin(2 * np.pi * 7 * f * t) * np.exp(-t * 14)
    return s * _env(n, .004, dur / 2.5)
def pad(notes, dur, bright, rng, vib=True):
    n = int(dur * SR); t = np.arange(n) / SR; out = np.zeros(n)
    for m in notes:
        f = hz(m)
        for d in (-.004, .004, .002):
            sig = np.zeros(n)
            for h in range(1, 6): sig += np.sin(2 * np.pi * f * (1 + d) * h * t + rng.random() * 6.28) / (h ** (1 + 2 * (1 - bright)))
            out += sig * (1 + (.12 * np.sin(2 * np.pi * (.1 + rng.random() * .1) * t) if vib else 0))
    a = min(dur * .35, 3.0); r = min(dur * .45, 3.5); e = np.ones(n); ai = int(a * SR); ri = int(r * SR); e[:ai] = np.linspace(0, 1, ai) ** 2; e[n - ri:] = np.linspace(1, 0, ri) ** 2
    return out * e / (len(notes) * 3)
def sub(m, dur, vol=.16):
    n = int(dur * SR); t = np.arange(n) / SR; return np.sin(2 * np.pi * hz(m) * t) * _env(n, .01, dur * .6) * vol
def bassnote(m, dur=.4):
    n = int(dur * SR); t = np.arange(n) / SR; f = hz(m)
    return (np.sin(2 * np.pi * f * t) + .3 * np.sin(2 * np.pi * 2 * f * t)) * _env(n, .004, dur / 2) * .5
def kick(vol=1.0):
    n = int(.22 * SR); t = np.arange(n) / SR; f = 110 * np.exp(-t * 28) + 45; ph = 2 * np.pi * np.cumsum(f) / SR; return np.sin(ph) * np.exp(-t * 16) * vol
def hat(rng, vol=.35, open_=False):
    n = int((.25 if open_ else .05) * SR); x = rng.standard_normal(n); x = np.diff(x, prepend=0); return x * np.exp(-np.arange(n) / SR * (14 if open_ else 80)) * vol * .6
def snare(rng, vol=.5):
    n = int(.18 * SR); t = np.arange(n) / SR; return (rng.standard_normal(n) * .6 + np.sin(2 * np.pi * 190 * t) * .5) * np.exp(-t * 22) * vol
def shaker(rng, vol=.25):
    n = int(.08 * SR); x = np.diff(rng.standard_normal(n), prepend=0); return x * np.exp(-np.arange(n) / SR * 45) * vol * .5

def reverb(x, sec=2.4, wet=.3, seed=1):
    r = np.random.default_rng(seed); n = int(SR * sec); t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-t * 2.4) / (n ** .5) * 40
    L = len(x) + n; F = 1 << (L - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, F) * np.fft.rfft(ir, F), F)[:len(x)]
    return x * (1 - wet) + y * wet

def put(buf, ev, at, vol=1.0):
    s = int(at * SR)
    if s >= len(buf): return
    seg = ev[:len(buf) - s]; buf[s:s + len(seg)] += seg * vol

# ---------- harmony ----------
CH = {'maj': (0, 4, 7), 'min': (0, 3, 7), 'maj7': (0, 4, 7, 11), 'min7': (0, 3, 7, 10), 'dom7': (0, 4, 7, 10), 'sus2': (0, 2, 7), 'add9': (0, 4, 7, 14), 'dim': (0, 3, 6)}
# progressions: list of (semitone offset from root, quality)
PROG = {
 'minor_sad':   [(0, 'min7'), (8, 'maj7'), (3, 'maj'), (10, 'dom7')],
 'minor_dark':  [(0, 'min'), (1, 'maj'), (0, 'min'), (10, 'maj')],
 'minor_drift': [(0, 'min7'), (5, 'min7'), (8, 'maj7'), (7, 'dom7')],
 'major_warm':  [(0, 'maj7'), (7, 'maj'), (9, 'min7'), (5, 'maj7')],
 'major_bright':[(0, 'maj'), (5, 'maj'), (7, 'maj'), (5, 'maj')],
 'major_soft':  [(0, 'add9'), (9, 'min7'), (5, 'maj7'), (7, 'sus2')],
 'quirky':      [(0, 'maj'), (3, 'maj'), (5, 'maj'), (7, 'dom7')],
 'sneak':       [(0, 'min'), (0, 'dim'), (5, 'min'), (7, 'dom7')],
 'wonder':      [(0, 'maj7'), (2, 'maj'), (9, 'min7'), (4, 'min7')],
}
SCALES = {'maj': (0, 2, 4, 7, 9), 'min': (0, 3, 5, 7, 10), 'dor': (0, 2, 3, 7, 9), 'lyd': (0, 2, 4, 6, 7, 9)}

# ---------- style recipes ----------
# engine: ambient | piano | lofi | pulse | bounce | quirky | sneak | drone
STYLES = {
 # --- ShelfMade (classic books): warm, literary, slow ---
 'sm_candle':   dict(brands=['shelfmade'], engine='piano',   prog=['major_warm', 'major_soft', 'minor_drift'], bpm=(58, 74), mood='warm', energy=.20, dens=.30, bright=.4),
 'sm_library':  dict(brands=['shelfmade'], engine='ambient', prog=['major_soft', 'minor_drift', 'major_warm'], bpm=(50, 62), mood='reflective', energy=.12, dens=.18, bright=.35),
 'sm_gothic':   dict(brands=['shelfmade'], engine='drone',   prog=['minor_dark', 'minor_sad'], bpm=(48, 60), mood='dramatic', energy=.30, dens=.22, bright=.25),
 'sm_adventure':dict(brands=['shelfmade'], engine='piano',   prog=['major_bright', 'wonder'], bpm=(84, 104), mood='curious', energy=.45, dens=.50, bright=.55),
 'sm_tender':   dict(brands=['shelfmade'], engine='piano',   prog=['minor_sad', 'major_soft'], bpm=(56, 68), mood='reflective', energy=.18, dens=.26, bright=.35),
 # --- MindLore (psychology): modern, thoughtful, a bit of beat ---
 'ml_lofi':     dict(brands=['mindlore'], engine='lofi',     prog=['minor_drift', 'major_warm', 'minor_sad'], bpm=(70, 86), mood='calm', energy=.38, dens=.45, bright=.4),
 'ml_pulse':    dict(brands=['mindlore'], engine='pulse',    prog=['minor_drift', 'wonder', 'minor_dark'], bpm=(92, 112), mood='curious', energy=.55, dens=.55, bright=.5),
 'ml_deep':     dict(brands=['mindlore'], engine='drone',    prog=['minor_dark', 'minor_drift'], bpm=(60, 76), mood='mysterious', energy=.28, dens=.2, bright=.3),
 'ml_wonder':   dict(brands=['mindlore'], engine='ambient',  prog=['wonder', 'major_soft'], bpm=(60, 74), mood='curious', energy=.22, dens=.3, bright=.55),
 'ml_tension':  dict(brands=['mindlore'], engine='pulse',    prog=['minor_dark', 'sneak'], bpm=(100, 120), mood='dramatic', energy=.65, dens=.5, bright=.35),
 # --- AnimationDoodles (comedy): bouncy, playful ---
 'dd_bounce':   dict(brands=['doodles'], engine='bounce',    prog=['major_bright', 'quirky'], bpm=(108, 126), mood='playful', energy=.75, dens=.65, bright=.6),
 'dd_quirky':   dict(brands=['doodles'], engine='quirky',    prog=['quirky', 'major_bright'], bpm=(96, 116), mood='playful', energy=.60, dens=.60, bright=.6),
 'dd_sneak':    dict(brands=['doodles'], engine='sneak',     prog=['sneak'], bpm=(88, 104), mood='sneaky', energy=.50, dens=.40, bright=.4),
 'dd_chill':    dict(brands=['doodles'], engine='lofi',      prog=['major_warm', 'major_soft'], bpm=(76, 90), mood='warm', energy=.38, dens=.42, bright=.5),
 'dd_hype':     dict(brands=['doodles'], engine='bounce',    prog=['major_bright', 'wonder'], bpm=(124, 138), mood='upbeat', energy=.90, dens=.75, bright=.65),
}

def chord_notes(root, off, q, octave_shift=0):
    return [root + off + i + octave_shift for i in CH[q]]

def render(style, seed, loop=80.0):
    S = STYLES[style]; rng = np.random.default_rng(seed)
    bpm = int(rng.integers(S['bpm'][0], S['bpm'][1] + 1)); beat = 60 / bpm
    root = int(rng.choice([45, 46, 47, 48, 50, 52, 53, 55])); prog = PROG[str(rng.choice(S['prog']))]
    minor = prog[0][1] in ('min', 'min7') or S['mood'] in ('mysterious', 'sneaky')
    scale = SCALES['min' if minor else str(rng.choice(['maj', 'lyd', 'dor'] if S['engine'] != 'quirky' else ['maj']))]
    bars = max(4, int(loop / (beat * 4))); loop = bars * beat * 4
    N = int(loop * SR); tail = int(4 * SR); buf = np.zeros(N + tail); bass = np.zeros(N + tail); drums = np.zeros(N + tail); mel = np.zeros(N + tail)
    eng = S['engine']; bright = S['bright']
    for bar in range(bars):
        off, q = prog[(bar // (2 if eng in ('ambient', 'drone') else 1)) % len(prog)]
        notes = chord_notes(root + 12, off, q); t0 = bar * beat * 4
        if eng in ('ambient', 'drone'):
            if bar % 2 == 0:
                p = pad(notes[:4], beat * 8 + 3, bright, rng); put(buf, p, t0, .7)
                put(bass, sub(root + off - 12, beat * 8 + 2, .2 if eng == 'drone' else .12), t0)
            if eng == 'ambient' or rng.random() < .35:
                for _ in range(int(2 + 2 * S['dens'] * 3)): put(mel, bell(root + 24 + int(rng.choice(scale)) + 12 * int(rng.integers(0, 2)), 3), t0 + rng.random() * beat * 4, float(rng.uniform(.15, .35)))
        elif eng == 'piano':
            pat = [0, 1, 2, 3, 2, 1, 2, 3] if S['dens'] < .4 else [0, 2, 1, 3, 0, 2, 1, 3]
            step = beat / 2 if S['dens'] > .25 else beat
            for i in range(int(4 * beat / step)):
                nt = notes[pat[i % len(pat)] % len(notes)]
                put(buf, pluck(nt + (12 if i % 4 == 3 and rng.random() < .3 else 0), 1.6, bright), t0 + i * step, .5)
            put(bass, sub(root + off - 12, beat * 3.8, .14), t0)
            if bar % 2 == 1 and rng.random() < .6: put(mel, pluck(root + 24 + int(rng.choice(scale)), 1.5, bright), t0 + beat * float(rng.choice([1, 2, 3])), .35)
        elif eng == 'lofi':
            swing = .06 * beat
            for i, st in enumerate((0, 1.5, 2, 3.5)): put(buf, epiano(notes[i % len(notes)] + 0, 1.8), t0 + st * beat + (swing if i % 2 else 0), .35)
            for nt in notes[:3]: put(buf, epiano(nt, 2.2), t0, .22)
            put(bass, bassnote(root + off - 12, beat * 1.4), t0, .55); put(bass, bassnote(root + off - 12 + (7 if rng.random() < .5 else 0), beat), t0 + beat * 2.5, .45)
            for b in range(4):
                if b in (0, 2) and (b == 0 or rng.random() < .8): put(drums, kick(.6), t0 + b * beat)
                if b in (1, 3): put(drums, snare(rng, .28), t0 + b * beat + (swing if b == 3 else 0))
            for e in range(8): put(drums, hat(rng, .2 + .1 * (e % 2)), t0 + e * beat / 2 + (swing if e % 2 else 0))
            if rng.random() < .55: put(mel, epiano(root + 24 + int(rng.choice(scale)), 1.4), t0 + beat * float(rng.choice([0.5, 1.5, 2.5, 3])), .3)
        elif eng == 'pulse':
            arp = notes + [notes[0] + 12]
            for i in range(16): put(buf, pluck(arp[(i * (3 if bar % 2 else 1)) % len(arp)] + 12, .35, bright), t0 + i * beat / 4, .26 if i % 4 else .38)
            put(bass, bassnote(root + off - 12, beat * .9), t0, .6); put(bass, bassnote(root + off - 12, beat * .9), t0 + beat * 2, .5)
            for b in range(4):
                if b % 2 == 0: put(drums, kick(.55), t0 + b * beat)
                else: put(drums, snare(rng, .22), t0 + b * beat)
            for e in range(8): put(drums, hat(rng, .16), t0 + e * beat / 2)
            if bar % 4 == 3: put(mel, bell(root + 24 + int(rng.choice(scale)), 2.5), t0 + beat * 2, .3)
        elif eng in ('bounce', 'quirky'):
            for i in range(8):
                if eng == 'bounce' or rng.random() < .75:
                    nt = notes[int(rng.integers(0, len(notes)))] + (12 if rng.random() < .4 else 0)
                    put(mel, marimba(nt + 12, .45), t0 + i * beat / 2, .30)
            for b in range(4):
                put(bass, bassnote(root + off - 12 + (0 if b % 2 == 0 else 7), beat * .8), t0 + b * beat, .6)
                if b % 2 == 0 and eng == 'bounce': put(drums, kick(.6), t0 + b * beat)
                if b % 2 == 1: put(drums, snare(rng, .3 if eng == 'bounce' else .18), t0 + b * beat)
            for e in range(8): put(drums, shaker(rng, .22) if eng == 'quirky' else hat(rng, .22), t0 + e * beat / 2)
            for nt in notes[:3]: put(buf, pluck(nt + 12, .25, .7), t0 + beat * 1.5, .25); put(buf, pluck(nt + 12, .25, .7), t0 + beat * 3.5, .25)
        elif eng == 'sneak':
            for b in range(4):
                put(bass, bassnote(root + off - 12, beat * .5), t0 + b * beat, .6)
                put(mel, pluck(notes[(b * 2) % len(notes)] + 12, .3, .3), t0 + b * beat + beat / 2, .35)
            if bar % 2 == 1:
                for k in range(3): put(mel, marimba(notes[k] + 24, .3), t0 + beat * (2 + k * .5), .25)
            for b in (1, 3): put(drums, shaker(rng, .3), t0 + b * beat)
            put(drums, kick(.35), t0)
    mix = buf + bass + drums * .85 + mel
    mix = reverb(mix, 2.6 if eng in ('ambient', 'drone', 'piano') else 1.2, .38 if eng in ('ambient', 'drone', 'piano') else .16, int(seed))
    mix[:tail] += mix[N:N + tail]; mix = mix[:N]
    st = np.stack([mix, np.roll(mix, int(.012 * SR))]) if eng not in ('bounce', 'pulse') else np.stack([mix, mix * .98])
    st = st - st.mean(axis=1, keepdims=True); st /= (np.max(np.abs(st)) * 1.1 + 1e-9)
    return st, bpm, loop

def to_mp3(st, path, tmp):
    (st.T.astype(np.float32)).tofile(tmp)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', str(tmp), '-af', 'highpass=f=35,lowpass=f=12000,loudnorm=I=-20:TP=-2:LRA=7', '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '96k', str(path)], check=True)

def main(out, per=4, only=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); idx = []
    for style, S in STYLES.items():
        if only and not style.startswith(only): continue
        for k in range(per):
            seed = int(hashlib.md5(f'{style}{k}'.encode()).hexdigest()[:8], 16); tid = f'{style}_{k + 1:02d}'
            st, bpm, loop = render(style, seed); to_mp3(st, out / (tid + '.mp3'), out / (tid + '.f32'))
            (out / (tid + '.f32')).unlink(missing_ok=True)
            idx.append(dict(id=tid, file=tid + '.mp3', style=style, brands=S['brands'], mood=S['mood'], bpm=bpm, energy=S['energy'], density=S['dens'], dur=round(loop, 1), source='synth'))
            print('made', tid, bpm, 'bpm', flush=True)
    (out / 'index.json').write_text(json.dumps(idx, indent=1))
    return idx
if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4, sys.argv[3] if len(sys.argv) > 3 else None)
