"""Stitches scene: energetic narrator + loud sound effects that match each action + light music bed, joined with the rendered frames. Uses scene_lib."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scene_lib import audio as A

T = 33.5
LINES = [(0.3, 4.2, 'A deep cut splits your skin wide open!'),
         (4.4, 8.6, 'The edges are too far apart to heal by themselves.'),
         (8.8, 13.8, 'So a curved needle dives in one side, and pops out the other!'),
         (14.0, 18.6, 'Pull it tight, tie a knot, and snap! The edges lock together.'),
         (18.8, 22.6, 'Stitch, by stitch, by stitch. The wound is sealed shut!'),
         (22.8, 27.8, 'Now your body goes to work, building new tissue across the gap.'),
         (28.0, 33.3, 'A week or two later, snip! The stitches come out.')]
voice, log = A.speak(LINES)
fx = A.Track(T)
fx.add(1.10, A.slice_(0.6), 1.0).add(1.62, A.whump(0.6), 1.0)                                   # the cut, then the skin gapes open
fx.add(9.9, A.tick(1300), 0.9).add(9.95, A.whoosh(1.6), 0.35).add(11.45, A.pop(), 1.0).add(12.1, A.zip_(1.2), 0.75)   # needle in, through, out, thread follows
fx.add(14.2, A.zip_(1.0, 400, 1900), 0.9).add(15.2, A.thunk(), 1.0).add(15.45, A.click(), 0.9).add(15.7, A.click(), 0.9)   # pull tight, edges meet, knot
for k in range(1, 5):                                                                            # four quick stitches
    a = 17.6 + (k - 1) * 1.15; fx.add(a + 0.12, A.tick(1300 + 120 * k), 0.85).add(a + 0.62, A.zip_(0.32, 500, 2000), 0.7).add(a + 0.98, A.click(), 0.9)
fx.add(23.0, A.sparkle(4.5), 0.55)
for d in range(10): fx.add(23.0 + d * 0.46, A.tick(700, 0.07), 0.45)                             # the day counter ticking
for k in range(5): fx.add(28.7 + k * 0.62, A.snip(), 1.0).add(28.78 + k * 0.62, A.whoosh(0.4), 0.4)   # snip and pull, five times
fx.add(32.0, A.chime(880, 1.2), 0.6).add(32.15, A.chime(1318.5, 1.2), 0.5)
out = A.mix(T, voice, fx.buf, A.music(T, bpm=118))
A.write_wav('audio.wav', out); A.mux('fr/%04d.jpg', 'audio.wav', 'stitches-scene.mp4')
Path('voice-log.txt').write_text('\n'.join(log) + '\n'); print('\n'.join(log)); print('DONE stitches-scene.mp4')
