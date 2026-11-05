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
FRONT = (" IMPORTANT FRAMING: both characters look straight toward the camera (front view, face fully visible, head upright and level, not tilted or turned away), "
         "faces large and well lit, mouths ALWAYS CLOSED (lips together, no open mouth, no teeth showing, even when shouting or explaining), hands and props never covering the faces.")
def main(work):
    work = Path(work).resolve(); st = json.loads((work / 'story.json').read_text())
    if (work / 'kaggle_stage1.DONE').exists(): log('stage 1 already done'); return
    vj = [{'who': l['who'], 'text': l['text'], 'feel': l['feel'], 'wav': f'line_{si:02d}_{li:02d}.wav'} for si, sh in enumerate(st['shots']) for li, l in enumerate(sh['lines'])]
    pj = [{'prompt': stories.LOOK + sh['scene'] + FRONT, 'out': f'shot_{i:02d}.png', 'seed': 100 + i} for i, sh in enumerate(st['shots'])]
    ins = work / 'k1_in'; shutil.rmtree(ins, ignore_errors=True); ins.mkdir()
    shutil.copy(ROOT / 'data/production/reference-v1/Opening-frame.png', ins / 'ref.png'); shutil.copy(HERE / 'voices.py', ins / 'voices.py'); shutil.copy(HERE / 'align.py', ins / 'align.py')
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
    if not list(tmp.rglob('DONE')) or got < len(vj) + len(pj): raise SystemExit('Kaggle output incomplete (%d files); log: %s' % (got, [str(x) for x in tmp.glob('*.log')]))
    (work / 'kaggle_stage1.DONE').write_text('ok'); shutil.rmtree(tmp, ignore_errors=True); log('stage 1 done:', got, 'files')
if __name__ == '__main__': main(sys.argv[1])
