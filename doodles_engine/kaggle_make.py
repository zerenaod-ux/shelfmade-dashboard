"""Mac: stage 1 of a Doodles Short on the FREE Kaggle GPU = voices + pictures + word timing. Usage: python kaggle_make.py <workdir>   (workdir has story.json)
Writes <workdir>/line_SS_LL.wav, shot_SS.png, align_SS_LL.json exactly like the local steps would. Any failure exits non-zero (caller can fall back to the local Mac engines)."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent; USER = 'minddoodles'; KERNEL = 'doodles-make'
sys.path.insert(0, str(HERE)); import stories
E = dict(os.environ); tp = Path.home() / '.kaggle' / 'access_token'
if tp.exists() and not E.get('KAGGLE_API_TOKEN'): E['KAGGLE_API_TOKEN'] = tp.read_text().strip()
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def kg(*a):
    code = 'import sys;from kaggle.cli import main;sys.argv=["kaggle"]+sys.argv[1:];main()'
    r = subprocess.run([sys.executable, '-c', code, *a], capture_output=True, text=True, env=E); return (r.stdout + r.stderr).strip()
FRONT = (" IMPORTANT FRAMING: both characters sit at the podcast desk, bodies angled slightly toward each other, faces turned three-quarters toward the camera (face fully visible, head upright and level, microphone below the mouth, never covering it), "
         "faces well lit, both characters fully in frame at equal size (medium two-shot, not a close-up), mouths ALWAYS CLOSED (lips together, no open mouth, no teeth showing, even when shouting or explaining), hands and props never covering the faces.")
WIDE = (" WIDE CINEMATIC 16:9 COMPOSITION: the two characters stand close together in the centre-left and centre-right of the frame, filling about half the height, in a realistic, detailed, lived-in location with depth, specific props and everyday clutter (not an empty room). "
        "Any other person mentioned in the scene (boss, barista, neighbour, ex) is visible in the background or at the edge, smaller, never in front of the two faces.")
def main(work):
    work = Path(work).resolve(); st = json.loads((work / 'story.json').read_text())
    if (work / 'kaggle_stage1.DONE').exists(): log('stage 1 already done'); return
    vj = [{'who': l['who'], 'text': l['text'], 'feel': l['feel'], 'wav': f'line_{si:02d}_{li:02d}.wav'} for si, sh in enumerate(st['shots']) for li, l in enumerate(sh['lines'])]
    wide = bool(st.get('landscape'))
    SINGLE = os.environ.get('DOODLES_SINGLE_SET', '1') == '1' and not wide
    if SINGLE:   # ONE_SET (owner 2026-11-15): one picture for the whole video; the render camera moves between Leo and Mia instead of changing the background
        sc = (stories.look_for(st.get('id') or st.get('title')) + 'SETTING: ' + stories.set_for(st.get('id') or st.get('title')) + '. '
              "COMPOSITION: both characters sit at one long podcast desk, Leo near the LEFT edge and Mia near the RIGHT edge with a clear gap of about one shoulder-width of desk between them, bodies angled slightly toward the centre, faces turned three-quarters toward the camera, "
              "chest-up framing, equal size, each head fully inside the picture, both listening calmly with closed mouths and friendly neutral faces, hands resting on the desk, one microphone for each below the mouth, the whole scene tidy with no props that hide faces.")
        pj = [{'prompt': sc, 'out': 'shot_00.png', 'seed': 100, 'w': 768, 'h': 1366}]
    else:
        pj = [{'prompt': stories.look_for(st.get('id') or st.get('title')) + sh['scene'] + FRONT + (WIDE if wide else ''), 'out': f'shot_{i:02d}.png', 'seed': 100 + i, **({'w': 1024, 'h': 576} if wide else {})} for i, sh in enumerate(st['shots'])]
    ins = work / 'k1_in'; shutil.rmtree(ins, ignore_errors=True); ins.mkdir()
    shutil.copy(ROOT / 'data/production/reference-v1/Opening-frame.png', ins / 'ref.png'); shutil.copy(HERE / 'voices.py', ins / 'voices.py'); shutil.copy(ROOT / 'data/engines/yunet/face_detection_yunet_2023mar.onnx', ins / 'yunet.onnx'); shutil.copy(HERE / 'align.py', ins / 'align.py')
    (ins / 'jobs.json').write_text(json.dumps({'story': st, 'prompts': pj, 'voice_jobs': vj}))
    slug = 'doodles-make-' + time.strftime('%d%H%M%S'); (ins / 'dataset-metadata.json').write_text(json.dumps({'title': slug.replace('-', ' '), 'id': f'{USER}/{slug}', 'licenses': [{'name': 'CC0-1.0'}]}))
    for attempt in range(5):
        r = kg('datasets', 'create', '-p', str(ins)); log(r[-120:])
        if 'error' not in r.lower() and 'problem' not in r.lower(): break
        log('Kaggle hiccup, retrying in 60 s'); time.sleep(60)
    else: raise SystemExit('Kaggle dataset upload kept failing')
    for i in range(60):
        if 'ready' in kg('datasets', 'status', f'{USER}/{slug}').lower(): break
        time.sleep(10)
    else: raise SystemExit('dataset never ready')
    kd = work / 'k1_kernel'; kd.mkdir(exist_ok=True); shutil.copy(HERE / 'kaggle_make_kernel.py', kd / 'kaggle_make_kernel.py')
    (kd / 'kernel-metadata.json').write_text(json.dumps({'id': f'{USER}/{KERNEL}', 'title': 'doodles make', 'code_file': 'kaggle_make_kernel.py', 'language': 'python', 'kernel_type': 'script',
        'is_private': True, 'enable_gpu': True, 'enable_internet': True, 'dataset_sources': [f'{USER}/{slug}'], 'competition_sources': [], 'kernel_sources': [], 'model_sources': []}))
    log('starting the free GPU...'); r = kg('kernels', 'push', '-p', str(kd)); log(r[-200:])
    if 'not valid' in r: raise SystemExit('Kaggle rejected the dataset: ' + r[-200:])
    t0 = time.time()
    while True:
        time.sleep(40); s = kg('kernels', 'status', f'{USER}/{KERNEL}').lower(); log(s[-60:])
        if 'complete' in s: break
        if 'error' in s or 'cancel' in s or 'fail' in s: raise SystemExit('kernel failed')
        if time.time() - t0 > 3 * 3600: raise SystemExit('kernel timeout')
    tmp = work / 'k1_dl'; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(); kg('kernels', 'output', f'{USER}/{KERNEL}', '-p', str(tmp))
    got = 0
    for f in list(tmp.rglob('shot_*.png')) + list(tmp.rglob('line_*.wav')) + list(tmp.rglob('align_*.json')):
        shutil.copy(f, work / f.name); got += 1
    _miss = [v['wav'] for v in vj if not (work / v['wav']).is_file()] + [j['out'] for j in pj if not (work / j['out']).is_file()]   # every voice line and picture must really be there
    if not list(tmp.rglob('DONE')) or got < len(vj) + len(pj) or _miss: raise SystemExit('Kaggle output incomplete (%d files, missing %s); log: %s' % (got, _miss, [str(x) for x in tmp.glob('*.log')]))
    if SINGLE:   # the same picture for every shot (the shots only decide who speaks and where the camera looks)
        for i in range(1, len(st['shots'])): shutil.copy(work / 'shot_00.png', work / f'shot_{i:02d}.png')
    (work / 'kaggle_stage1.DONE').write_text('ok'); shutil.rmtree(tmp, ignore_errors=True); log('stage 1 done:', got, 'files')
if __name__ == '__main__': main(sys.argv[1])
