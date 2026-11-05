"""Makes before/after narration samples to listen to. Run with the Kokoro runtime python (see local_voice.RUNTIME)."""
import os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import local_voice as lv
os.environ['HF_HOME']=str(lv.WORK/'kokoro-models');os.environ['XDG_CACHE_HOME']=str(lv.WORK/'kokoro-cache');os.environ['HF_HUB_OFFLINE']='1'
from kokoro import KPipeline
import voice_frontend,voice_director,numpy as np,soundfile as sf
voice_frontend.configure()
pipe=KPipeline(lang_code='a',repo_id='hexgrad/Kokoro-82M',device='cpu')
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
TEXTS={
 'habit':"Why do we keep doing what we know will hurt us? Darwin believed habit was stronger than reason. He never saw it as weakness, only as inheritance. And yet, there is hope: a gentle change, repeated together, can reshape a life.",
 'fear':"Imagine a crowd, suddenly afraid. Nobody chose this. Nobody planned it. And in that silence, a single voice can change everything. Remember that, the next time you feel certain."
}
for name,t in TEXTS.items():
 parts=[a.numpy() if hasattr(a,'numpy') else a for _,_,a in pipe(t,voice='af_heart',speed=0.95)]
 sf.write(out/f'{name}_before.wav',np.concatenate(parts),24000,subtype='PCM_16')
 sf.write(out/f'{name}_after.wav',voice_director.render(pipe,t),24000,subtype='PCM_16')
 print('made',name)
