"""Free synthetic sound for whiteboard videos (numpy only): pencil scratch while the pen draws, a soft tick when a picture finishes,
and a quiet slow chord pad underneath. mix(narration_wav, events, duration, out_wav) -> out_wav (24 kHz mono)."""
import wave, subprocess, numpy as np
from pathlib import Path

SR = 24000


def _scratch(n, rng):
    x = rng.standard_normal(n); x = np.diff(x, prepend=0.0); x = np.diff(x, prepend=0.0)   # bright noise
    t = np.arange(n) / SR
    mod = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * (9 + 5 * rng.random()) * t + rng.random() * 6))
    return x * mod / 4.0


def build(events, duration, out_wav, seed=7):
    rng = np.random.default_rng(seed); n = int((duration + 1) * SR); y = np.zeros(n, np.float32)
    for st, du, kind in events:
        i0, ln = int(st * SR), int(max(0.2, du) * SR)
        if i0 >= n: continue
        ln = min(ln, n - i0); seg = _scratch(ln, rng).astype(np.float32)
        a = np.minimum(1.0, np.minimum(np.arange(ln) / (0.04 * SR), (ln - np.arange(ln)) / (0.06 * SR)))
        y[i0:i0 + ln] += seg * a * (0.5 if kind in ('arrow', 'cross') else 0.42)
        te = np.arange(int(0.12 * SR)) / SR; tick = np.sin(2 * np.pi * 1040 * te) * np.exp(-te * 38) * 0.10
        j = min(n, i0 + ln); y[j:j + len(tick)] += tick[:max(0, min(len(tick), n - j))]
    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]; seg_s = 7.0; t = np.arange(n) / SR; pad = np.zeros(n, np.float32)
    for k in range(int(duration / seg_s) + 2):
        a0, a1 = int(k * seg_s * SR), min(n, int((k + 1) * seg_s * SR + 2 * SR))
        if a0 >= n: break
        tt = t[a0:a1] - k * seg_s; env = np.minimum(1, tt / 2.0) * np.clip((seg_s + 2 - tt) / 2.0, 0, 1)
        for m in chords[k % 4]:
            f = 440 * 2 ** ((m - 69) / 12); pad[a0:a1] += (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.004 * tt)) * env * 0.018
    y += pad
    y = np.clip(y, -0.9, 0.9)
    with wave.open(str(out_wav), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype('<i2').tobytes())
    return out_wav


def mix(narration, events, duration, out_wav):
    out_wav = Path(out_wav); fx = out_wav.with_name('sfx.wav'); build(events, duration, fx)
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(narration), '-i', str(fx), '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=longest:normalize=0[a]', '-map', '[a]', '-ar', str(SR), '-ac', '1', str(out_wav)], capture_output=True, text=True)
    if r.returncode: raise RuntimeError('sound mix failed: ' + r.stderr[-300:])
    return out_wav
