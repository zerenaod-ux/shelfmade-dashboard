"""Expressive narration for whiteboard videos (free edge-tts). Every sentence is spoken on its own with its own energy:
hook = punchy, question = rising, exclamation = fast and loud, order/suggestion = firm, ending = warm and slower; small human pauses between sentences.
run(panels, work) -> (timings per panel [{'tokens','duration'}], wav paths)."""
import asyncio, json, re, subprocess, wave
from pathlib import Path
import numpy as np

SR = 24000
VOICES = ['en-US-AndrewMultilingualNeural', 'en-US-AndrewNeural', 'en-US-GuyNeural', 'en-US-JennyNeural']
BASE_RATE = 14   # percent faster than normal: energetic, fast, still clear
ORDER = re.compile(r"^(start|stop|do|don't|pick|try|move|open|set|write|put|make|keep|save|take|use|check|look|ask|tell|give|go|build|plan|cut|skip|never|always|remember|imagine|picture|think)\b", re.I)


def prosody(s, i, n, first_panel):
    """Return (rate %, pitch Hz, volume %, pause seconds after) for one sentence."""
    t = s.strip(); rate, pitch, vol, pause = BASE_RATE, 3, 4, 0.22
    if t.endswith('?'): rate, pitch, vol, pause = BASE_RATE - 2, 10, 6, 0.38      # real question: voice lifts, then a beat
    elif t.endswith('!'): rate, pitch, vol, pause = BASE_RATE + 8, 8, 12, 0.30    # excited
    elif ORDER.match(t) or re.search(r'\b(today|right now|this week|tonight)\b', t, re.I): rate, pitch, vol, pause = BASE_RATE + 2, 1, 10, 0.34   # firm suggestion/order
    elif re.search(r'\d', t): rate, pitch, vol = BASE_RATE + 4, 5, 8                 # numbers get punch
    if first_panel and i == 0: rate, pitch, vol, pause = BASE_RATE + 8, 6, 12, 0.35   # hook: grab in 3 seconds
    if i == n - 1: rate, pitch, vol, pause = rate - 6, max(-2, pitch - 4), vol, 0.12  # panel ending: warmer, slower
    if re.search(r'\b(but|then|suddenly|except|until)\b', t, re.I) and not t.endswith(('?', '!')): pitch += 2
    return rate, pitch, vol, pause


async def _one(text, voice, rate, pitch, vol):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate='%+d%%' % rate, pitch='%+dHz' % pitch, volume='%+d%%' % vol, boundary='WordBoundary')
    audio, words = bytearray(), []
    async for ch in com.stream():
        if ch['type'] == 'audio': audio += ch['data']
        elif ch['type'] == 'WordBoundary': words.append((ch['text'], ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7))
    if not audio: raise RuntimeError('no audio')
    return bytes(audio), words


def _pcm(mp3):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-ar', str(SR), '-ac', '1', '-f', 's16le', 'pipe:1'], input=mp3, capture_output=True)
    if r.returncode: raise RuntimeError('decode failed')
    return np.frombuffer(r.stdout, np.int16)


def _say(text, voice, pr):
    last = None
    for a in range(4):
        try: return asyncio.run(_one(text, voice, *pr))
        except Exception as e:
            last = e; import time; time.sleep(2 + 3 * a)
    raise RuntimeError('voice failed: ' + str(last)[:200])


def pick_voice():
    for v in VOICES:
        try:
            asyncio.run(_one('Okay, here we go.', v, 10, 0, 0)); return v
        except Exception:
            continue
    raise RuntimeError('no edge voice available')


def run(panels, work, voice=None):
    work = Path(work); voice = voice or pick_voice(); print('voice:', voice, flush=True)
    timings, wavs = [], []
    for pi, p in enumerate(panels):
        sents = [s['say'] for s in p['sentences']]; chunks, tokens, t = [], [], 0.0
        for i, s in enumerate(sents):
            rate, pitch, vol, pause = prosody(s, i, len(sents), pi == 0)
            mp3, words = _say(s, voice, (rate, pitch, vol)); pcm = _pcm(mp3)
            for w, a, b in words: tokens.append({'text': w, 'start': t + a, 'end': t + b})
            gap = np.zeros(int(pause * SR), np.int16); chunks += [pcm, gap]; t += len(pcm) / SR + pause
        data = np.concatenate(chunks) if chunks else np.zeros(SR, np.int16)
        wav = work / ('p%02d.wav' % pi)
        with wave.open(str(wav), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.astype('<i2').tobytes())
        timings.append({'tokens': tokens, 'duration': len(data) / SR}); wavs.append(str(wav))
        (work / ('p%02d.json' % pi)).write_text(json.dumps(timings[-1]))
    return timings, wavs
