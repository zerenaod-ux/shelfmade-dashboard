"""Runs ON KAGGLE (free GPU): AnimationDoodles stage 1 = voices (Qwen3-TTS fp32) -> pictures (FLUX.2 klein edit of the approved Leo&Mia reference) -> word timing (wav2vec2).
Input dataset: jobs.json {story, prompts[], voice_jobs[]}, ref.png, voices.py, align.py. Output /kaggle/working/out: shot_SS.png, line_SS_LL.wav, align_SS_LL.json, story.json, DONE."""
import glob, gc, json, os, shutil, subprocess, sys, time
OUT = '/kaggle/working/out'; os.makedirs(OUT, exist_ok=True)
IN = os.path.dirname(glob.glob('/kaggle/input/**/jobs.json', recursive=True)[0]); sys.path.insert(0, IN)
J = json.load(open(IN + '/jobs.json')); json.dump(J['story'], open(OUT + '/story.json', 'w'))
subprocess.run('pip install -q -U diffusers transformers accelerate sentencepiece protobuf qwen-tts soundfile 2>&1 | tail -1', shell=True)
import numpy as np, torch, soundfile as sf
import voices as V
SR = V.SR
t0 = time.time()
from qwen_tts import Qwen3TTSModel
m = Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice', device_map='cuda:0', dtype=torch.float32)
try: avail = [x.lower() for x in m.get_supported_speakers()]
except Exception: avail = []
def pick(pref):
    for p in pref:
        if not avail or p.lower() in avail: return p
    return pref[0]
SPK = {'leo': pick(['Ryan', 'Aiden', 'Eric', 'Dylan']), 'mia': pick(['Vivian', 'Serena', 'Ono_Anna'])}; print('voices', SPK, flush=True)
for j in J['voice_jobs']:
    inst = V.BASE[j['who']] + V.FEEL.get(j.get('feel', 'warm'), V.FEEL['warm'])
    parts = []
    for attempt in range(3):
        try:
            wavs, sr = m.generate_custom_voice(text=j['text'], language='English', speaker=SPK[j['who']], instruct=inst); break
        except Exception as e:
            print('tts retry', attempt, str(e)[:100], flush=True); time.sleep(2)
    a = np.array(wavs[0], dtype='float32').reshape(-1)
    if int(sr) != SR: a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * SR / sr)), np.arange(len(a)), a).astype('float32')
    pk = float(np.max(np.abs(a))) or 1.0
    if pk > 0.95: a = a * (0.95 / pk)
    sf.write(OUT + '/' + j['wav'], a, SR, subtype='PCM_16'); print('voice', j['wav'], round(len(a) / SR, 1), flush=True)
del m; gc.collect(); torch.cuda.empty_cache(); print('voices done', round(time.time() - t0), flush=True)
from diffusers import Flux2KleinPipeline
from PIL import Image
p = Flux2KleinPipeline.from_pretrained('black-forest-labs/FLUX.2-klein-4B', torch_dtype=torch.float16); p.enable_model_cpu_offload()
ref = Image.open(IN + '/ref.png').convert('RGB')
for k, jb in enumerate(J['prompts']):
    img = p(image=[ref], prompt=jb['prompt'], width=int(jb.get('w',576)), height=int(jb.get('h',1024)), num_inference_steps=4, guidance_scale=1.0, generator=torch.Generator('cpu').manual_seed(int(jb['seed']))).images[0]
    img.save(OUT + '/' + jb['out']); print('picture', jb['out'], flush=True)
del p; gc.collect(); torch.cuda.empty_cache()
shutil.copy(IN + '/align.py', '/kaggle/working/align.py')
r = subprocess.run([sys.executable, '/kaggle/working/align.py', OUT], capture_output=True, text=True); print((r.stdout + r.stderr)[-800:], flush=True)
open(OUT + '/DONE', 'w').write('ok'); print('ALL DONE', round(time.time() - t0), flush=True)
