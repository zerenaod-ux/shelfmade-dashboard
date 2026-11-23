"""Build one ShelfMade one-canvas whiteboard video: topic -> script (free AI) -> voice (free edge-tts, word times) -> canvas render.
Usage: python wb_build.py "topic" OUTDIR [minutes]    |   python wb_build.py --demo OUTDIR   (no AI, fixture script)
Test mode without network voice: WB_FAKE_VOICE=1 (silent audio, 0.36 s per word)."""
import json, os, re, sys, wave, subprocess
from pathlib import Path

GAP = 1.4   # seconds of quiet between panels: the camera pulls back while the pen rests
RATE = '+8%'


def norm(w): return re.sub(r'[^a-z0-9]', '', w.lower())


def fake_voice(job):
    n = len(job['text'].split()); dur = n * 0.36
    with wave.open(str(job['wav']), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\x00\x00' * int(24000 * dur))
    toks = [{'text': t, 'start': i * 0.36, 'end': i * 0.36 + 0.3} for i, t in enumerate(job['text'].split())]
    Path(job['timing']).write_text(json.dumps({'tokens': toks, 'duration': dur}))


def voice(panels, work):
    jobs = [{'text': ' '.join(s['say'] for s in p['sentences']), 'wav': str(work / ('p%02d.wav' % i)), 'timing': str(work / ('p%02d.json' % i))} for i, p in enumerate(panels)]
    if os.environ.get('WB_FAKE_VOICE'):
        for j in jobs: fake_voice(j)
    else:
        import local_voice
        os.environ.setdefault('CE_EDGE_RATE', RATE)
        local_voice.edge_run(jobs)
    return [json.loads(Path(j['timing']).read_text()) for j in jobs], [j['wav'] for j in jobs]


def locate(tokens, sentences):
    """Start time of every word of every sentence (matched in order against the voice's word times)."""
    tn = [norm(t['text']) for t in tokens]; ptr = 0; out = []
    total_words = sum(len(s['say'].split()) for s in sentences) or 1; seen = 0
    dur = tokens[-1]['end'] if tokens else 1.0
    for s in sentences:
        row = []
        for w in s['say'].split():
            nw = norm(w); hit = None
            for k in range(ptr, min(len(tn), ptr + 5)):
                if tn[k] == nw or (nw and tn[k].startswith(nw[:4]) and len(nw) > 3):
                    hit = k; break
            if hit is not None:
                row.append(tokens[hit]['start']); ptr = hit + 1
            else:
                row.append(dur * seen / total_words)
            seen += 1
        out.append(row)
    return out


def concat_audio(wavs, gap, out_wav):
    sil = out_wav.with_name('gap.wav')
    with wave.open(str(sil), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\x00\x00' * int(24000 * gap))
    lst = out_wav.with_name('concat.txt')
    lst.write_text(''.join("file '%s'\nfile '%s'\n" % (Path(w).resolve(), sil.resolve()) for w in wavs))
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(out_wav)], capture_output=True, text=True)
    if r.returncode: raise RuntimeError('audio join failed: ' + r.stderr[-300:])


def make_spec(script, timings):
    panels, t0 = [], 0.0
    for p, tm in zip(script['panels'], timings):
        word_t = locate(tm['tokens'], p['sentences']); items = []
        for si, s in enumerate(p['sentences']):
            it = s.get('item')
            if not it: continue
            ws = [norm(w) for w in s['say'].split()]
            try: k = ws.index(norm(it['anchor']))
            except ValueError: k = 0
            d = dict(it); d.pop('anchor', None)
            d['t'] = t0 + max(0.0, word_t[si][k] - 0.1)
            items.append(d)
        panels.append({'title': p['title'], 'tag': p.get('tag'), 'items': items, 'start': t0})
        t0 += tm['duration'] + GAP
    return {'duration': t0 + 1.5, 'panels': panels}


def build(script, outdir, fps=30):
    out = Path(outdir); work = out / 'work'; work.mkdir(parents=True, exist_ok=True)
    (out / 'script.json').write_text(json.dumps(script, indent=1))
    timings, wavs = voice(script['panels'], work)
    spec = make_spec(script, timings); (out / 'spec.json').write_text(json.dumps(spec, indent=1))
    audio = work / 'narration.wav'; concat_audio(wavs, GAP, audio)
    import canvas_whiteboard
    mp4 = out / 'WHITEBOARD.mp4'
    canvas_whiteboard.render(spec, mp4, audio, fps=fps, progress=lambda i, n: print('render %d/%d' % (i, n), flush=True))
    (out / 'POST_THIS.txt').write_text(script['title'] + '\n\n' + ' '.join(s['say'] for p in script['panels'] for s in p['sentences'][:2])[:400] + '\n')
    return mp4


def main(argv):
    if argv and argv[0] == '--demo':
        import wb_writer; script = dict(wb_writer.DEMO, panels=[wb_writer.clean_panel(p) for p in wb_writer.DEMO['panels']]); outdir = argv[1]
    else:
        import wb_writer
        topic, outdir = argv[0], argv[1]; minutes = float(argv[2]) if len(argv) > 2 else 8
        script = wb_writer.write(topic, minutes)
    print('BUILT', build(script, outdir))


if __name__ == '__main__':
    main(sys.argv[1:])
