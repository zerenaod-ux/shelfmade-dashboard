"""Runs ON KAGGLE: round 2 of free image-to-video models: Wan2.2-TI2V-5B and HunyuanVideo-1.5 (480p i2v) on three pictures, incl. an OPEN BOOK (the case where LTX melted colors). Output: pic_X.png, <model>_X.mp4, log.txt."""
import gc, os, shutil, subprocess, time, traceback
os.environ['HF_HOME'] = '/kaggle/temp/hf'; os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'; os.makedirs('/kaggle/temp/hf', exist_ok=True)
OUT = '/kaggle/working/out'; os.makedirs(OUT, exist_ok=True); LOG = open(OUT + '/log.txt', 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
subprocess.run('pip install -q -U git+https://github.com/huggingface/diffusers transformers accelerate sentencepiece protobuf imageio imageio-ffmpeg ftfy 2>&1 | tail -1', shell=True)
import torch
from PIL import Image
from diffusers.utils import export_to_video
STYLE = ', cinematic 3D render, miniature diorama, bright soft light, rich colors, sharp focus, no text, vertical 9:16'
PICS = {'hill': 'A green hillside with a small trodden dirt path winding up toward a lone cottage, morning mist' + STYLE,
        'desk': 'A wooden desk with a small green seedling in a pot growing from a stack of old books, sunlight from a window' + STYLE,
        'book': 'An old open leather book lying on a wooden table, pages with faint handwriting, a candle beside it, warm window light' + STYLE}
MOTION = {'hill': 'slow cinematic push-in, mist drifting, grass swaying in the wind, light rays moving',
          'desk': 'gentle camera drift, the seedling slowly grows taller, leaves unfurl, dust motes floating in sunlight',
          'book': 'the pages gently turn one by one, candle flame flickers, soft camera push-in, the book stays sharp and detailed'}
from diffusers import Flux2KleinPipeline
p = Flux2KleinPipeline.from_pretrained('black-forest-labs/FLUX.2-klein-4B', torch_dtype=torch.float16); p.enable_model_cpu_offload()
for k, pr in PICS.items():
    p(prompt=pr, width=576, height=1024, num_inference_steps=4, guidance_scale=1.0, generator=torch.Generator('cpu').manual_seed(5)).images[0].save(OUT + '/pic_%s.png' % k); log('pic', k)
del p; gc.collect(); torch.cuda.empty_cache()
BUDGET = 100 * 60
def run(name, fn):
    t = time.time()
    try: fn(t); log(name, 'OK', round(time.time() - t), 's total')
    except Exception: log(name, 'FAIL', traceback.format_exc()[-900:])
    gc.collect(); torch.cuda.empty_cache(); shutil.rmtree('/kaggle/temp/hf/hub', ignore_errors=True)   # free disk before the next model
def wan(t0):
    from diffusers import WanImageToVideoPipeline
    v = WanImageToVideoPipeline.from_pretrained('Wan-AI/Wan2.2-TI2V-5B-Diffusers', torch_dtype=torch.bfloat16); v.enable_model_cpu_offload(); v.vae.enable_tiling()
    for k in PICS:
        if time.time() - t0 > BUDGET: log('wan budget used, skipping', k); continue
        t = time.time(); im = Image.open(OUT + '/pic_%s.png' % k).convert('RGB').resize((384, 640))
        fr = v(image=im, prompt=MOTION[k], negative_prompt='blurry, distorted, melting, smeared, jitter, text, watermark', height=640, width=384, num_frames=33, num_inference_steps=24, guidance_scale=5.0, generator=torch.Generator('cpu').manual_seed(3)).frames[0]
        export_to_video(fr, OUT + '/wan_%s.mp4' % k, fps=24); log('wan', k, round(time.time() - t), 's')
def hy(t0):
    from diffusers import HunyuanVideo15ImageToVideoPipeline
    v = HunyuanVideo15ImageToVideoPipeline.from_pretrained('hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_i2v', torch_dtype=torch.bfloat16); v.enable_model_cpu_offload(); v.vae.enable_tiling()
    for k in PICS:
        if time.time() - t0 > BUDGET: log('hy budget used, skipping', k); continue
        t = time.time(); im = Image.open(OUT + '/pic_%s.png' % k).convert('RGB').resize((384, 672))
        fr = v(image=im, prompt=MOTION[k], num_frames=33, num_inference_steps=20, generator=torch.Generator('cpu').manual_seed(3)).frames[0]
        export_to_video(fr, OUT + '/hy_%s.mp4' % k, fps=24); log('hy', k, round(time.time() - t), 's')
for n, f in (('Wan2.2-TI2V-5B', wan), ('HunyuanVideo-1.5', hy)): run(n, f)
open(OUT + '/DONE', 'w').write('ok'); log('ALL DONE')
