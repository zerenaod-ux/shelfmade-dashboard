import unittest, numpy as np
from doodles_engine import eyes

def face():
    img = np.full((300, 400, 3), (222, 160, 140), 'uint8')
    for cx in (150, 250):
        yy, xx = np.mgrid[0:300, 0:400]
        img[((xx - cx) / 28.0) ** 2 + ((yy - 140) / 20.0) ** 2 <= 1] = (250, 250, 250)
        img[((xx - cx) ** 2 + (yy - 140) ** 2) <= 81] = (20, 20, 20)
    return img

class BothEyesBlink(unittest.TestCase):
    def test_second_eye_gets_lid_when_not_measurable(self):
        img = face(); orig = eyes._eye_mask; calls = {'n': 0}
        def fake(rgb, E, x0, y0, x1, y1):
            calls['n'] += 1
            return orig(rgb, E, x0, y0, x1, y1) if calls['n'] == 1 else None
        eyes._eye_mask = fake
        try:
            g = eyes.geom(img, {'eyes': ((150, 140), (250, 140))})
        finally:
            eyes._eye_mask = orig
        if g[0]['mask'] is None and g[1]['mask'] is None:
            self.skipTest('synthetic eye not measurable on this OpenCV build')
        self.assertTrue(all(E['mask'] is not None for E in g))
        out = eyes.apply(img.copy(), g, 1.0, (0, 0))
        for cx in (150, 250):
            self.assertGreater(int(np.abs(out[130:150, cx - 20:cx + 20].astype(int) - img[130:150, cx - 20:cx + 20].astype(int)).sum()), 500, 'eye at %d did not blink' % cx)

if __name__ == '__main__':
    unittest.main()
