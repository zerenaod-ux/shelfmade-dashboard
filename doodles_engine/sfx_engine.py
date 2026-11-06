"""Sound design for AnimationDoodles: NO music. Real action sounds (typing, phone ping, door knock, footsteps, clock tick, mug, blanket, sigh...) placed from
(1) explicit per-shot cues  shot['sfx'] = [{'cue': 'phone_typing', 'at': 0.4, 'gain': 1.0}]  (the story writer may add these), else
(2) cues recognized in the shot's scene description (keywords), plus a sigh after a 'tired' line.
Rules that keep it tasteful: at most 2 cues per shot, each cue type waits 2+ shots before repeating, a quiet clock tick bed only while a clock is in the scene,
and every sound is ducked under the voices. Returns the voice track with the sounds mixed in. Off with DOODLES_SFX=0."""
import zlib
import numpy as np
import sfx_synth as S

TARGET = 0.050     # loudness (rms) of a normal cue next to speech rms of about 0.10-0.12
REL = {'phone_typing': 1.0, 'laptop_typing': 1.0, 'ping': 0.8, 'phone_buzz': 0.7, 'swoosh': 0.8, 'door_knock': 1.1, 'footsteps': 1.0, 'mug': 0.9,
       'blanket': 1.0, 'sigh': 0.9, 'alarm': 0.55, 'heartbeat': 0.9, 'boing': 0.8, 'pop': 0.8}
KEYS = [  # cue, words in the scene text that call for it (first match wins per cue type)
    ('door_knock', ('knock',)),
    ('phone_typing', ('typing', 'texting', 'types ', 'scrolling', 'thumbs')),
    ('laptop_typing', ('laptop', 'keyboard')),
    ('ping', ('notification', 'phone buzz', 'message arrives', 'text message')),
    ('footsteps', ('walks', 'walking', 'pacing', 'steps', 'stroll', 'hallway')),
    ('mug', (' mug', 'coffee', ' tea ', ' cup')),
    ('blanket', ('blanket', 'pillow', 'duvet', 'under the covers', 'in bed', 'bed,')),
    ('alarm', ('alarm',)),
]
COOLDOWN = 2   # shots before the same cue type may repeat
MAXCUES = 2


def _loud(x, rel):
    act = x[np.abs(x) > 0.05 * (np.max(np.abs(x)) + 1e-9)]
    r = float(np.sqrt(np.mean(act ** 2))) if len(act) else 1.0
    return x * (TARGET * rel / (r + 1e-9))


def plan(st, timeline):
    """-> list of {'t','cue','gain','dur'} in seconds on the video timeline."""
    ev, last = [], {}
    shots = st.get('shots', [])
    for si, (sh, tl) in enumerate(zip(shots, timeline)):
        s0, s1 = tl['start'], tl['end']
        used = 0
        ex = sh.get('sfx')
        if ex:
            for c in ex:
                if c.get('cue') in S.CUES and used < MAXCUES:
                    ev.append({'t': s0 + float(c.get('at', 0.2)), 'cue': c['cue'], 'gain': float(c.get('gain', 1.0))}); used += 1
        else:
            txt = ' ' + (sh.get('scene', '') or '').lower() + ' '
            for cue, words in KEYS:
                if used >= MAXCUES: break
                if any(w in txt for w in words) and si - last.get(cue, -99) > COOLDOWN:
                    ev.append({'t': s0 + 0.15 + 0.2 * used, 'cue': cue, 'gain': 1.0}); last[cue] = si; used += 1
            if used < MAXCUES and any(l.get('feel') == 'tired' for l in sh.get('lines', [])) and si - last.get('sigh', -99) > COOLDOWN:
                ln = [l for l in tl['lines']][0]
                ev.append({'t': ln['start'] - 0.55 if ln['start'] - 0.55 > s0 - 0.2 else s0 + 0.02, 'cue': 'sigh', 'gain': 1.0}); last['sigh'] = si
    return ev


def clock_spans(st, timeline):
    sp, cur = [], None
    for sh, tl in zip(st.get('shots', []), timeline):
        has = 'clock' in (sh.get('scene', '') or '').lower()
        if has and cur is None: cur = [tl['start'], tl['end']]
        elif has: cur[1] = tl['end']
        elif cur is not None: sp.append(tuple(cur)); cur = None
    if cur is not None: sp.append(tuple(cur))
    return sp


def mix(track, st, timeline, sr, total):
    """Returns (new_track, events). Never raises: on any problem the untouched voice track comes back."""
    try:
        assert sr == S.SR, 'sample rate'
        n = len(track); sfx = np.zeros(n, dtype='float32'); ev = plan(st, timeline)
        for e in ev:
            S.seed(zlib.crc32(('%s%.2f' % (e['cue'], e['t'])).encode()))
            x = _loud(S.make(e['cue']), REL.get(e['cue'], 1.0)) * e['gain']
            e['dur'] = round(len(x) / sr, 2)
            i = int(max(0.0, e['t']) * sr); j = min(n, i + len(x))
            if i < n: sfx[i:j] += x[:j - i].astype('float32')
        for a, b in clock_spans(st, timeline):
            S.seed(5); x = _loud(S.tick_loop(max(0.6, b - a)), 0.45)
            i = int(a * sr); j = min(n, i + len(x)); fade = np.minimum(1, np.minimum(np.arange(j - i) / (0.2 * sr), (j - i - np.arange(j - i)) / (0.2 * sr)))
            sfx[i:j] += (x[:j - i] * fade).astype('float32'); ev.append({'t': round(a, 2), 'cue': 'clock_tick_bed', 'gain': 0.45, 'dur': round(b - a, 2)})
        # duck the sounds under the voices
        w = int(0.04 * sr); env = np.convolve(np.abs(track), np.ones(w) / w, mode='same')
        ref = float(np.percentile(env[env > 0.01], 90)) if (env > 0.01).any() else 1.0
        duck = 1 - 0.65 * np.clip(env / ref, 0, 1); duck = np.convolve(duck, np.ones(int(0.06 * sr)) / int(0.06 * sr), mode='same')
        out = track + sfx * duck.astype('float32')
        pk = float(np.max(np.abs(out)))
        if pk > 0.97: out = out * (0.97 / pk)
        return out.astype('float32'), ev
    except Exception as ex:  # noqa
        print('sfx skipped:', str(ex)[:120], flush=True)
        return track, []
