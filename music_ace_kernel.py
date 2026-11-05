"""Runs ON KAGGLE (free GPU): composes original instrumental tracks with ACE-Step (Apache-2.0). Output -> /kaggle/working/out/<id>.mp3 + timing.json.
Setup once; then ONE PROCESS PER TRACK so a crash or GPU-memory leak cannot kill the run (the first AI test died after track 1)."""
import os, subprocess, json, time, sys, re
def sh(c, show=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if show: print('$', c[:120], '\n', (r.stdout + r.stderr)[-1200:], flush=True)
    return r
SPECS = json.loads('''__SPECS__''')
T = '/kaggle/temp'; OUT = '/kaggle/working/out'; os.makedirs(T, exist_ok=True); os.makedirs(OUT, exist_ok=True)
GEN = dict(guidance_scale=15.0, scheduler_type='euler', cfg_type='apg', omega_scale=10.0, guidance_interval=0.5, guidance_interval_decay=0.0, min_guidance_scale=3.0,
           use_erg_tag=True, use_erg_lyric=False, use_erg_diffusion=True, oss_steps=None, guidance_scale_text=0.0, guidance_scale_lyric=0.0)
WORKER = len(sys.argv) > 2 and sys.argv[1] == '--one'
if WORKER:
    sys.path.insert(0, T + '/ACE')
    from acestep.pipeline_ace_step import ACEStepPipeline
    s = [x for x in SPECS if x['id'] == sys.argv[2]][0]; wav = f"{T}/{s['id']}.wav"
    pipe = ACEStepPipeline(checkpoint_dir=T + '/ckpt', dtype='float32', torch_compile=False, cpu_offload=True)
    pipe(audio_duration=s['dur'], prompt=s['prompt'], lyrics='[instrumental]', infer_step=s.get('steps', 40), manual_seeds=str(s['seed']), save_path=wav, **GEN)
    sh(f"ffmpeg -v error -y -i {wav} -af 'highpass=f=35,loudnorm=I=-20:TP=-2:LRA=7' -ar 44100 -c:a libmp3lame -b:a 96k {OUT}/{s['id']}.mp3", False)
    os.remove(wav); sys.exit(0)
# ---------- setup (once) ----------
sh('nvidia-smi -L')
sh(f'git clone --depth 1 https://github.com/ace-step/ACE-Step {T}/ACE')
def pipi(*spec):
    return subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *spec], capture_output=True, text=True).returncode == 0
failed = []
for line in open(T + '/ACE/requirements.txt').read().splitlines():
    line = line.split('#')[0].strip()
    if not line or line.startswith('-'): continue
    name = re.split(r'[=<>~;\[ ]', line)[0].lower()
    if name in ('torch', 'torchaudio', 'torchvision'): continue
    if not pipi(line) and not pipi(name): failed.append(line)
pipi('huggingface_hub>=0.30')
for pkg in ('transformers', 'diffusers', 'accelerate', 'peft'): pipi('-U', pkg)
sh(f'cd {T}/ACE && {sys.executable} -m pip install -q --no-deps -e . 2>&1 | tail -3', False)
timing = {'tracks': {}, 'errors': [], 'setup_failed': failed}
def save(): json.dump(timing, open('/kaggle/working/timing.json', 'w'), indent=1)
for s in SPECS:
    t0 = time.time()
    for attempt in (1, 2):
        r = subprocess.run([sys.executable, __file__, '--one', s['id']], capture_output=True, text=True)
        if os.path.exists(f"{OUT}/{s['id']}.mp3"): timing['tracks'][s['id']] = round(time.time() - t0, 1); break
        timing['errors'].append('%s try %d: %s' % (s['id'], attempt, (r.stdout + r.stderr)[-500:]))
    save(); print('done', s['id'], timing['tracks'].get(s['id']), flush=True)
open('/kaggle/working/DONE', 'w').write('ok'); print('ALL DONE', len(timing['tracks']), 'tracks', flush=True)
