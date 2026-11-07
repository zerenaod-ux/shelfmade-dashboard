"""Two emotional character voices (free, local Qwen3-TTS). Run with the tts-lab python.
stdin: {"jobs":[{"who":"leo|mia","text":..,"feel":..,"wav":path}]}. Leo = 'Ryan', Mia = 'Vivian'."""
import json,sys
from pathlib import Path
import numpy as np
MODEL="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16";SR=24000
SPK={'leo':'Ryan','mia':'Vivian'}
PACE="Talk at a quick, natural conversational pace like a real friend chatting, casual and unscripted, with short natural pauses, never like a narrator or announcer. "   # PACE
BASE={'leo':"A young man in his twenties, an overthinking, lovable goofball. "+PACE,
      'mia':"A young woman in her twenties, dry-witted, kind and quick. "+PACE}
FEEL={'confident':"Speak confidently and a little too sure of himself.",'deadpan':"Speak flat and deadpan with a hint of amusement, dry timing.",
 'sheepish':"Speak sheepishly and defensively, a bit embarrassed.",'panicked':"Speak in rising panic, fast and high-pitched, comically alarmed.",
 'tired':"Speak exhausted and drained, slow and slurred.",'warm':"Speak warmly and gently, with a smile in the voice.",
 'excited':"Speak with bright excitement like explaining something cool to a friend.",'hopeful':"Speak with hopeful, wide-eyed sincerity.",
 'anxious':"Speak anxiously and nervously, fast and tense.",'dramatic':"Speak with theatrical over-the-top drama.",
 'amused':"Speak with a playful amused smile, light teasing.",'smug':"Speak smugly and delighted with herself.",
 'surprised':"Speak with genuine surprise and wonder.",'realizing':"Speak slowly as a realization dawns, quiet and amazed.",
 'grim':"Speak grimly and flatly, disappointed.",'curious':"Speak with curious rising intonation.",'determined':"Speak with stubborn determination.",
 'strained':"Speak strained through gritted teeth, politely suffering.",'relieved':"Speak with a big relieved sigh in the voice.",
 'happy':"Speak happily and cheerfully.",'skeptical':"Speak skeptically, one eyebrow raised.",'sleepy':"Speak sleepily, soft and slow.",
 'serious':"Speak with absurdly serious gravity.",'curious ':"Speak with curious rising intonation."}
def main():
    job=json.loads(sys.stdin.read())
    from mlx_audio.tts.utils import load_model
    import soundfile as sf
    model=load_model(MODEL)
    try:avail=[x.lower() for x in model.get_supported_speakers()]
    except Exception:avail=[]
    print('speakers:',avail,flush=True)
    def pick(pref):
        for p in pref:
            if not avail or p.lower() in avail:return p
        return pref[0]
    SPK['leo']=pick(['Ryan','Aiden','Eric','Dylan']);SPK['mia']=pick(['Vivian','Serena','Ono_Anna'])
    print('voices:',SPK,flush=True)
    for j in job['jobs']:
        out=Path(j['wav'])
        if out.is_file() and out.stat().st_size>2000:print('have',out.name,flush=True);continue
        instruct=BASE[j['who']]+FEEL.get(j.get('feel','warm'),FEEL['warm'])
        parts=[]
        for r in model.generate_custom_voice(text=j['text'],speaker=SPK[j['who']],language='English',instruct=instruct):
            a=np.array(getattr(r,'audio',r),dtype='float32').reshape(-1);sr=int(getattr(r,'sample_rate',SR) or SR)
            if sr!=SR:a=np.interp(np.linspace(0,len(a)-1,int(len(a)*SR/sr)),np.arange(len(a)),a).astype('float32')
            parts.append(a)
        if not parts:raise RuntimeError('no audio for: '+j['text'][:50])
        a=np.concatenate(parts);pk=float(np.max(np.abs(a)))or 1.0
        if pk>0.95:a=a*(0.95/pk)
        sf.write(str(out),a,SR,subtype='PCM_16');print('made',out.name,round(len(a)/SR,1),flush=True)
if __name__=='__main__':main()
