"""MUSIC DIRECTOR: picks (and builds) the background-music bed for ONE video so that it fits the content, not the same loop every time.
Chooses from the library in data/music/index.json (tracks are downloaded on demand from the public GitHub release 'music-lib', cached in music/lib).
Matches: brand palette, story mood, speaking pace (words/second -> busy music under fast talking tires viewers), format (short/full).
Never raises: any problem returns None and the caller keeps the old single-track behaviour.
    bed = music_director.make_bed(brand, kind, text, total, out_path, mood=None, words=None, key='')
returns {'path':..., 'tracks':[ids], 'mood':..., 'pace':...} or None. The bed is already faded/trimmed to `total` seconds; caller just mixes it (ducking stays as before)."""
import json, os, random, hashlib, subprocess, urllib.request, re
from pathlib import Path
BASE = Path(__file__).resolve().parent
LIB = BASE / 'music' / 'lib'
REL = 'https://github.com/zerenaod-ux/shelfmade-dashboard/releases/download/music-lib/'
# story/engine mood words -> library moods
ALIAS = {'tense': 'dramatic', 'suspense': 'mysterious', 'hopeful': 'warm', 'sad': 'reflective', 'funny': 'playful', 'comic': 'playful', 'happy': 'upbeat',
         'sneaky': 'sneaky', 'excited': 'upbeat', 'serious': 'dramatic', 'wonder': 'curious', 'dark': 'mysterious', 'gentle': 'warm', 'neutral': 'calm'}
# which moods are acceptable substitutes (score 0.5)
NEAR = {'calm': {'warm', 'reflective'}, 'warm': {'calm', 'reflective', 'upbeat'}, 'reflective': {'calm', 'warm', 'mysterious'}, 'curious': {'mysterious', 'playful', 'calm'},
        'mysterious': {'curious', 'dramatic', 'reflective', 'sneaky'}, 'dramatic': {'mysterious', 'sneaky'}, 'playful': {'upbeat', 'sneaky', 'curious'},
        'upbeat': {'playful', 'warm'}, 'sneaky': {'mysterious', 'playful', 'dramatic'}}
MOODS = {
 'dramatic': r'\b(war|death|died|fear|danger|revolution|crowd|mob|panic|anger|rage|violence|tragedy|crisis|lost|abandon\w*|murder|blood|ghost|monster)\b',
 'mysterious': r'\b(dream\w*|sleep|unconscious|hidden|secret|mystery|strange|shadow|unknown|hypnosis|suggestion|illusion|trick\w*|bias|manipulat\w*)\b',
 'warm': r'\b(love|friend\w*|kindness|hope|joy|laugh\w*|happy|happiness|care|together|home|grateful|gratitude|family|tender)\b',
 'curious': r'\b(why|how|what|if|question\w*|wonder|puzzle|discover\w*|think\w*|mind|attention|habit\w*|learn\w*|brain|psycholog\w*)\b',
 'reflective': r'\b(memory|remember\w*|time|history|past|life|meaning|reflect\w*|essay|age|old|regret|grief|alone)\b',
 'playful': r'\b(lol|funny|joke|silly|ridiculous|awkward|hilarious|boss|coffee|nap|snack|argue|prank)\b',
}

def _index():
    try:
        return json.loads((BASE / 'data' / 'music' / 'index.json').read_text())
    except Exception:
        return []

def mood_for(text):
    t = (text or '').lower(); best = ('calm', 0)
    for m, p in MOODS.items():
        n = len(re.findall(p, t))
        if n > best[1]: best = (m, n)
    return best[0]

def _ensure(tr):
    p = LIB / tr['file']
    if p.is_file() and p.stat().st_size > 20000: return p
    LIB.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(REL + tr['file'], headers={'User-Agent': 'studio-music'})
        data = urllib.request.urlopen(req, timeout=60).read()
        if len(data) < 20000: return None
        p.write_bytes(data); return p
    except Exception as e:
        print('music download failed', tr['file'], e, flush=True); return None

def _targets(brand, kind, pace):
    """desired (energy, density) from format and speaking pace. Fast talking -> sparser music; slow narration -> more room for melody."""
    base_e = {'shelfmade': .22, 'mindlore': .42, 'doodles': .65}.get(brand, .35)
    if kind == 'short': base_e += .08
    p = pace or 2.5
    dens = max(.15, min(.8, .62 - (p - 2.0) * .2))
    en = max(.1, min(.95, base_e + (p - 2.5) * .12))
    return en, dens

def _bias(brand):
    for base in (Path('data/learned'), BASE / 'data' / 'learned'):
        try: return {k: v.get('bias', 0) for k, v in json.loads((base / ('music-%s.json' % brand)).read_text()).get('styles', {}).items()}
        except Exception: continue
    return {}

def pick(brand, kind='short', mood=None, text='', pace=None, key='', avoid=(), n=1):
    idx = _index()
    if not idx: return []
    mood = ALIAS.get(mood, mood) if mood else mood_for(text)
    en_t, de_t = _targets(brand, kind, pace)
    bias = _bias(brand)
    scored = []
    for t in idx:
        if t['id'] in avoid: continue
        s = 0.0
        s += 1.0 if t['mood'] == mood else (.45 if t['mood'] in NEAR.get(mood, ()) else 0)
        s += 1.0 if brand in t.get('brands', []) else -.8
        s -= 1.4 * abs(t['energy'] - en_t) + 1.0 * abs(t['density'] - de_t)
        s += bias.get(t['style'], 0)
        scored.append((s, t))
    scored.sort(key=lambda x: -x[0])
    pool = scored[:max(6, n * 4)]
    rng = random.Random(hashlib.md5(('%s|%s|%s' % (key, brand, kind)).encode()).hexdigest())
    out = []
    for _ in range(n):
        if not pool: break
        w = [max(.05, s - pool[-1][0] + .3) for s, _ in pool]
        i = rng.choices(range(len(pool)), weights=w)[0]
        out.append(pool.pop(i)[1])
    return out

def make_bed(brand, kind, text, total, out_path, mood=None, words=None, key='', gain=None):
    try:
        if os.environ.get('CE_DISABLE_MUSIC'): return None
        pace = (words / total) if (words and total) else None
        want = 1 if total <= 75 else min(6, int(total // 65) + 1)
        tracks = pick(brand, kind, mood, text, pace, key, n=want)
        files = []
        for t in tracks:
            p = _ensure(t)
            if p: files.append((t, p))
        if not files: return None
        g = gain if gain is not None else (0.8 if (pace or 0) > 3.3 else (1.1 if (pace or 3) < 2.2 else 1.0))
        out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['ffmpeg', '-v', 'error', '-y']
        rng = random.Random(key or 'x')
        for i, (t, p) in enumerate(files):
            if len(files) == 1 and total <= t['dur'] - 4: cmd += ['-ss', '%.2f' % rng.uniform(0, max(0, t['dur'] - total - 2)), '-i', str(p)]
            else: cmd += (['-stream_loop', '-1', '-i', str(p)] if len(files) == 1 else ['-i', str(p)])
        f = ''
        if len(files) > 1:
            prev = '0:a'
            for i in range(1, len(files)):
                f += '[%s][%d:a]acrossfade=d=5:c1=tri:c2=tri[x%d];' % (prev, i, i); prev = 'x%d' % i
            f += '[%s]volume=%.2f,afade=t=out:st=%.2f:d=2.5,atrim=0:%.2f[a]' % (prev, g, max(0, total - 2.5), total)
        else:
            f = '[0:a]volume=%.2f,afade=t=out:st=%.2f:d=2.5,atrim=0:%.2f[a]' % (g, max(0, total - 2.5), total)
        cmd += ['-filter_complex', f, '-map', '[a]', '-t', '%.2f' % total, '-ar', '48000', '-ac', '2', str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        info = {'path': str(out), 'tracks': [t['id'] for t, _ in files], 'styles': [t['style'] for t, _ in files], 'mood': ALIAS.get(mood, mood) if mood else mood_for(text), 'pace': round(pace, 2) if pace else None, 'gain': g}
        try: out.with_suffix('.music.json').write_text(json.dumps(info))
        except Exception: pass
        print('music director:', info, flush=True)
        return info
    except Exception as e:
        print('music director unavailable:', e, flush=True)
        return None
