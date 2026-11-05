"""Draw each speaker's 'mouth open, mid-sentence' version of every shot with the same free picture model (FLUX.2 klein edit).
render.py then blends only the mouth area between the closed and open pictures along the voice loudness - so the mouth is the real drawn mouth.
Run with the img-lab python: python3 mouthvar.py <workdir>   (resumable, ~90 s per picture)"""
import json,sys,time
from pathlib import Path
NAME={'leo':'Leo (the young man with dark curly hair and yellow hoodie)','mia':'Mia (the young woman with the short dark bob and teal sweater)'}
def main():
    work=Path(sys.argv[1]);st=json.loads((work/'story.json').read_text())
    closed=[x for x in (sys.argv[sys.argv.index('--closed')+1].split(',') if '--closed' in sys.argv else []) if x]
    from mflux.models.flux2.variants import Flux2KleinEdit
    model=Flux2KleinEdit(quantize=8);t00=time.time()
    if closed:
        for c in closed:
            si=int(c.split(':')[0]);who=c.split(':')[1];src=work/f'shot_{si:02d}.png';out=work/f'closed_{si:02d}_{who}.png'
            if out.is_file():continue
            p=("Edit this exact picture. Keep everything identical: same characters, same poses, same camera, same lighting, same background, same clothes, same hair. "
               f"Only change: {NAME[who]} now has a closed mouth with lips together and no teeth showing, a gentle small closed-lip smile. Nothing else changes.")
            img=model.generate_image(seed=500+si,prompt=p,width=576,height=1024,guidance=1.0,image_paths=[src],num_inference_steps=4,scheduler='flow_match_euler_discrete');img.save(path=str(out),export_json_metadata=False);print('made',out.name,flush=True)
        print('CLOSED DONE',flush=True);return
    for si,sh in enumerate(st['shots']):
        src=work/f'shot_{si:02d}.png'
        for who in dict.fromkeys(l['who'] for l in sh['lines']):
            out=work/f'open_{si:02d}_{who}.png'
            if out.is_file() and out.stat().st_size>20000:print('have',out.name,flush=True);continue
            p=("Edit this exact picture. Keep everything identical: same characters, same poses, same camera, same lighting, same background, same clothes, same hair, same expression direction. "
               f"Only change: {NAME[who]} now has the mouth open wide in the middle of speaking, upper teeth slightly visible. Nothing else changes.")
            t=time.time()
            img=model.generate_image(seed=300+si,prompt=p,width=576,height=1024,guidance=1.0,image_paths=[src],num_inference_steps=4,scheduler='flow_match_euler_discrete')
            img.save(path=str(out),export_json_metadata=False);print('made',out.name,round(time.time()-t),'s',flush=True)
    print('MOUTHVAR DONE',round(time.time()-t00),'s',flush=True)
if __name__=='__main__':main()
