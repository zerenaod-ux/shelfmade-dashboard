"""Runs ON KAGGLE (free GPU): ShelfMade 'idea as a living picture'. jobs.json {beats:[{image, ...}], scene, style}.
Step 1 pictures: beat 1 = FLUX.2 klein text-to-image, beats 2..n = FLUX.2 klein EDIT of the previous picture (the same scene visibly changes).
Step 2 motion: LTX-Video image-to-video turns each picture into a short live clip. Output /kaggle/working/out: pic_NN.png, clip_NN.mp4, log.txt, DONE."""
import glob, gc, json, os, subprocess, sys, time, traceback
OUT = '/kaggle/working/out'; os.makedirs(OUT, exist_ok=True)
IN = os.path.dirname(glob.glob('/kaggle/input/**/jobs.json', recursive=True)[0]); J = json.load(open(IN + '/jobs.json'))
LOG = open(OUT + '/log.txt', 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
subprocess.run('pip install -q -U diffusers transformers accelerate sentencepiece protobuf imageio imageio-ffmpeg 2>&1 | tail -1', shell=True)
import torch
from PIL import Image
t0 = time.time(); W, H = 576, 1024; beats = J['beats']
from diffusers import Flux2KleinPipeline
p = Flux2KleinPipeline.from_pretrained('black-forest-labs/FLUX.2-klein-4B', torch_dtype=torch.float16); p.enable_model_cpu_offload()
prev = None; pics = []
for i, b in enumerate(beats):
    try:
        g = torch.Generator('cpu').manual_seed(int(J.get('seed', 7)) + i)
        if prev is None:
            img = p(prompt=J['scene_prompt'] + ' ' + b['image'] + J['style'], width=W, height=H, num_inference_steps=4, guidance_scale=1.0, generator=g).images[0]
        else:
            img = p(image=[prev], prompt='Keep exactly the same scene, camera angle, objects and style. Only change this: ' + b['image'] + J['style'], width=W, height=H, num_inference_steps=4, guidance_scale=1.0, generator=g).images[0]
        img.save(OUT + '/pic_%02d.png' % i); prev = img; pics.append(i); log('picture', i, round(time.time() - t0))
    except Exception:
        log('PICTURE FAIL', i, traceback.format_exc()[-600:]); break
del p; gc.collect(); torch.cuda.empty_cache()
try:
    from diffusers import LTXImageToVideoPipeline
    from diffusers.utils import export_to_video
    dt = torch.bfloat16 if os.environ.get('LTX_DTYPE', 'bf16') == 'bf16' else torch.float16
    v = LTXImageToVideoPipeline.from_pretrained('Lightricks/LTX-Video', torch_dtype=dt); v.enable_model_cpu_offload(); v.vae.enable_tiling()
    for i in pics:
        try:
            t1 = time.time(); im = Image.open(OUT + '/pic_%02d.png' % i).convert('RGB').resize((480, 832))
            fr = v(image=im, prompt=beats[i].get('motion', 'slow smooth cinematic camera move, gentle natural motion') + ', ' + beats[i]['image'], negative_prompt='worst quality, inconsistent motion, blurry, jittery, distorted, text, watermark',
                   width=480, height=832, num_frames=65, num_inference_steps=int(os.environ.get('LTX_STEPS', '25')), guidance_scale=3.0, generator=torch.Generator('cpu').manual_seed(11 + i)).frames[0]
            export_to_video(fr, OUT + '/clip_%02d.mp4' % i, fps=24); log('clip', i, round(time.time() - t1), 's')
        except Exception:
            log('CLIP FAIL', i, traceback.format_exc()[-800:])
except Exception:
    log('LTX LOAD FAIL', traceback.format_exc()[-800:])
open(OUT + '/DONE', 'w').write('ok'); log('ALL DONE', round(time.time() - t0))
