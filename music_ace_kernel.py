"""Runs ON KAGGLE (free GPU): composes original instrumental tracks with ACE-Step (Apache-2.0). Output -> /kaggle/working/out/<id>.mp3 + timing.json"""
import os, subprocess, json, time, glob, sys, traceback
def sh(c, show=True):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    if show: print('$', c[:120], '\n', (r.stdout + r.stderr)[-1200:], flush=True)
    return r
SPECS = json.loads('''__SPECS__''')
T = '/kaggle/temp'; OUT = '/kaggle/working/out'; os.makedirs(T, exist_ok=True); os.makedirs(OUT, exist_ok=True)
sh('nvidia-smi -L')
sh(f'git clone --depth 1 https://github.com/ace-step/ACE-Step {T}/ACE')
SETUP = []
SETUP.append(sh(f"cd {T}/ACE && grep -viE '^(torch|torchaudio|torchvision)([=<>~ ]|$)' requirements.txt > req_notorch.txt; {sys.executable} -m pip install -q -r req_notorch.txt 2>&1 | tail -12").stdout[-900:])
SETUP.append(sh(f'cd {T}/ACE && {sys.executable} -m pip install -q --no-deps -e . 2>&1 | tail -3').stdout[-400:])
SETUP.append(sh(f'{sys.executable} -m pip install -q loguru 2>&1 | tail -3').stdout[-300:])
import importlib; importlib.invalidate_caches()
sys.path.insert(0, T + '/ACE')
timing = {'tracks': {}, 'errors': [], 'setup': SETUP}
def save():
    json.dump(timing, open('/kaggle/working/timing.json', 'w'), indent=1)
pipe = None
for dtype, off in (('bfloat16', False), ('float32', True), ('float32', False)):
    try:
        from acestep.pipeline_ace_step import ACEStepPipeline
        t0 = time.time()
        pipe = ACEStepPipeline(checkpoint_dir=T + '/ckpt', dtype=dtype, torch_compile=False, cpu_offload=off)
        pipe.load_checkpoint(T + '/ckpt') if hasattr(pipe, 'load_checkpoint') and not getattr(pipe, 'loaded', False) else None
        timing['pipeline'] = {'dtype': dtype, 'cpu_offload': off, 'load_s': round(time.time() - t0, 1)}; print('pipeline ok', timing['pipeline'], flush=True)
        # warm probe: shortest job decides whether this dtype works
        s = SPECS[0]; t0 = time.time()
        pipe(audio_duration=min(20, s['dur']), prompt=s['prompt'], lyrics='[instrumental]', infer_step=30, guidance_scale=15.0, scheduler_type='euler', cfg_type='apg',
             omega_scale=10.0, manual_seeds=str(s['seed']), guidance_interval=0.5, guidance_interval_decay=0.0, min_guidance_scale=3.0, use_erg_tag=True, use_erg_lyric=False,
             use_erg_diffusion=True, oss_steps=None, guidance_scale_text=0.0, guidance_scale_lyric=0.0, save_path=T + '/probe.wav')
        timing['probe_20s_seconds'] = round(time.time() - t0, 1); save(); break
    except Exception as e:
        timing['errors'].append('%s/%s: %s' % (dtype, off, traceback.format_exc()[-600:])); print('pipeline failed', dtype, off, e, flush=True); pipe = None; save()
        import gc, torch; gc.collect(); torch.cuda.empty_cache()
if pipe is None:
    save(); print('NO PIPELINE'); sys.exit(1)
for s in SPECS:
    t0 = time.time(); wav = f"{T}/{s['id']}.wav"
    try:
        pipe(audio_duration=s['dur'], prompt=s['prompt'], lyrics='[instrumental]', infer_step=s.get('steps', 40), guidance_scale=15.0, scheduler_type='euler', cfg_type='apg',
             omega_scale=10.0, manual_seeds=str(s['seed']), guidance_interval=0.5, guidance_interval_decay=0.0, min_guidance_scale=3.0, use_erg_tag=True, use_erg_lyric=False,
             use_erg_diffusion=True, oss_steps=None, guidance_scale_text=0.0, guidance_scale_lyric=0.0, save_path=wav)
        r = sh(f"ffmpeg -v error -y -i {wav} -af 'highpass=f=35,loudnorm=I=-20:TP=-2:LRA=7' -ar 44100 -c:a libmp3lame -b:a 96k {OUT}/{s['id']}.mp3", False)
        os.remove(wav) if os.path.exists(wav) else None
        timing['tracks'][s['id']] = round(time.time() - t0, 1)
    except Exception as e:
        timing['errors'].append('%s: %s' % (s['id'], str(e)[-300:]))
        import gc, torch; gc.collect(); torch.cuda.empty_cache()
    save(); print('done', s['id'], timing['tracks'].get(s['id']), flush=True)
open('/kaggle/working/DONE', 'w').write('ok'); print('ALL DONE', len(timing['tracks']), 'tracks', flush=True)
