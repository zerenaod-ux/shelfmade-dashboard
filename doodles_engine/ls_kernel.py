"""Runs ON KAGGLE (free GPU): LatentSync lip-sync for every prepared line. Output -> /kaggle/working/out/ls_SS_LL.mp4"""
import os,subprocess,json,glob,sys,time
def sh(c,show=True):
    r=subprocess.run(c,shell=True,capture_output=True,text=True)
    if show:print('$',c[:110],'\n',(r.stdout+r.stderr)[-1500:],flush=True)
    return r
T='/kaggle/temp';OUT='/kaggle/working/out';os.makedirs(T,exist_ok=True);os.makedirs(OUT,exist_ok=True)
IN=[os.path.dirname(p) for p in glob.glob('/kaggle/input/**/jobs.json',recursive=True)][0]
jobs=json.load(open(IN+'/jobs.json'))['jobs'];print('jobs',len(jobs),flush=True)
LS=T+'/LS'
sh(f'git clone --depth 1 https://github.com/bytedance/LatentSync {LS}')
sh('pip install -q diffusers==0.32.2 transformers==4.48.0 decord einops omegaconf mediapipe python_speech_features scenedetect ffmpeg-python imageio imageio-ffmpeg lpips face-alignment huggingface_hub accelerate insightface onnxruntime-gpu DeepCache torchmetrics kornia 2>&1 | tail -3')
from huggingface_hub import snapshot_download
snapshot_download('ByteDance/LatentSync-1.5',local_dir=LS+'/checkpoints')
sh(f'mkdir -p ~/.cache/torch/hub/checkpoints && for f in {LS}/checkpoints/auxiliary/*; do ln -sf $f ~/.cache/torch/hub/checkpoints/$(basename $f); done',False)
ng=max(1,len([l for l in sh('nvidia-smi -L',False).stdout.splitlines() if l.startswith('GPU')]));print('gpus',ng,flush=True)
STEPS=int(os.environ.get('LS_STEPS','20'));GS=os.environ.get('LS_GUIDANCE','3.0')
def cmd(j,g,deep):
    k=j['key']
    return (f"cd {LS} && CUDA_VISIBLE_DEVICES={g} python -m scripts.inference --unet_config_path configs/unet/stage2.yaml --inference_ckpt_path checkpoints/latentsync_unet.pt "
            f"--inference_steps {STEPS} --guidance_scale {GS} {'--enable_deepcache ' if deep else ''}--video_path {IN}/{k}.mp4 --audio_path {IN}/{k}.wav --video_out_path {OUT}/{k}.mp4 2>&1 | tail -6")
work=[[] for _ in range(ng)]
for i,j in enumerate(sorted(jobs,key=lambda j:-j['dur'])):work[i%ng].append(j)
procs=[]
for g,lst in enumerate(work):
    code=('import subprocess,os,sys\nfor c in sys.argv[1:]:\n    c1,c2=c.split("|||")\n    out=c1.split("--video_out_path ")[1].split(" ")[0]\n'
          '    if os.path.exists(out):continue\n    r=subprocess.run(c1,shell=True,capture_output=True,text=True);print(r.stdout[-600:],flush=True)\n'
          '    if not os.path.exists(out):\n        r=subprocess.run(c2,shell=True,capture_output=True,text=True);print("retry no-deepcache",r.stdout[-600:],flush=True)\n')
    open(f'{T}/w{g}.py','w').write(code)
    args=' '.join("'"+cmd(j,g,True)+'|||'+cmd(j,g,False)+"'" for j in lst)
    procs.append(subprocess.Popen(f"python {T}/w{g}.py {args}",shell=True))
t0=time.time()
for p in procs:p.wait()
done=sorted(os.path.basename(f) for f in glob.glob(OUT+'/*.mp4'))
print('DONE',len(done),'of',len(jobs),'in',round((time.time()-t0)/60,1),'min',done,flush=True)
json.dump({'done':done,'jobs':len(jobs)},open('/kaggle/working/done.json','w'))
