"""Runs ON KAGGLE (free GPU): compares free image-to-video models on the same two ShelfMade-style pictures. Output: pic_X.png, <model>_X.mp4, log.txt (with seconds per clip)."""
import gc, os, subprocess, time, traceback
OUT = '/kaggle/working/out'; os.makedirs(OUT, exist_ok=True); LOG = open(OUT + '/log.txt', 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
subprocess.run('pip install -q -U diffusers transformers accelerate sentencepiece protobuf imageio imageio-ffmpeg 2>&1 | tail -1', shell=True)
import torch
from PIL import Image
from diffusers.utils import export_to_video
STYLE = ', cinematic 3D render, miniature diorama, bright soft light, rich colors, sharp focus, no text, vertical 9:16'
PICS = {'hill': 'A green hillside with a small trodden dirt path winding up toward a lone cottage, morning mist' + STYLE,
        'desk': 'A wooden desk with a small green seedling in a pot growing from a stack of old books, sunlight from a window' + STYLE}
from diffusers import Flux2KleinPipeline
p = Flux2KleinPipeline.from_pretrained('black-forest-labs/FLUX.2-klein-4B', torch_dtype=torch.float16); p.enable_model_cpu_offload()
for k, pr in PICS.items():
    p(prompt=pr, width=576, height=1024, num_inference_steps=4, guidance_scale=1.0, generator=torch.Generator('cpu').manual_seed(5)).images[0].save(OUT + '/pic_%s.png' % k); log('pic', k)
del p; gc.collect(); torch.cuda.empty_cache()
MOTION = {'hill': 'slow cinematic push-in, mist drifting, grass swaying, light rays moving', 'desk': 'gentle camera drift, the seedling slowly grows taller, leaves unfurl, dust motes in sunlight'}
def run(name, fn):
    try:
        t = time.time(); fn(); log(name, 'OK', round(time.time() - t), 's total')
    except Exception: log(name, 'FAIL', traceback.format_exc()[-700:])
    gc.collect(); torch.cuda.empty_cache()
def ltx():
    from diffusers import LTXImageToVideoPipeline
    v = LTXImageToVideoPipeline.from_pretrained('Lightricks/LTX-Video', torch_dtype=torch.bfloat16); v.enable_model_cpu_offload(); v.vae.enable_tiling()
    for k in PICS:
        t = time.time(); im = Image.open(OUT + '/pic_%s.png' % k).convert('RGB').resize((480, 832))
        fr = v(image=im, prompt=MOTION[k], negative_prompt='worst quality, blurry, jittery, distorted, text, watermark', width=480, height=832, num_frames=65, num_inference_steps=25, guidance_scale=3.0).frames[0]
        export_to_video(fr, OUT + '/ltx_%s.mp4' % k, fps=24); log('ltx', k, round(time.time() - t), 's')
def svd():
    from diffusers import StableVideoDiffusionPipeline
    v = StableVideoDiffusionPipeline.from_pretrained('stabilityai/stable-video-diffusion-img2vid-xt', torch_dtype=torch.float16, variant='fp16'); v.enable_model_cpu_offload()
    for k in PICS:
        t = time.time(); im = Image.open(OUT + '/pic_%s.png' % k).convert('RGB').resize((576, 1024))
        fr = v(im, decode_chunk_size=4, motion_bucket_id=140, noise_aug_strength=0.05, num_frames=25, generator=torch.manual_seed(3)).frames[0]
        export_to_video(fr, OUT + '/svd_%s.mp4' % k, fps=8); log('svd', k, round(time.time() - t), 's')
def cog():
    from diffusers import CogVideoXImageToVideoPipeline
    v = CogVideoXImageToVideoPipeline.from_pretrained('THUDM/CogVideoX-5b-I2V', torch_dtype=torch.float16); v.enable_sequential_cpu_offload(); v.vae.enable_tiling()
    for k in PICS:
        t = time.time(); im = Image.open(OUT + '/pic_%s.png' % k).convert('RGB').resize((480, 720))
        fr = v(image=im, prompt=MOTION[k], num_frames=33, num_inference_steps=25, guidance_scale=6.0, generator=torch.Generator('cpu').manual_seed(3)).frames[0]
        export_to_video(fr, OUT + '/cog_%s.mp4' % k, fps=8); log('cog', k, round(time.time() - t), 's')
for n, f in (('LTX-Video', ltx), ('SVD-XT', svd), ('CogVideoX-5B', cog)): run(n, f)
open(OUT + '/DONE', 'w').write('ok'); log('ALL DONE')
