"""Driver (runs on GitHub Actions, workflow music-ace.yml; no Mac needed): composes music on the FREE Kaggle GPU (account minddoodles) with ACE-Step.
  python3 music_ace.py test   -> 3 short test tracks + speed report (decides if the free GPU is fast enough)
  python3 music_ace.py full [per_style] -> a full AI-composed library merged into music-lib/index.json (then run push-music2.sh)"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import music_studio
USER = 'minddoodles'; KERNEL = 'music-ace'
E = dict(os.environ); tp = Path.home() / '.kaggle' / 'access_token'
if tp.exists() and not E.get('KAGGLE_API_TOKEN'): E['KAGGLE_API_TOKEN'] = tp.read_text().strip()
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def kg(*a):
    code = 'import sys;from kaggle.cli import main;sys.argv=["kaggle"]+sys.argv[1:];main()'
    r = subprocess.run([sys.executable, '-c', code, *a], capture_output=True, text=True, env=E); return (r.stdout + r.stderr).strip()
TAGS = {
 'sm_candle': 'solo piano, soft felt piano, gentle arpeggios, warm, intimate, candlelight, literary, slow, 66 bpm, instrumental',
 'sm_library': 'ambient pad, soft strings, quiet library atmosphere, calm, reflective, slow, minimal, instrumental',
 'sm_gothic': 'dark ambient, low drone, cello, gothic, brooding, eerie, slow, cinematic, instrumental',
 'sm_adventure': 'light orchestral, plucked strings, piano, adventurous, hopeful, curious, 95 bpm, instrumental',
 'sm_tender': 'sad piano, soft strings, tender, melancholic, slow, emotional, instrumental',
 'ml_lofi': 'lo-fi hip hop, mellow rhodes piano, vinyl warmth, soft drums, 78 bpm, chill, thoughtful, instrumental',
 'ml_pulse': 'minimal electronic, soft synth arpeggio, subtle beat, thoughtful, modern, 100 bpm, instrumental',
 'ml_deep': 'deep dark ambient, evolving drone, mysterious, subtle pulse, introspective, instrumental',
 'ml_wonder': 'airy pads, bells, glockenspiel, wonder, curiosity, floating, gentle, instrumental',
 'ml_tension': 'suspenseful electronic, driving pulse, dark synth, tension, 110 bpm, cinematic, instrumental',
 'dd_bounce': 'upbeat playful cartoon music, marimba, pizzicato strings, bouncy bass, light drums, comedy, 118 bpm, major key, instrumental',
 'dd_quirky': 'quirky comedic music, staccato pizzicato, xylophone, bassoon, sneaky playful, 105 bpm, instrumental',
 'dd_sneak': 'sneaking tiptoe comedy music, pizzicato, muted bass, suspenseful but funny, 95 bpm, instrumental',
 'dd_chill': 'chill feel-good acoustic guitar, light percussion, warm, easygoing, sitcom background, 84 bpm, instrumental',
 'dd_hype': 'energetic fun upbeat pop instrumental, claps, bright synth, bouncy, excited, 130 bpm, instrumental',
}
def specs(per, dur, steps):
    out = []
    for style in music_studio.STYLES:
        for k in range(per):
            out.append({'id': f'ace_{style}_{k + 1:02d}', 'style': style, 'prompt': TAGS[style], 'dur': dur, 'seed': 1000 + 37 * k + len(out), 'steps': steps})
    return out
def run(sp):
    work = HERE / '_ace_work'; shutil.rmtree(work, ignore_errors=True); (work / 'k').mkdir(parents=True)
    code = (HERE / 'music_ace_kernel.py').read_text().replace('__SPECS__', json.dumps(sp).replace("'", ' '))
    (work / 'k' / 'music_ace_kernel.py').write_text(code)
    (work / 'k' / 'kernel-metadata.json').write_text(json.dumps({'id': f'{USER}/{KERNEL}', 'title': 'music ace', 'code_file': 'music_ace_kernel.py', 'language': 'python', 'kernel_type': 'script',
        'is_private': True, 'enable_gpu': True, 'enable_internet': True, 'dataset_sources': [], 'competition_sources': [], 'kernel_sources': [], 'model_sources': []}))
    log('starting the free GPU...'); log(kg('kernels', 'push', '-p', str(work / 'k'))[-200:])
    t0 = time.time()
    while True:
        time.sleep(40); s = kg('kernels', 'status', f'{USER}/{KERNEL}').lower(); log(s[-60:])
        if 'complete' in s: break
        if 'error' in s or 'cancel' in s or 'fail' in s: break
        if time.time() - t0 > 8 * 3600: log('timeout'); break
    dl = work / 'dl'; dl.mkdir(); kg('kernels', 'output', f'{USER}/{KERNEL}', '-p', str(dl)); return dl
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'test'
    if mode == 'test':
        sp = [s for s in specs(1, 60, 40) if s['style'] in ('dd_bounce', 'ml_lofi', 'sm_candle')]
        dl = run(sp); t = dl / 'timing.json'
        if t.exists(): print(json.dumps(json.loads(t.read_text()), indent=1)[:2500])
        out = HERE / 'music-ace-test'; out.mkdir(exist_ok=True)
        for f in dl.rglob('*.mp3'): shutil.copy(f, out / f.name)
        log('test tracks in', out, [p.name for p in out.glob('*.mp3')])
        if not list(out.glob('*.mp3')): raise SystemExit('NO TRACKS MADE - see timing above')
    else:
        per = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        dl = run(specs(per, 75, 40)); lib = HERE / 'music-lib'; lib.mkdir(exist_ok=True); idxp = HERE / 'data' / 'music' / 'index.json'; idx = json.loads(idxp.read_text())
        got = 0
        for f in dl.rglob('ace_*.mp3'):
            style = f.stem.split('_', 1)[1].rsplit('_', 1)[0]; S = music_studio.STYLES[style]; shutil.copy(f, lib / f.name)
            idx = [i for i in idx if i['id'] != f.stem] + [dict(id=f.stem, file=f.name, style=style, brands=S['brands'], mood=S['mood'], bpm=int(sum(S['bpm']) / 2), energy=S['energy'], density=S['dens'], dur=75.0, source='ace')]; got += 1
        idxp.write_text(json.dumps(idx, indent=1)); log('added', got, 'AI tracks to the library')
        if not got: raise SystemExit('NO TRACKS MADE')
main()
