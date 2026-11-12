"""TEST: ShelfMade FAST-CUT Short (owner: fast moves, a different picture for each line, no single picture for the whole video).
One idea from a public-domain book -> 7 short beats; each beat = one line + its OWN picture; quick zoom moves; quick 0.12 s cuts.
OLD: "idea as a changing picture" (style of the 'How to Invent a Dam' Short the owner liked).
One big idea from a public-domain book -> 6 beats; each beat = one narrated line + one image of the SAME scene changing; slow camera moves, cross-fades, one big word at a time.
  python story_art.py "<Book>" "<Author>" out/name.mp4
Free tools only: free LLM (llm.py), free image API (Pollinations; fallback listed in notes), edge-tts voice, ffmpeg."""
import json, os, sys, subprocess, urllib.request, urllib.parse, time, random, hashlib
from pathlib import Path
import llm, local_voice
W, H, FPS, XF = 720, 1280, 30, 0.12
STYLE = ', wide establishing shot of the whole scene from a high angle, cinematic 3D render, miniature diorama, bright soft light, sharp focus everywhere, rich colors, no text, no letters, no watermark'

def plan(book, author):
    sysm = 'You write viral educational Shorts. Return ONLY JSON.'
    p = ('Book: %s by %s (public domain). Pick the ONE most useful, surprising idea a modern viewer can use today and explain it in exactly 7 FAST beats. '
         'Each beat is a DIFFERENT picture that shows the thing named in that line (not one scene changing).\n'
         'Return JSON: {"title":"2-5 words, You/Your or Why statement, no yes/no question",'
         '"beats":[{"line":"one short spoken sentence (7-14 words), plain words, beat 1 speaks to the viewer with you/your","image":"one concrete picture that shows exactly what the line says, 15-25 words, one subject, no people close-ups"}]}\n'
         'Rules: 7 beats, total narration 70-100 words, last beat ties the idea to the viewer\'s day today, do not invent facts about the author, say "the book argues" for claims.')
    d = llm.json_call(sysm, p, temperature=0.8)
    assert len(d['beats']) >= 6, 'too few beats'
    return d

def fetch_image(prompt, seed, path):
    url = 'https://image.pollinations.ai/prompt/%s?width=%d&height=%d&nologo=true&seed=%d&model=flux' % (urllib.parse.quote(prompt), W, H, seed)
    last = ''
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120) as r:
                data = r.read()
            if len(data) > 5000:
                Path(path).write_bytes(data); return True
        except Exception as e:
            last = str(e)[:100]
        time.sleep(6 + 6 * k)
    print('image failed:', last, flush=True); return False

def sh(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(' '.join(a[:3]) + ' ' + r.stderr[-400:])

def ass_time(t): return '%d:%02d:%05.2f' % (int(t // 3600), int(t % 3600 // 60), t % 60)

def build(book, author, out):
    work = Path(out).with_suffix('.work'); work.mkdir(parents=True, exist_ok=True)
    d = plan(book, author); (work / 'plan.json').write_text(json.dumps(d, indent=1))
    seed = random.randint(1, 10**6); beats = d['beats'][:7]
    # voice per beat (exact length of each beat + word timings)
    jobs = [{'text': b['line'], 'wav': str(work / ('v%d.wav' % i)), 'timing': str(work / ('t%d.json' % i))} for i, b in enumerate(beats)]
    os.environ.setdefault('CE_EDGE_RATE', '+18%')
    local_voice.edge_run(jobs)
    durs = [json.loads(Path(j['timing']).read_text())['duration'] for j in jobs]
    # images
    for i, b in enumerate(beats):
        pr = '%s%s' % (b['image'], STYLE)
        if not fetch_image(pr, seed, work / ('i%d.jpg' % i)): raise RuntimeError('no image for beat %d' % i)
    # clips with slow camera move
    n = len(beats); clips = []
    for i in range(n):
        dur = durs[i] + (XF if i < n - 1 else 0.3) + 0.05; frames = int(dur * FPS) + 1
        z = "min(zoom+0.0030,1.22)" if i % 2 == 0 else "if(eq(on,1),1.22,max(zoom-0.0030,1.0))"
        x = "iw/2-(iw/zoom/2)+((on/%d)-0.5)*90" % frames
        sh('ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', str(work / ('i%d.jpg' % i)), '-vf',
           "scale=%d:%d:force_original_aspect_ratio=increase,crop=iw:ih*0.93:0:0,scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,scale=2160:-1,zoompan=z='%s':x='%s':y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=%d,format=yuv420p" % (W, H, W, H, W, H, z, x, frames, W, H, FPS),
           '-t', '%.2f' % dur, '-an', str(work / ('c%d.mp4' % i)))
        clips.append(work / ('c%d.mp4' % i))
    ins = []; [ins.extend(['-i', str(c)]) for c in clips]
    f = ''; last = '0:v'; off = 0.0
    for i in range(1, n):
        off += durs[i - 1] + 0.15 + XF - XF if False else 0
    off = 0.0
    for i in range(1, n):
        off += durs[i - 1] + 0.05
        f += '[%s][%d:v]xfade=transition=fade:duration=%.2f:offset=%.2f[x%d];' % (last, i, XF, off, i); last = 'x%d' % i
    # audio: voices back to back, each starts where its beat starts
    starts = []; t = 0.0
    for i in range(n): starts.append(t); t += durs[i] + 0.05
    total = t + 0.2
    # captions: one big word at a time
    ev = []
    for i in range(n):
        toks = json.loads(Path(jobs[i]['timing']).read_text())['tokens']
        for k, w in enumerate(toks):
            s = starts[i] + w['start']; e = starts[i] + (toks[k + 1]['start'] if k + 1 < len(toks) else w['end'] + 0.1)
            txt = w['text'].strip().upper().replace('{', '').replace('}', '')
            ev.append('Dialogue: 0,%s,%s,W,,,%s' % (ass_time(s), ass_time(e), txt))
    hdr = ('[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n'
           'Style: W,DejaVu Sans,86,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,2,5,40,40,0,1\n[Events]\nFormat: Layer,Start,End,Style,Name,Effect,Text\n' % (W, H))
    (work / 'cap.ass').write_text(hdr + '\n'.join(ev) + '\n')
    sh('ffmpeg', '-v', 'error', '-y', *sum([['-i', str(work / ('v%d.wav' % i))] for i in range(n)], []), '-filter_complex',
       ''.join('[%d:a]adelay=%d|%d[a%d];' % (i, int(starts[i] * 1000), int(starts[i] * 1000), i) for i in range(n)) + ''.join('[a%d]' % i for i in range(n)) + 'amix=inputs=%d:normalize=0[m]' % n, '-map', '[m]', str(work / 'voice.wav'))
    sh('ffmpeg', '-v', 'error', '-y', *ins, '-i', str(work / 'voice.wav'), '-filter_complex', f + '[%s]ass=%s[v]' % (last, str(work / 'cap.ass')), '-map', '[v]', '-map', '%d:a' % n,
       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(out))
    Path(out).with_suffix('.txt').write_text('Fast-cut test: 7 beats, each its own picture. Not posted.\n')
    print('DONE', out, 'title:', d.get('title'), 'seconds~%.0f' % total, flush=True)

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3])
