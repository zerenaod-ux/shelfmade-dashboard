"""Free local picture maker: FLUX.2 klein 4B (Apache-2.0) via mflux, edits the approved Leo & Mia reference into new scenes.
Run with the img-lab python. stdin: {"ref":[paths],"jobs":[{"prompt","out","seed","w","h"}]}. Model loads once; skips finished files."""
import json,sys,time
from pathlib import Path
def main():
    cfg=json.loads(sys.stdin.read())
    from mflux.models.flux2.variants import Flux2KleinEdit
    t0=time.time()
    model=Flux2KleinEdit(quantize=8)
    print('model loaded',round(time.time()-t0),'s',flush=True)
    refs=[Path(p) for p in cfg['ref']]
    for j in cfg['jobs']:
        out=Path(j['out'])
        if out.is_file() and out.stat().st_size>20000:print('have',out.name,flush=True);continue
        t=time.time()
        img=model.generate_image(seed=int(j.get('seed',7)),prompt=j['prompt'],width=int(j.get('w',576)),height=int(j.get('h',1024)),guidance=1.0,image_paths=refs,num_inference_steps=4,scheduler='flow_match_euler_discrete')
        img.save(path=str(out),export_json_metadata=False)
        print('made',out.name,round(time.time()-t),'s',flush=True)
if __name__=='__main__':main()
