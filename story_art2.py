"""ShelfMade 'living picture' Short, v2 (owner: 'think big, real live movement'). Runs in GitHub Actions + the free Kaggle GPU.
  python story_art2.py "<Book>" "<Author>" out/name.mp4
plan (free LLM) -> voice per beat (edge-tts) -> Kaggle: FLUX.2 klein pictures (each beat EDITS the previous one) + LTX-Video clips -> ffmpeg: clips stretched to the voice, cross-fades, one big word at a time."""
import json, os, sys, shutil, subprocess, time, random
from pathlib import Path
import llm, local_voice
from story_art import sh, ass_time
W, H, FPS, XF = 720, 1280, 30, 0.4
USER = 'minddoodles'; KERNEL = 'shelf-art'
E = dict(os.environ)
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def kg(*a):
    code = 'import sys;from kaggle.cli import main;sys.argv=["kaggle"]+sys.argv[1:];main()'
    r = subprocess.run([sys.executable, '-c', code, *a], capture_output=True, text=True, env=E); return (r.stdout + r.stderr).strip()

def plan(book, author):
    p = ('Book: %s by %s (public domain). Pick the ONE most useful, surprising idea a modern viewer can use today and tell it as a 6-beat VISUAL STORY, like the viral Short "How to Invent a Dam": '
         'one physical scene whose objects visibly CHANGE and GROW beat by beat so the picture itself explains the idea (e.g. a bare hill -> a path appears -> a bridge -> a city).\n'
         'Return ONLY JSON: {"title":"2-5 words, You/Your or Why statement, not a yes/no question","scene_prompt":"one vivid sentence describing the starting scene (concrete, physical, no close-up faces)",'
         '"beats":[{"line":"1-2 short spoken sentences (10-20 words), plain words; beat 1 speaks to the viewer with you/your","image":"what the picture shows or what CHANGES in it at this beat: a BIG, obvious, concrete visual change (beat 1: the starting state), 15-25 words","motion":"what moves in the clip, 8-12 words (camera move + natural motion)"}]}\n'
         'Rules: exactly 6 beats, narration 90-115 words total, last beat links the idea to the viewer\'s day, say "the book argues" for claims, never invent facts about the author.')
    d = llm.json_call('You write viral educational Shorts. Return ONLY JSON.', p, temperature=0.8)
    assert len(d['beats']) >= 5; d['beats'] = d['beats'][:6]; return d

def kaggle_stage(d, work):
    ins = work / 'k_in'; shutil.rmtree(ins, ignore_errors=True); ins.mkdir()
    (ins / 'jobs.json').write_text(json.dumps({'beats': d['beats'], 'scene_prompt': d['scene_prompt'], 'seed': random.randint(1, 9999),
        'style': ', cinematic 3D render, miniature diorama, bright soft light, rich colors, sharp focus, no text, no watermark, vertical 9:16'}))
    slug = 'shelf-art-' + time.strftime('%d%H%M%S'); (ins / 'dataset-metadata.json').write_text(json.dumps({'title': slug.replace('-', ' '), 'id': f'{USER}/{slug}', 'licenses': [{'name': 'CC0-1.0'}]}))
    for a in range(5):
        r = kg('datasets', 'create', '-p', str(ins)); log(r[-100:])
        if 'error' not in r.lower() and 'problem' not in r.lower(): break
        time.sleep(40)
    else: raise SystemExit('Kaggle dataset upload failed')
    for i in range(60):
        if 'ready' in kg('datasets', 'status', f'{USER}/{slug}').lower(): break
        time.sleep(10)
    kd = work / 'k_kernel'; kd.mkdir(exist_ok=True); shutil.copy(Path(__file__).with_name('shelf_art_kernel.py'), kd / 'shelf_art_kernel.py')
    (kd / 'kernel-metadata.json').write_text(json.dumps({'id': f'{USER}/{KERNEL}', 'title': 'shelf art', 'code_file': 'shelf_art_kernel.py', 'language': 'python', 'kernel_type': 'script',
        'is_private': True, 'enable_gpu': True, 'enable_internet': True, 'dataset_sources': [f'{USER}/{slug}'], 'competition_sources': [], 'kernel_sources': [], 'model_sources': []}))
    log('starting free GPU'); log(kg('kernels', 'push', '-p', str(kd))[-200:]); t0 = time.time()
    while True:
        time.sleep(45); s = kg('kernels', 'status', f'{USER}/{KERNEL}').lower(); log(s[-50:])
        if 'complete' in s or 'error' in s or 'cancel' in s or 'fail' in s: break
        if time.time() - t0 > 3 * 3600: raise SystemExit('kernel timeout')
    tmp = work / 'k_out'; shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(); kg('kernels', 'output', f'{USER}/{KERNEL}', '-p', str(tmp))
    for f in tmp.rglob('*'):
        if f.is_file() and (f.suffix in ('.mp4', '.png', '.txt')): shutil.copy(f, work / f.name)
    if (work / 'log.txt').exists(): print('--- KAGGLE LOG ---\n' + (work / 'log.txt').read_text()[-3000:], flush=True)

def build(book, author, out):
    work = Path(out).with_suffix('.work'); work.mkdir(parents=True, exist_ok=True)
    d = plan(book, author); (work / 'plan.json').write_text(json.dumps(d, indent=1)); beats = d['beats']; n = len(beats)
    jobs = [{'text': b['line'], 'wav': str(work / ('v%d.wav' % i)), 'timing': str(work / ('t%d.json' % i))} for i, b in enumerate(beats)]
    os.environ.setdefault('CE_EDGE_RATE', '+10%'); local_voice.edge_run(jobs)
    durs = [json.loads(Path(j['timing']).read_text())['duration'] for j in jobs]
    kaggle_stage(d, work)
    starts = []; t = 0.0
    for i in range(n): starts.append(t); t += durs[i] + 0.15
    clips = []
    for i in range(n):
        dur = durs[i] + 0.15 + (XF if i < n - 1 else 0.3); c = work / ('c%d.mp4' % i); src = work / ('clip_%02d.mp4' % i); pic = work / ('pic_%02d.png' % i)
        vf = 'scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=%d,format=yuv420p' % (W, H, W, H, FPS)
        if src.exists():   # live clip stretched to the beat (slow-motion look), last frame held if the beat is longer
            r = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(src)], capture_output=True, text=True).stdout.strip() or 2.7)
            f = max(1.0, min(2.2, dur / r))
            sh('ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf', 'setpts=%.3f*PTS,%s,tpad=stop_mode=clone:stop_duration=%.2f' % (f, vf, dur), '-t', '%.2f' % dur, '-an', str(c))
        elif pic.exists():   # fallback: still picture with slow zoom
            fr = int(dur * FPS) + 1
            sh('ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', str(pic), '-vf', "scale=2160:-1,zoompan=z='min(zoom+0.0008,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=%d,format=yuv420p" % (fr, W, H, FPS), '-t', '%.2f' % dur, '-an', str(c))
        else: raise RuntimeError('no picture or clip for beat %d' % i)
        clips.append(c)
    ins = []; [ins.extend(['-i', str(c)]) for c in clips]; f = ''; last = '0:v'; off = 0.0
    for i in range(1, n):
        off += durs[i - 1] + 0.15; f += '[%s][%d:v]xfade=transition=fade:duration=%.2f:offset=%.2f[x%d];' % (last, i, XF, off, i); last = 'x%d' % i
    ev = []
    for i in range(n):
        toks = json.loads(Path(jobs[i]['timing']).read_text())['tokens']
        for k, w in enumerate(toks):
            s = starts[i] + w['start']; e = starts[i] + (toks[k + 1]['start'] if k + 1 < len(toks) else w['end'] + 0.1)
            ev.append('Dialogue: 0,%s,%s,W,,,%s' % (ass_time(s), ass_time(e), w['text'].strip().upper().replace('{', '').replace('}', '')))
    hdr = ('[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n'
           'Style: W,DejaVu Sans,86,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,2,5,40,40,0,1\n[Events]\nFormat: Layer,Start,End,Style,Name,Effect,Text\n' % (W, H))
    (work / 'cap.ass').write_text(hdr + '\n'.join(ev) + '\n')
    sh('ffmpeg', '-v', 'error', '-y', *sum([['-i', str(work / ('v%d.wav' % i))] for i in range(n)], []), '-filter_complex',
       ''.join('[%d:a]adelay=%d|%d[a%d];' % (i, int(starts[i] * 1000), int(starts[i] * 1000), i) for i in range(n)) + ''.join('[a%d]' % i for i in range(n)) + 'amix=inputs=%d:normalize=0[m]' % n, '-map', '[m]', str(work / 'voice.wav'))
    sh('ffmpeg', '-v', 'error', '-y', *ins, '-i', str(work / 'voice.wav'), '-filter_complex', f + '[%s]ass=%s[v]' % (last, str(work / 'cap.ass')), '-map', '[v]', '-map', '%d:a' % n,
       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(out))
    live = sum(1 for i in range(n) if (work / ('clip_%02d.mp4' % i)).exists())
    print('DONE', out, 'title:', d.get('title'), 'live clips: %d/%d' % (live, n), flush=True)

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3])
