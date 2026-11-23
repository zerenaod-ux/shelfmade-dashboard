"""Build one ShelfMade one-canvas whiteboard video: topic -> script (free AI) -> voice (free edge-tts, word times) -> canvas render.
Usage: python wb_build.py "topic" OUTDIR [minutes]    |   python wb_build.py --demo OUTDIR   (no AI, fixture script)
Test mode without network voice: WB_FAKE_VOICE=1 (silent audio, 0.36 s per word)."""
import json, os, re, sys, wave, subprocess
from pathlib import Path

VOICE0 = 1.0   # narration starts 1 s in, while the pencil writes the ShelfMade name
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
        import wb_voice
        return wb_voice.run(panels, work)
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
    lst = out_wav.with_name('concat.txt'); lead = out_wav.with_name('lead.wav')
    with wave.open(str(lead), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b'\x00\x00' * int(24000 * VOICE0))
    lst.write_text("file '%s'\n" % lead.resolve() + ''.join("file '%s'\nfile '%s'\n" % (Path(w).resolve(), sil.resolve()) for w in wavs))
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(out_wav)], capture_output=True, text=True)
    if r.returncode: raise RuntimeError('audio join failed: ' + r.stderr[-300:])


def make_spec(script, timings):
    panels, t0 = [], VOICE0; moods, punches, caps = [], [], []
    for p, tm in zip(script['panels'], timings):
        word_t = locate(tm['tokens'], p['sentences']); items = []
        for si, s in enumerate(p['sentences']):
            say = s['say'].strip(); ts = t0 + word_t[si][0]
            moods.append((ts, 'think' if say.endswith('?') else 'wow' if (say.endswith('!') or any(ch.isdigit() for ch in say)) else 'happy' if si == len(p['sentences']) - 1 else 'idle'))
            if say.endswith('!') or (any(ch.isdigit() for ch in say) and si % 2 == 0): punches.append(ts + 0.2)
            ws = say.split()
            for g in range(0, len(ws), 3):
                grp = ws[g:g + 3]; times = [t0 + word_t[si][g + q] for q in range(len(grp))]
                end = (t0 + word_t[si][g + 3]) if g + 3 < len(ws) else times[-1] + 0.9
                caps.append({'t0': times[0], 't1': end, 'words': grp, 'times': times})
            it = s.get('item')
            if not it: continue
            ws = [norm(w) for w in s['say'].split()]
            try: k = ws.index(norm(it['anchor']))
            except ValueError: k = 0
            d = dict(it); d.pop('anchor', None)
            d['t'] = t0 + max(0.0, word_t[si][0] - 0.05)   # the pen starts when the sentence starts and keeps drawing through it
            items.append(d)
        panels.append({'title': p['title'], 'tag': p.get('tag'), 'items': items, 'start': t0})
        t0 += tm['duration'] + GAP
    return {'duration': t0 + 1.5, 'panels': panels, 'moods': moods, 'punches': sorted(punches), 'captions': caps}


RULES = {'short': {'min': 40.0, 'max': 59.0, 'vertical': True}, 'long': {'min': 480.0, 'max': 598.0, 'vertical': False}}   # owner 2026-11-22: Short 40-60 s, long 8-10 min (total incl. name intro + subscribe card)
HASH = '#ShelfMade #learn #explained #didyouknow'


def fix_title(t):
    import re as _re
    t = _re.sub(r'\s+', ' ', str(t)).strip().strip('"')
    emo = _re.findall(r'[\U0001F300-\U0001FAFF\u2600-\u27BF]', t)
    t = _re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]', '', t).strip(' -:')
    if not _re.match(r'(?i)^(how|why)\b', t): t = 'Why ' + t[0].lower() + t[1:] if t else 'Why it works'
    return (t[:88] + ' ' + (emo[0] if emo else '\U0001F4A1')).strip()


def parent_line(script):
    try:
        h = json.loads((Path(__file__).parent / 'data' / 'wb-history.json').read_text())
        for x in h:
            if x['topic'] == script.get('topic') and x.get('parent'): return '\nThis is part 2 of: %s\n' % x['parent']
    except Exception: pass
    return ''


def post_text(script, spec, kind):
    title = fix_title(script['title']); sents = [s['say'] for p in script['panels'] for s in p['sentences']]
    if kind == 'short':
        return title + '\n\n' + ' '.join(sents[:2]) + parent_line(script) + '\nFollow ShelfMade for a new idea every day.\n\n' + HASH + '\n'
    ch, k = [], 0
    for pi, (p, sp) in enumerate(zip(script['panels'], spec['panels'])):
        if pi % 3 == 0:
            s = int(sp['start']) if pi else 0; ch.append('%d:%02d %s' % (s // 60, s % 60, p['title']))
    desc = ' '.join(sents[:3]) + '\n\nChapters:\n' + '\n'.join(ch) + parent_line(script) + '\nSubscribe to ShelfMade for a new idea every day.\n\n' + HASH
    return '--- TITLE ---\n' + title + '\n--- DESCRIPTION ---\n' + desc + '\n'


def build(script, outdir, fps=30, kind='long'):
    rule = RULES[kind]; vertical = rule['vertical']
    out = Path(outdir); work = out / 'work'; work.mkdir(parents=True, exist_ok=True)
    timings, wavs = voice(script['panels'], work)
    extra = 2.0 + 1.5 + 2.4 + VOICE0      # intro, spec tail, subscribe card
    while len(script['panels']) > 2 and VOICE0 + sum(t['duration'] + GAP for t in timings) + extra > rule['max']:
        k = max(1, len(script['panels']) // 2)   # drop a middle panel; hook and ending stay
        for l in (script['panels'], timings, wavs): del l[k]
    (out / 'script.json').write_text(json.dumps(script, indent=1))
    spec = make_spec(script, timings)
    import wb_cover, re as _re
    _t = fix_title(script['title']); _e = _re.findall(r'[\U0001F300-\U0001FAFF\u2600-\u27BF]', _t)
    spec['cover'] = {'title': _re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]', '', _t).strip(), 'emoji': _e[0] if _e else '\U0001F4A1'}
    spec['accent'] = list(wb_cover.accent_for(spec['cover']['title']))
    (out / 'spec.json').write_text(json.dumps(spec, indent=1))
    import canvas_whiteboard
    total = spec['duration'] + canvas_whiteboard.END
    if not rule['min'] <= total <= rule['max']:
        raise SystemExit('LENGTH %.0f s outside the %s rule %.0f-%.0f s: try again' % (total, kind, rule['min'], rule['max']))
    audio = work / 'narration.wav'; concat_audio(wavs, GAP, audio)
    import wb_sound
    canvas_whiteboard.configure(vertical)
    _r = canvas_whiteboard.Renderer(spec)
    import cv2; cv2.imwrite(str(out / 'cover.jpg'), _r.frame(canvas_whiteboard.INTRO - 0.05), [cv2.IMWRITE_JPEG_QUALITY, 92])
    ev = [(x['start'], x['dur'], x['kind']) for x in _r.items if x['kind'] != 'frame']
    ev += [(0.2, 1.4, 'text'), (spec['duration'] + 0.1, 1.8, 'text')]
    try:
        audio = wb_sound.mix(audio, ev, total, work / 'mixed.wav')
    except Exception as e:
        print('sound skipped:', e)
    mp4 = out / 'WHITEBOARD.mp4'
    canvas_whiteboard.render(spec, mp4, audio, fps=fps, vertical=vertical, progress=lambda i, n: print('render %d/%d' % (i, n), flush=True))
    (out / 'POST_THIS.txt').write_text(post_text(script, spec, kind))
    return mp4


def main(argv):
    kind = 'short' if 'short' in argv else 'long'
    argv = [a for a in argv if a not in ('short', 'long')]
    import wb_writer
    if argv and argv[0] == '--demo':
        script = dict(wb_writer.DEMO, panels=[wb_writer.clean_panel(p) for p in wb_writer.DEMO['panels']]); outdir = argv[1]
    else:
        topic, outdir = argv[0], argv[1]; minutes = float(argv[2]) if len(argv) > 2 else 9
        script = wb_writer.write(topic, 1 if kind == 'short' else minutes, short=(kind == 'short'), cache=os.environ.get('WB_CACHE'))
    print('BUILT', build(script, outdir, kind=kind))


if __name__ == '__main__':
    main(sys.argv[1:])
