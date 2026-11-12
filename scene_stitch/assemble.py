"""Stitches scene test: natural voice (free edge-tts, same voice code as the Shorts) + soft generated background, joined with the rendered frames."""
import json, os, shutil, subprocess, sys, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ff = shutil.which('ffmpeg')
if not ff:  # no system ffmpeg: use the pip copy and put it on PATH (the voice code calls "ffmpeg")
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe(); b = Path('bin'); b.mkdir(exist_ok=True)
    if not (b / 'ffmpeg').exists(): os.symlink(ff, b / 'ffmpeg')
    os.environ['PATH'] = str(b.resolve()) + os.pathsep + os.environ['PATH']
import local_voice

T = 33.5; SR = 44100
LINES = [(0.3, 4.2, 'A deep cut splits your skin wide open.'),
         (4.4, 8.6, 'The edges are too far apart to heal by themselves.'),
         (8.8, 13.8, 'So a curved needle carries a thread down one side, and up the other.'),
         (14.0, 18.6, 'Pull it tight, tie a knot, and the edges press together.'),
         (18.8, 22.6, 'Stitch by stitch, the wound is held shut.'),
         (22.8, 27.8, 'Now your body builds new tissue across the gap.'),
         (28.0, 33.3, 'After a week or two, the stitches come out.')]
os.environ.setdefault('CE_EDGE_RATE', '+6%')
jobs = [{'text': tx, 'wav': 'v%d.wav' % i, 'timing': 't%d.json' % i} for i, (a, b, tx) in enumerate(LINES)]
local_voice.edge_run(jobs)

def read(path):
    with wave.open(path) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    n = int(len(x) * SR / sr); return np.interp(np.arange(n) * sr / SR, np.arange(len(x)), x)

n = int(T * SR); t = np.arange(n) / SR; voice = np.zeros(n); log = []
for i, (a, b, tx) in enumerate(LINES):
    dur = json.loads(Path('t%d.json' % i).read_text())['duration']; room = b - a - 0.15; src = 'v%d.wav' % i
    if dur > room:  # speak a little faster so the line fits its part of the video
        k = min(1.35, dur / room); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter:a', 'atempo=%.3f' % k, 'f%d.wav' % i], check=True); src = 'f%d.wav' % i
    x = read(src); i0 = int((a + 0.1) * SR); x = x[:n - i0]; voice[i0:i0 + len(x)] += x
    log.append('line %d: %.2fs spoken, %.2fs room%s' % (i + 1, dur, room, ' (sped up)' if dur > room else ''))
# soft background: two slow notes + gentle air, kept low under the voice
pad = 0.035 * (np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t)) + 0.7 * np.sin(2 * np.pi * 329.6 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t + 1)) + 0.5 * np.sin(2 * np.pi * 164.8 * t))
rs = np.random.RandomState(3); air = rs.randn(n); F = np.fft.rfft(air); f = np.fft.rfftfreq(n, 1 / SR); F[(f < 300) | (f > 2500)] = 0; air = np.fft.irfft(F, n); air /= np.abs(air).max()
out = voice * 0.95 + pad + 0.012 * air
for tk in [1.6, 15.9, 18.75, 19.9, 21.05, 22.2, 28.7, 29.32, 29.94, 30.56, 31.18]:  # small soft ticks on the cut, knots and snips
    i0 = int(tk * SR); m = int(0.12 * SR); tt = np.arange(m) / SR; out[i0:i0 + m] += 0.10 * np.sin(2 * np.pi * 880 * tt) * np.exp(-tt * 40)
out *= np.minimum(1, np.minimum(t / 0.3, (T - t) / 0.6)); out = np.tanh(out * 1.2) / 1.2
with wave.open('audio.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32000).astype(np.int16).tobytes())
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '30', '-i', 'fr/%04d.jpg', '-i', 'audio.wav', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', 'stitches-scene.mp4'], check=True)
Path('voice-log.txt').write_text('\n'.join(log) + '\n'); print('\n'.join(log)); print('DONE stitches-scene.mp4')
