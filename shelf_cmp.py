"""Pushes shelf_cmp_kernel.py to the free Kaggle GPU, waits, downloads clips to out/ (TEST only)."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
USER = 'minddoodles'; KERNEL = 'shelf-cmp'; E = dict(os.environ)
def kg(*a):
    code = 'import sys;from kaggle.cli import main;sys.argv=["kaggle"]+sys.argv[1:];main()'
    r = subprocess.run([sys.executable, '-c', code, *a], capture_output=True, text=True, env=E); return (r.stdout + r.stderr).strip()
kd = Path('cmp_kernel'); shutil.rmtree(kd, ignore_errors=True); kd.mkdir(); shutil.copy('shelf_cmp_kernel.py', kd / 'shelf_cmp_kernel.py')
(kd / 'kernel-metadata.json').write_text(json.dumps({'id': f'{USER}/{KERNEL}', 'title': 'shelf cmp', 'code_file': 'shelf_cmp_kernel.py', 'language': 'python', 'kernel_type': 'script', 'is_private': True, 'enable_gpu': True, 'enable_internet': True, 'dataset_sources': [], 'competition_sources': [], 'kernel_sources': [], 'model_sources': []}))
print(kg('kernels', 'push', '-p', str(kd))[-200:]); t0 = time.time()
while True:
    time.sleep(45); s = kg('kernels', 'status', f'{USER}/{KERNEL}').lower(); print(time.strftime('%H:%M'), s[-50:], flush=True)
    if 'complete' in s or 'error' in s or 'cancel' in s or 'fail' in s: break
    if time.time() - t0 > 3 * 3600: break
Path('out').mkdir(exist_ok=True); tmp = Path('cmp_out'); tmp.mkdir(exist_ok=True); kg('kernels', 'output', f'{USER}/{KERNEL}', '-p', str(tmp))
for f in tmp.rglob('*'):
    if f.is_file() and f.suffix in ('.mp4', '.png', '.txt'): shutil.copy(f, 'out/cmp-' + f.name)
print((tmp / 'log.txt').read_text()[-3000:] if (tmp / 'log.txt').exists() else 'no log')
