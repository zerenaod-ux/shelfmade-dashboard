"""Scene test: builds the sound track (river noise + stone thuds, all generated) and joins it with the rendered frames. Free tools only."""
import shutil, subprocess, wave
import numpy as np

sr = 44100; T = 30.0; n = int(sr * T); t = np.arange(n) / sr
rs = np.random.RandomState(4)
def band(noise, lo, hi):
    F = np.fft.rfft(noise); f = np.fft.rfftfreq(len(noise), 1 / sr); F[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(F, len(noise))
river = band(rs.randn(n), 250, 3800); river /= np.abs(river).max()
env = np.interp(t, [0, 4, 13, 15, 18, 24.5, 26, 30], [0.55, 0.55, 0.6, 0.5, 0.22, 0.22, 0.8, 0.75])
wob = 1 + 0.15 * np.sin(2 * np.pi * 0.7 * t) + 0.1 * np.sin(2 * np.pi * 1.9 * t + 1)
out = 0.20 * river * env * wob
low = band(rs.randn(n), 60, 220); low /= np.abs(low).max(); out += 0.10 * low * np.interp(t, [0, 24.5, 26.5, 30], [0.2, 0.2, 1, 0.9])
for L in [4.9, 5.6, 6.3, 7.0, 9.3, 9.9, 10.5, 11.3, 11.9, 12.8]:
    i = int(L * sr); m = int(0.45 * sr); tt = np.arange(m) / sr
    thud = np.sin(2 * np.pi * (95 * np.exp(-tt * 9) + 45) * tt) * np.exp(-tt * 11)
    sp = band(rs.randn(m), 900, 6000); sp /= np.abs(sp).max(); sp *= np.exp(-tt * 7) * np.minimum(1, tt * 60)
    out[i:i + m] += 0.55 * thud + 0.16 * sp
out *= np.minimum(1, np.minimum(t / 0.4, (T - t) / 0.8)); out = np.tanh(out * 1.4) / 1.4
w = wave.open('audio.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((out * 32000).astype(np.int16).tobytes()); w.close()

ff = shutil.which('ffmpeg')
if not ff:
    import imageio_ffmpeg; ff = imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ff, '-v', 'error', '-y', '-framerate', '30', '-i', 'fr/%04d.jpg', '-i', 'audio.wav', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', 'river-dam-scene.mp4'], check=True)
print('DONE river-dam-scene.mp4')
