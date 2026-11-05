#!/usr/bin/env python3
"""
Content Empire — REAL end-to-end video generator (standalone proof).

Produces a polished faceless vertical (9:16) video from a topic using only
FREE local tools (plus your Claude key if you set CLAUDE_API_KEY):

  • Script   : Claude API if CLAUDE_API_KEY is set, else a built-in template
  • Voiceover: macOS `say` (free) → MP3
  • Frames   : Pillow — gradient backgrounds, bold type, progress bar, brand
  • Subtitles: estimated SRT burned into the video (huge for watch time)
  • Music    : soft self-generated ambient bed mixed under the voice
  • Assembly : ffmpeg → final MP4

Run:
    python3 make_video.py "Why the stock market drops in September"
    python3 make_video.py            # default topic

Output:
    demo/output/<slug>/final.mp4
"""

import os, sys, re, json, subprocess, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─── Secure key loading ─────────────────────────────────────────────────────
def _load_env():
    """Load KEY=VALUE pairs from demo/.env into the environment (if present).
    Keeps secrets out of code and out of chat. .env is gitignored."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
# Paid credentials deliberately not loaded in the local worker.

W, H   = 1080, 1920
BRAND  = (255, 107, 53)
ASSETS = Path(__file__).parent / "assets"
OUT    = Path(__file__).parent / "output"

def load_font(size, bold=True):
    for c in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if os.path.exists(c):
            try: return ImageFont.truetype(c, size)
            except Exception: pass
    return ImageFont.load_default()

# ─────────────────────────── 1. SCRIPT ─────────────────────────────────────
def write_script(topic):
    key = os.environ.get("CLAUDE_API_KEY")
    if key:
        try: return claude_script(topic, key)
        except Exception as e: print(f"  ⚠️  Claude failed ({e}); using template.")
    return {
        "hook": "Did you know?",
        "title": topic,
        "points": [
            "Most people get this completely wrong.",
            "Here is what actually moves the market.",
            "Smart money positions before the crowd reacts.",
        ],
        "cta": "Follow for daily market insights.",
    }

def claude_script(topic, key):
    """Research + write a fact-rich, viral-structured faceless script."""
    system = (
        "You are an elite short-form video writer who studies retention. "
        "You know the first 2 seconds decide everything. Your hooks create an "
        "open curiosity loop the viewer NEEDS resolved, so they keep watching. "
        "Every line earns the next second. You write accurate, specific, "
        "faceless scripts — no human name, no first-person story, no fluff. "
        "You front-load the single most shocking, counter-intuitive fact.")
    prompt = (
        f"Topic: {topic}\n\n"
        "Write a 30-45 second vertical video script ENGINEERED FOR RETENTION.\n\n"
        "HOOK RULES (most important): the hook must be a scroll-stopping line "
        "that opens a curiosity gap — a shocking claim, a 'most people don't "
        "know', a bold number, or a 'stop doing X'. It must make scrolling away "
        "feel like missing out.\n\n"
        "Then each point must escalate and tease the next (mini cliffhangers).\n\n"
        "Return STRICT JSON:\n"
        "- hook: one scroll-stopping line (max 8 words)\n"
        "- title: the core promise/idea (one line)\n"
        "- points: 4 punchy, specific, fact-driven sentences that each make the "
        "viewer want the next one\n"
        "- cta: one line driving a comment or follow\n"
        "- bquery: 2-3 word stock-video search term that visually matches the "
        "topic (e.g. 'stock market chart', 'ocean waves', 'city night')\n"
        "JSON only, no markdown.")
    body = json.dumps({
        "model":"claude-opus-4-5","max_tokens":900,"system":system,
        "messages":[{"role":"user","content":prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key":key,"anthropic-version":"2023-06-01",
                 "content-type":"application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    text = re.sub(r"^```json|```$","",data["content"][0]["text"].strip()).strip()
    out = json.loads(text)
    print("       ✨ script written by Claude (researched)")
    return out

# ─────────────────────────── 2. FRAMES ─────────────────────────────────────
def gradient_bg(accent):
    """Vertical dark→accent gradient background."""
    base = Image.new("RGB", (W, H), (12, 12, 16))
    top = (12, 12, 16); bot = tuple(int(c*0.28) for c in accent)
    for y in range(H):
        t = y / H
        r = int(top[0]*(1-t) + bot[0]*t)
        g = int(top[1]*(1-t) + bot[1]*t)
        b = int(top[2]*(1-t) + bot[2]*t)
        for x in range(0, W, W):  # one fill per row
            pass
        Image.new
    # faster: build with numpy-free row paste
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / H
        grad.putpixel((0, y), (
            int(top[0]*(1-t)+bot[0]*t),
            int(top[1]*(1-t)+bot[1]*t),
            int(top[2]*(1-t)+bot[2]*t)))
    return grad.resize((W, H))

def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur+" "+w).strip()
        if draw.textlength(test, font=font) <= max_w: cur = test
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def _extract_visual_query(text, kind, base_query):
    """Turn a segment's spoken text + type into a cinematic Pexels search query.
    The hook gets dramatic/mysterious. Points pull concrete nouns from what's spoken.
    CTA gets wide/inspiring. Each segment is visually distinct."""
    import re
    stop = {
        'the','a','an','is','are','was','were','be','been','being','have','has',
        'had','do','does','did','will','would','could','should','may','might',
        'must','shall','can','your','my','our','its','their','this','that',
        'these','those','and','or','but','not','with','at','by','for','from',
        'in','on','to','of','what','when','where','who','how','why','all',
        'more','most','very','just','even','so','as','than','here','there',
        'then','about','into','during','after','before','above','some','such',
        'also','each','than','them','they','make','like','know','think','want',
        'people','things','every','follow','shelfmade','mindlore','daily',
        'book','fact','classic','mind','life','time','year','ways','thing',
    }
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    keywords = [w for w in words if w not in stop]
    base0 = base_query.split()[0] if base_query else ""
    base1 = " ".join(base_query.split()[:2]) if base_query else ""

    if kind == 'hook':
        # First second = most captivating — dark, dramatic, mysterious
        top = keywords[:2] if keywords else [base0]
        return f"{' '.join(top)} dark dramatic mysterious cinematic"

    if kind == 'title':
        # Wide establishing shot — epic reveal of the world
        return f"{base1} epic wide cinematic golden"

    if kind == 'cta':
        # Close on something inspiring/beautiful
        return f"{base0} light horizon inspiring wide beautiful"

    # Points 1-4: pull the most concrete/visual nouns from what's actually being said
    # Prefer longer words (more specific), de-dupe with base_query words
    base_words = set(base_query.lower().split())
    specific = [w for w in keywords if w not in base_words][:2]
    general  = [w for w in keywords if w in base_words][:1]
    top = (specific + general)[:3] or base_query.split()[:3]
    return " ".join(top)


def _pexels_video_one(query, folder, idx, fallback=None):
    """Download ONE Pexels clip matching query. Uses idx to vary result selection
    so repeated calls with the same query return different clips. Returns raw path."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key: return None
    import urllib.parse
    for attempt_q in ([query] + ([fallback] if fallback and fallback != query else [])):
        try:
            eq = urllib.parse.quote_plus(attempt_q)
            url = (f"https://api.pexels.com/videos/search"
                   f"?query={eq}&per_page=10&orientation=landscape")
            req = urllib.request.Request(
                url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            vids = [v for v in data.get("videos", []) if v.get("duration", 0) >= 4]
            if not vids: continue
            # Rotate through results so each segment gets a genuinely different clip
            vid = vids[idx % len(vids)]
            files = sorted(vid["video_files"], key=lambda f: f.get("width",0), reverse=True)
            pick = next((f for f in files if 720 <= f.get("width",0) <= 1920), files[0])
            raw = folder / f"raw_{idx:02d}.mp4"
            with urllib.request.urlopen(urllib.request.Request(
                    pick["link"], headers={"User-Agent": "Mozilla/5.0"}),
                    timeout=120) as r:
                raw.write_bytes(r.read())
            return str(raw)
        except Exception:
            continue
    return None


def _build_segmented_montage(seg_infos, folder):
    """The cinematic engine: each script segment gets its OWN content-matched clip.
    Clips are sped up (hook slightly slower for mystery, rest at 1.4×), then joined
    with smooth crossfade dissolves between every scene change.
    seg_infos: [(kind, text, duration_secs, base_query), ...]
    Returns path to finished portrait montage mp4."""
    FADE = 0.35   # crossfade duration between segments (seconds)

    clips = []    # (path, actual_duration)
    for i, (kind, text, target_dur, base_query) in enumerate(seg_infos):
        query = _extract_visual_query(text, kind, base_query)
        raw   = _pexels_video_one(query, folder, i, fallback=base_query)
        if not raw:
            raw = _pexels_video_one(base_query, folder, 100 + i)
        if not raw:
            continue

        # Hook: slightly slower → builds tension; rest: 1.4× → energetic
        speed = 0.88 if kind == 'hook' else 0.72
        # How much raw footage we need to fill target_dur after speed-up
        raw_need = (target_dur + FADE + 1.5) / speed
        # Skip into the video to avoid boring static openings
        skip = 0.2 if kind == 'hook' else 1.5

        clip = folder / f"seg_{i:02d}.mp4"
        r = subprocess.run([
            "ffmpeg", "-y", "-ss", str(skip), "-i", raw,
            "-t", str(raw_need),
            "-vf", (f"crop=ih*9/16:ih,"
                    f"scale={W}:{H}:force_original_aspect_ratio=disable,"
                    f"setpts={speed:.3f}*PTS"),
            "-c:v", "libx264", "-preset", "veryfast", "-an", "-r", "30",
            str(clip)
        ], capture_output=True)

        if r.returncode == 0 and clip.exists() and clip.stat().st_size > 5000:
            # Measure actual clip duration after processing
            dr = subprocess.run(
                ["ffprobe","-v","error","-show_entries","format=duration",
                 "-of","default=noprint_wrappers=1:nokey=1", str(clip)],
                capture_output=True, text=True)
            actual = float(dr.stdout.strip()) if dr.stdout.strip() else target_dur + 2
            clips.append((str(clip), actual))
            print(f"       🎬  seg {i} ({kind:6}): '{query[:40]}' → {actual:.1f}s")

    if not clips:
        return None

    if len(clips) == 1:
        return clips[0][0]

    # ── Assemble with crossfade dissolves between every scene ──
    # xfade offset = cumulative duration of previous clips minus overlap already taken
    inputs = []
    for p, _ in clips:
        inputs += ["-i", p]

    cumulative = 0.0
    filter_parts = []
    prev = "[0:v]"
    for i in range(1, len(clips)):
        cumulative += clips[i-1][1] - FADE
        out = f"[x{i}]" if i < len(clips) - 1 else "[vout]"
        filter_parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:"
            f"duration={FADE}:offset={cumulative:.3f}{out}"
        )
        prev = out

    montage = folder / "video_bg.mp4"
    cmd = (["ffmpeg", "-y"] + inputs +
           ["-filter_complex", ";".join(filter_parts),
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "fast", "-an",
            str(montage)])
    r = subprocess.run(cmd, capture_output=True)

    if r.returncode != 0:
        # Fallback: simple concat (no crossfades) if xfade fails
        lst = folder / "montage_list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p, _ in clips))
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c:v", "libx264", "-preset", "fast",
                        "-an", str(montage)], capture_output=True)

    return str(montage) if montage.exists() else None

def _pexels_photo(query, folder, idx):
    """Download a relevant vertical photo from Pexels (free API key).
    Returns a path, or None if no key / not found."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        import urllib.parse
        # bias toward calm, simple, minimal backdrops (less busy = cleaner)
        q = f"{query} minimal calm dark"
        url = ("https://api.pexels.com/v1/search?per_page=20&orientation=portrait&query="
               + urllib.parse.quote(q))
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": ua})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        photos = data.get("photos", [])
        if not photos:
            return None
        # prefer darker photos (avg_color closer to dark) for readability
        def darkness(p):
            c = (p.get("avg_color") or "#888888").lstrip("#")
            try: return sum(int(c[i:i+2],16) for i in (0,2,4))
            except: return 384
        photos.sort(key=darkness)
        pick = photos[idx % min(6, len(photos))]   # pick among the 6 darkest
        img_url = pick["src"].get("portrait") or pick["src"].get("large")
        dest = folder / f"bg_{idx:02d}.jpg"
        img_req = urllib.request.Request(img_url, headers={"User-Agent": ua})
        with urllib.request.urlopen(img_req, timeout=30) as r:
            dest.write_bytes(r.read())
        return str(dest)
    except Exception as e:
        print(f"       ⚠️  bg fetch failed: {str(e)[:80]}")
        return None

def _bg_from_photo(photo_path, accent):
    """Load a photo, crop to 9:16, darken with a scrim so text stays readable."""
    img = Image.open(photo_path).convert("RGB")
    # cover-crop to 1080x1920
    scale = max(W / img.width, H / img.height)
    img = img.resize((int(img.width*scale), int(img.height*scale)))
    left = (img.width - W)//2; top = (img.height - H)//2
    img = img.crop((left, top, left+W, top+H))
    # dark scrim for readability (stronger in the middle where text sits)
    scrim = Image.new("RGB", (W, H), (0,0,0))
    img = Image.blend(img, scrim, 0.55)
    return img

def make_frame(path, lines_spec, accent, progress, bg_photo=None):
    img = _bg_from_photo(bg_photo, accent) if bg_photo else gradient_bg(accent)
    d = ImageDraw.Draw(img)
    # top brand bar
    d.rectangle([0, 0, W, 14], fill=accent)
    # render centered text block
    rendered = []
    for text, font, color in lines_spec:
        for ln in wrap(d, text, font, W-180):
            rendered.append((ln, font, color, font.size+26))
    total = sum(h for *_, h in rendered)
    y = (H-total)//2
    for ln, font, color, h in rendered:
        tw = d.textlength(ln, font=font)
        # soft shadow for readability
        d.text(((W-tw)//2+3, y+3), ln, font=font, fill=(0,0,0))
        d.text(((W-tw)//2,   y),   ln, font=font, fill=color)
        y += h
    # progress bar at the bottom
    bar_w = int(W * progress)
    d.rectangle([0, H-18, bar_w, H], fill=accent)
    img.save(path)
    return str(path)

def build_frames(script, folder, accent):
    big, mid, small = load_font(108), load_font(78), load_font(58)
    segs = [("hook", script["hook"].upper()),
            ("title", script["title"])]
    for i,p in enumerate(script["points"], 1):
        segs.append((f"point{i}", p))
    segs.append(("cta", script["cta"]))

    # Real photo backgrounds from Pexels (if key set) — kills the "void" look
    bquery = script.get("bquery") or script.get("title","")
    using_photos = bool(os.environ.get("PEXELS_API_KEY"))
    if using_photos:
        print(f"       🖼  fetching real backgrounds for '{bquery}'…")

    frames, n = [], len(segs)
    for idx,(kind,text) in enumerate(segs):
        prog = (idx+1)/n
        bg = _pexels_photo(bquery, folder, idx) if using_photos else None
        if kind == "hook":
            spec = [(text, big, accent)]
        elif kind == "title":
            spec = [(text, mid, (255,255,255))]
        elif kind.startswith("point"):
            num = kind.replace("point","")
            spec = [(f"#{num}", big, accent), (text, small, (255,255,255))]
        else:
            spec = [(text, mid, (255,255,255)), ("👇", big, accent)]
        frames.append(make_frame(folder/f"{idx:02d}.png", spec, accent, prog, bg))
    return frames, segs

# ─────────────────────────── 3. VOICE + SRT ────────────────────────────────
def _best_mac_voice():
    """Pick the best FEMALE macOS voice (so any fallback is still female —
    never a male voice mixed into a video). Female names only."""
    FEMALE = ["Samantha","Ava","Allison","Susan","Zoe","Karen","Moira",
              "Tessa","Kate","Serena","Fiona","Victoria","Kathy"]
    try:
        out = subprocess.run(["say","-v","?"], capture_output=True, text=True).stdout
    except Exception:
        return "Samantha"
    lines = [l for l in out.splitlines() if "en_" in l]
    names = [l.split("  ")[0].strip() for l in lines]
    # 1) a female Premium/Enhanced neural voice
    for tier in ["(Premium)","(Enhanced)"]:
        for n in names:
            if tier in n and any(n.startswith(f) for f in FEMALE):
                return n
    # 2) any female basic voice (Samantha is always installed)
    for f in FEMALE:
        for n in names:
            if n == f or n.startswith(f + " "):
                return n
    return "Samantha"

def make_voice(segs, folder):
    narration = " . ".join(t for _,t in segs)
    mp3 = folder/"voice.mp3"

    # 1) BEST: ElevenLabs human voice if a key is configured
    el_key = os.environ.get("ELEVENLABS_API_KEY")
    if el_key:
        try:
            return _elevenlabs_voice(narration, el_key, folder)
        except Exception as e:
            print(f"       ⚠️  ElevenLabs failed ({e}); using best macOS voice.")

    # 2) FREE: best installed macOS voice (premium/enhanced if available)
    voice = _best_mac_voice()
    aiff = folder/"voice.aiff"
    subprocess.run(["say","-v",voice,"-o",str(aiff),narration], check=True)
    subprocess.run(["ffmpeg","-y","-i",str(aiff),str(mp3)], check=True, capture_output=True)
    print(f"       🎙  voice: {voice}")
    return str(mp3)

def _elevenlabs_voice(text, key, folder):
    """Truly human AI narration via ElevenLabs.
    Default = Sarah (free-tier female). Rachel is paid-only so never default to it."""
    mp3 = folder/"voice.mp3"
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or "EXAVITQu4vr4xnSDxMaL"  # Sarah
    body = json.dumps({
        "text": text, "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability":0.5,"similarity_boost":0.75,
                            "style":0.3,"use_speaker_boost":True}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=body, headers={"xi-api-key":key,"Content-Type":"application/json",
                            "Accept":"audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        mp3.write_bytes(r.read())
    print(f"       🎙  voice: ElevenLabs Sarah (human female)")
    return str(mp3)

def audio_seconds(path):
    out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",path], capture_output=True,text=True).stdout.strip()
    try: return float(out)
    except: return 30.0

def _voice_music_filter(voice_input, music_input, duration):
    """Mix a restrained music bed that automatically ducks during narration."""
    fade = min(0.8, max(0.1, duration / 3))
    fade_out = max(0, duration - fade)
    return (f"{voice_input}aresample=48000,asplit=2[vo][sc];"
            f"{music_input}aresample=48000,volume=0.80,afade=t=in:st=0:d={fade:.3f},afade=t=out:st={fade_out:.3f}:d={fade:.3f}[mu];"
            "[mu][sc]sidechaincompress=threshold=0.06:ratio=2:attack=25:release=500[ducked];"
            "[vo][ducked]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[a]")

# ════════════════════════════════════════════════════════════════════════════
#  ANIMATED CAPTIONS PIPELINE — words appear one-by-one in sync with the voice
# ════════════════════════════════════════════════════════════════════════════

def _clean_for_tts(text):
    """Strip characters that cause ElevenLabs to pause, hesitate, or mispronounce.
    @handles → the word after @  |  emoji → removed  |  URLs → removed
    The caption overlay still shows the original text — this is voice-only."""
    import re
    t = text
    t = re.sub(r'@(\w[\w.]*)', r'\1', t)          # @shelfmade.daily → shelfmade.daily
    t = re.sub(r'https?://\S+', '', t)              # remove URLs
    t = re.sub(r'[^\x00-\x7F]+', '', t)             # strip all non-ASCII (emoji, etc.)
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t or text   # never return empty string

def _voice_segment(text, idx, folder):
    """Narrate ONE segment; return (mp3_path, duration_seconds).
    ElevenLabs is RETRIED several times (transient rate-limits are common during
    rapid generation) so a single hiccup never drops a video to the Mac voice."""
    import time
    tts_text = _clean_for_tts(text)     # sanitize @handles, emoji, URLs before TTS
    el_key = os.environ.get("ELEVENLABS_API_KEY")
    mp3 = folder / f"seg_{idx:02d}.mp3"
    if el_key:
        last_err = None
        for attempt in range(4):                 # retry up to 4x
            try:
                _elevenlabs_voice(tts_text, el_key, folder)
                (folder/"voice.mp3").replace(mp3)
                return str(mp3), audio_seconds(str(mp3))
            except Exception as e:
                last_err = e
                time.sleep(2 * (attempt + 1))     # backoff: 2s,4s,6s
        # only reached if all retries failed → female Mac fallback (never male)
        print(f"       ⚠️  ElevenLabs failed after retries ({str(last_err)[:60]}) "
              f"→ female Mac voice fallback")
    voice = _best_mac_voice()
    aiff = folder / f"seg_{idx:02d}.aiff"
    raw  = folder / f"seg_{idx:02d}_raw.mp3"
    # slower rate = calmer, more natural mood delivery
    subprocess.run(["say","-v",voice,"-r","158","-o",str(aiff),tts_text], check=True)
    subprocess.run(["ffmpeg","-y","-i",str(aiff),str(raw)], check=True, capture_output=True)
    # warm it: gentle high-cut to remove robotic harshness + soft reverb + normalize
    subprocess.run(["ffmpeg","-y","-i",str(raw),
        "-af","highpass=f=90,lowpass=f=8500,aecho=0.85:0.5:60:0.12,dynaudnorm=f=200",
        str(mp3)], check=True, capture_output=True)
    return str(mp3), audio_seconds(str(mp3))

def _zoomed_bg(bg_photo, accent, zoom):
    """Background with a smooth slow zoom + heavy blur + dark scrim → calm,
    cinematic, always readable (never busy/ugly)."""
    if bg_photo:
        from PIL import ImageFilter
        img = Image.open(bg_photo).convert("RGB")
        scale = max(W/img.width, H/img.height) * zoom
        img = img.resize((int(img.width*scale), int(img.height*scale)))
        left = (img.width - W)//2; top = (img.height - H)//2
        img = img.crop((left, top, left+W, top+H))
        # light blur keeps the image attractive & recognizable (not a plain void)
        img = img.filter(ImageFilter.GaussianBlur(6))
        # gentle overall dim + stronger dark gradient ONLY behind the centered text
        img = Image.blend(img, Image.new("RGB",(W,H),(0,0,0)), 0.32)
        grad = Image.new("L",(1,H),0); gp=grad.load()
        for y in range(H):
            # darkest in the vertical middle (where captions sit), clearer top/bottom
            d = 1.0 - min(1.0, abs(y-H*0.52)/(H*0.34))
            gp[0,y] = int(150*max(0.0,d))
        grad = grad.resize((W,H))
        shade = Image.new("RGB",(W,H),(0,0,0))
        img = Image.composite(shade, img, grad)
    else:
        img = gradient_bg(accent)
        if zoom > 1.0:  # subtle zoom on gradient too
            nw, nh = int(W*zoom), int(H*zoom)
            img = img.resize((nw,nh)).crop(((nw-W)//2,(nh-H)//2,(nw-W)//2+W,(nh-H)//2+H))
    return img

def _draw_words(img, visible_words, highlight_idx, font, accent):
    """Draw the revealed words centered, newest word in accent color."""
    d = ImageDraw.Draw(img)
    max_w = W - 160
    # wrap visible words into lines, tracking each word's global index
    lines, cur, cur_idx = [], [], []
    for i, w in enumerate(visible_words):
        test = " ".join(cur + [w])
        if d.textlength(test, font=font) <= max_w:
            cur.append(w); cur_idx.append(i)
        else:
            lines.append((cur, cur_idx)); cur, cur_idx = [w], [i]
    if cur: lines.append((cur, cur_idx))

    line_h = font.size + 22
    total = len(lines) * line_h
    y = (H - total)//2
    for words_line, idxs in lines:
        line_str = " ".join(words_line)
        x = (W - d.textlength(line_str, font=font))//2
        for w, gi in zip(words_line, idxs):
            color = accent if gi == highlight_idx else (255,255,255)
            # shadow + word
            d.text((x+3, y+3), w, font=font, fill=(0,0,0))
            d.text((x, y), w, font=font, fill=color)
            x += d.textlength(w + " ", font=font)
        y += line_h
    return img

def produce(script, folder, accent):
    """Full animated build: voice + word-by-word captions over cinematic video B-roll.
    Video mode: each script segment gets its OWN content-matched clip with crossfades.
    Photo mode: single zoomed Pexels photo (fallback)."""
    folder.mkdir(parents=True, exist_ok=True)
    import short_motion
    os.environ['SHELFMADE_MUSIC_KEY'] = str(folder.name) + str(script.get('hook',''))
    music = short_motion.music_asset()
    if not music.is_file():
        raise RuntimeError('The configured ShelfMade music track is missing. Restore it before generating a draft; narration-only output is disabled.')
    if os.environ.get('SHELFMADE_LOCAL_MOTION','0') == '1':
        short_motion.prerequisites(folder,music)

    if os.environ.get("USE_STICKMAN", "0") == "1":
        try:
            import sys as _sys
            _engine_dir = Path(__file__).parent / "animation_engine"
            if str(_engine_dir) not in _sys.path:
                _sys.path.insert(0, str(_engine_dir))
            import stickman as _stickman
            font_fn = lambda is_hook: load_font(128 if is_hook else 104)
            final = _stickman.produce_stickman_video(
                script, accent, folder, voice_segment_fn=_voice_segment,
                caption_font_fn=font_fn)
            print("       🎨 talking stick-figure character video")
            return final
        except Exception as e:
            print(f"       ⚠️  stickman engine failed ({e}) — falling back to Pexels video")

    big, mid = load_font(128), load_font(104)
    if os.environ.get('SHELFMADE_LOCAL_MOTION','0') != '1':
        from opening_visual import card as opening_card
        opener=opening_card(script,load_font)
        opener.save(folder/'cover.jpg',quality=94)
        opener.save(folder/'opening.png')
    CHUNK = 4

    segs = [("hook", script["hook"])]
    for i, p in enumerate(script["points"], 1):
        segs.append((f"point{i}", p))
    segs.append(("cta", script["cta"]))

    bquery    = script.get("bquery") or script.get("title", "")
    use_photos = bool(os.environ.get("PEXELS_API_KEY"))
    use_video  = os.environ.get("USE_VIDEO_BG", "0") == "1" and use_photos
    local_motion = os.environ.get("SHELFMADE_LOCAL_MOTION", "0") == "1"
    use_video = use_video or local_motion

    if use_video:
        # ── CINEMATIC MODE: voice first → per-segment B-roll → captions ──

        # Pass 1 — generate all voice segments so we know each duration
        seg_data = []   # (kind, text, mp3_path, duration_s)
        batch_voice = getattr(sys.modules.get(__name__), '_voice_segments', None)
        if batch_voice:
            rendered=batch_voice([text for _,text in segs],folder)
            if len(rendered)!=len(segs):raise RuntimeError('Batch narration returned an incomplete segment list.')
            seg_data=[(kind,text,mp3,dur) for (kind,text),(mp3,dur) in zip(segs,rendered)]
        else:
            for idx, (kind, text) in enumerate(segs):
                mp3, dur = _voice_segment(text, idx, folder)
                seg_data.append((kind, text, mp3, dur))

        if local_motion:
            import render_readiness as readiness, cinematic_pipeline as cinema, short_motion
            readiness.record(folder,'short_before_footage_search',lambda:short_motion.narration(script,seg_data,folder,cinema.probe))

        use_animation = os.environ.get("USE_ANIMATION_BG", "0") == "1"
        bg_path = None
        if use_animation:
            try:
                import sys as _sys
                _engine_dir = Path(__file__).parent / "animation_engine"
                if str(_engine_dir) not in _sys.path:
                    _sys.path.insert(0, str(_engine_dir))
                import engine as _anim_engine
                total_dur = sum(dur for _, _, _, dur in seg_data)
                bg_path = str(_anim_engine.render(script, total_dur, accent, folder))
                print("       🎨 in-house animation background")
            except Exception as e:
                print(f"       ⚠️  animation engine failed ({e}) — falling back to Pexels video")
                bg_path = None

        if not bg_path:
            # Build per-segment content-matched montage with crossfade dissolves
            seg_infos = [(kind, text, dur, bquery)
                         for kind, text, _, dur in seg_data]
            if local_motion:
                from short_motion import montage
                bg_path = montage(script,seg_infos,folder)
            else:
                bg_path = _build_segmented_montage(seg_infos, folder)
        if not bg_path:
            print("       ⚠️  cinematic montage failed — falling back to photo")
            use_video = False

        if use_video:
            # Pass 2 — RGBA caption overlay frames (transparent bg)
            timed_frames = []; fcount = 0
            audio_parts  = []
            for kind, text, mp3, dur in seg_data:
                audio_parts.append(mp3)
                words = text.split(); n = max(1, len(words))
                per   = short_motion.caption_interval(dur,n) if local_motion else max(0.30, dur / n)
                # Hook captions use the same transparent moving-word treatment as the body.
                font  = big if kind == "hook" else mid
                chunks = [words[i:i+CHUNK] for i in range(0, len(words), CHUNK)]
                for chunk in chunks:
                    for k in range(1, len(chunk)+1):
                        img = _render_caption_rgba((chunk if kind == 'hook' else chunk[:k]), k-1, font, accent)  # hook: whole line visible from frame 1, spoken word highlighted
                        fp  = folder / f"f_{fcount:04d}.png"
                        img.save(fp); fcount += 1
                        timed_frames.append((str(fp), per))

            combined = folder / "voice.mp3"
            alist    = folder / "alist.txt"
            alist.write_text("".join(f"file '{a}'\n" for a in audio_parts))
            subprocess.run(["ffmpeg","-y","-f","concat","-safe","0",
                            "-i",str(alist),"-c:a","libmp3lame","-q:a","2",str(combined)],
                           check=True, capture_output=True)
            return _assemble_video_bg_timed(timed_frames, str(combined), folder, bg_path)

    # ── PHOTO MODE: single calm zoomed background (fallback / USE_VIDEO_BG=0) ──
    single_bg = _pexels_photo(bquery, folder, 0) if use_photos else None
    if use_photos:
        print(f"       🖼  one calm background: '{bquery}'")

    total_words = sum(max(1, len(t.split())) for _, t in segs)
    words_done  = 0
    timed_frames = []; audio_parts = []; fcount = 0

    for idx, (kind, text) in enumerate(segs):
        seg_mp3, dur = _voice_segment(text, idx, folder)
        audio_parts.append(seg_mp3)
        words = text.split(); n = max(1, len(words))
        per   = max(0.30, dur / n)
        font  = big if kind == "hook" else mid
        chunks = [words[i:i+CHUNK] for i in range(0, len(words), CHUNK)]
        if kind == 'hook':
            fp=folder/'opening.png'
            timed_frames.append((str(fp),dur))
            words_done+=n
            continue
        wseen  = 0
        for chunk in chunks:
            for k in range(1, len(chunk)+1):
                gprog = (words_done + wseen + k) / total_words
                zoom  = 1.0 + 0.10 * gprog
                img   = _zoomed_bg(single_bg, accent, zoom)
                ImageDraw.Draw(img).rectangle([0,0,W,12], fill=accent)
                _draw_words(img, chunk[:k], k-1, font, accent)
                fp = folder / f"f_{fcount:04d}.png"
                img.save(fp); fcount += 1
                timed_frames.append((str(fp), per))
            wseen += len(chunk)
        words_done += n

    combined = folder / "voice.mp3"
    alist    = folder / "alist.txt"
    alist.write_text("".join(f"file '{a}'\n" for a in audio_parts))
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(alist),
                    "-c:a","libmp3lame","-q:a","2",str(combined)], check=True, capture_output=True)
    return _assemble_timed(timed_frames, str(combined), folder)

def _render_caption_rgba(visible_words, highlight_idx, font, accent):
    """Caption-only RGBA frame — transparent bg so live video shows through.
    Gradient dark scrim only in the text zone keeps words readable over any video."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("L", (1, H), 0); gp = grad.load()
    for y in range(H):
        dist = abs(y - H * 0.52) / (H * 0.38)
        gp[0, y] = int(190 * max(0.0, 1.0 - min(1.0, dist)))
    grad = grad.resize((W, H), Image.NEAREST)
    scrim = Image.merge("RGBA", [Image.new("L",(W,H),0), Image.new("L",(W,H),0),
                                  Image.new("L",(W,H),0), grad])
    img = Image.alpha_composite(img, scrim)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 14], fill=(*accent, 255))
    max_w = W - 160
    lines, cur, cur_idx = [], [], []
    for i, w in enumerate(visible_words):
        test = " ".join(cur + [w])
        if d.textlength(test, font=font) <= max_w:
            cur.append(w); cur_idx.append(i)
        else:
            lines.append((cur, cur_idx)); cur, cur_idx = [w], [i]
    if cur: lines.append((cur, cur_idx))
    line_h = font.size + 22
    y = (H - len(lines) * line_h) // 2
    for words_line, idxs in lines:
        line_str = " ".join(words_line)
        x = int((W - d.textlength(line_str, font=font)) // 2)
        for w, gi in zip(words_line, idxs):
            color = (*accent, 255) if gi == highlight_idx else (255, 255, 255, 255)
            d.text((x+4, y+4), w, font=font, fill=(0,0,0,200))
            d.text((x,   y),   w, font=font, fill=color)
            x += int(d.textlength(w + " ", font=font))
        y += line_h
    return img


def _assemble_video_bg_timed(timed_frames, voice, folder, bg_video_path):
    """Live video compositing: bg video plays at native 30fps, RGBA captions float on top.
    No baked frames = perfectly smooth background movement, independent of word timing."""
    listfile = folder / "frames_cap.txt"
    with open(listfile, "w") as f:
        for fp, sec in timed_frames:
            f.write(f"file '{fp}'\nduration {sec:.3f}\n")
        f.write(f"file '{timed_frames[-1][0]}'\n")

    voice_dur = audio_seconds(voice)   # hard stop — no infinite loops
    import short_motion
    music = short_motion.music_asset()
    out   = folder / "final.mp4"

    vf = (f"[0:v]setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=disable[bg];"
          "[1:v]setpts=PTS-STARTPTS[cap];"
          "[bg][cap]overlay=0:0:format=auto[v]")

    if music.is_file():
        af = _voice_music_filter('[2:a]','[3:a]',voice_dur)
        cmd = ["ffmpeg", "-y",
               "-stream_loop", "-1", "-i", bg_video_path,
               "-f", "concat", "-safe", "0", "-i", str(listfile),
               "-i", voice,
               "-stream_loop", "-1", "-i", str(music),
               "-filter_complex", vf + ";" + af,
               "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-c:a", "aac",
               "-t", f"{voice_dur:.3f}", str(out)]
    else:
        cmd = ["ffmpeg", "-y",
               "-stream_loop", "-1", "-i", bg_video_path,
               "-f", "concat", "-safe", "0", "-i", str(listfile),
               "-i", voice,
               "-filter_complex", vf,
               "-map", "[v]", "-map", "2:a",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-c:a", "aac",
               "-t", f"{voice_dur:.3f}", str(out)]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg composite failed:\n{result.stderr.decode()[-1200:]}")
    return str(out)


def _assemble_timed(timed_frames, voice, folder):
    """Build video from (frame, duration) pairs + voice + music."""
    listfile = folder / "frames.txt"
    with open(listfile,"w") as f:
        for fp, sec in timed_frames:
            f.write(f"file '{fp}'\nduration {sec:.3f}\n")
        f.write(f"file '{timed_frames[-1][0]}'\n")

    silent = folder/"video_silent.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listfile),
                    "-r","30","-fps_mode","cfr","-pix_fmt","yuv420p","-c:v","libx264",
                    str(silent)], check=True, capture_output=True)

    import short_motion
    music = short_motion.music_asset(); out = folder/"final.mp4"
    if music.is_file():
        cmd = ["ffmpeg","-y","-i",str(silent),"-i",voice,
               "-stream_loop","-1","-i",str(music),
               "-filter_complex",
               _voice_music_filter('[1:a]','[2:a]',audio_seconds(voice)),
               "-map","0:v","-map","[a]","-c:v","libx264","-pix_fmt","yuv420p",
               "-c:a","aac","-shortest",str(out)]
    else:
        cmd = ["ffmpeg","-y","-i",str(silent),"-i",voice,"-map","0:v","-map","1:a",
               "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return str(out)

def srt_time(s):
    h=int(s//3600); m=int((s%3600)//60); sec=int(s%60); ms=int((s-int(s))*1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

def build_srt(segs, total, folder):
    """Estimate per-segment timing proportional to text length → SRT captions."""
    texts = [t for _,t in segs]
    weights = [max(1,len(t)) for t in texts]
    tot_w = sum(weights)
    srt, t0 = [], 0.0
    for i,(text,w) in enumerate(zip(texts,weights),1):
        dur = total * (w/tot_w)
        t1 = t0+dur
        srt.append(f"{i}\n{srt_time(t0)} --> {srt_time(t1)}\n{text}\n")
        t0 = t1
    path = folder/"captions.srt"
    path.write_text("\n".join(srt))
    return str(path)

# ─────────────────────────── 4. ASSEMBLE ───────────────────────────────────
def _ken_burns_clip(frame, seconds, idx, folder, zoom_in=True):
    """Turn one still frame into a slowly zooming clip (motion = retention)."""
    fps = 30
    total = max(1, int(seconds * fps))
    clip = folder / f"clip_{idx:02d}.mp4"
    # alternate zoom in/out for visual variety
    if zoom_in:
        z = "min(zoom+0.0012,1.18)"
    else:
        z = "if(lte(zoom,1.0),1.18,max(zoom-0.0012,1.0))"
    vf = (f"scale={W*2}:{H*2},"
          f"zoompan=z='{z}':d={total}:s={W}x{H}:fps={fps}:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
          f"format=yuv420p")
    subprocess.run(["ffmpeg","-y","-loop","1","-i",frame,"-t",f"{seconds:.2f}",
                    "-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p", str(clip)],
                   check=True, capture_output=True)
    return str(clip)

def assemble(frames, voice, folder):
    """Build a Ken-Burns (zooming) clip per frame, concat them, then mix
    voice + soft music. Captions are burned into the frames already."""
    dur = audio_seconds(voice)
    per = max(2.2, dur/len(frames))

    # 1) make a zooming clip per frame (alternating zoom direction)
    clips = [_ken_burns_clip(fr, per, i, folder, zoom_in=(i % 2 == 0))
             for i, fr in enumerate(frames)]

    # 2) concat the clips (video only)
    listfile = folder/"clips.txt"
    listfile.write_text("".join(f"file '{c}'\n" for c in clips))
    silent = folder/"video_silent.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listfile),
                    "-c","copy", str(silent)], check=True, capture_output=True)

    # 3) mix voice + music onto the concatenated video
    import short_motion
    music = short_motion.music_asset()
    out = folder/"final.mp4"
    if music.is_file():
        cmd = ["ffmpeg","-y","-i",str(silent),"-i",voice,"-stream_loop","-1","-i",str(music),
               "-filter_complex",
               _voice_music_filter('[1:a]','[2:a]',dur),
               "-map","0:v","-map","[a]","-c:v","libx264","-pix_fmt","yuv420p",
               "-c:a","aac","-shortest", str(out)]
    else:
        cmd = ["ffmpeg","-y","-i",str(silent),"-i",voice,
               "-map","0:v","-map","1:a","-c:v","libx264","-pix_fmt","yuv420p",
               "-c:a","aac","-shortest", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return str(out)

# ─────────────────────────────── main ──────────────────────────────────────
def main():
    topic = sys.argv[1] if len(sys.argv)>1 else \
        "Why most traders lose money in their first year"
    accent = BRAND
    slug = re.sub(r"[^a-z0-9]+","-",topic.lower())[:40].strip("-")
    folder = OUT/slug; folder.mkdir(parents=True, exist_ok=True)

    print(f"\n🎬 Creating video: \"{topic}\"\n")
    print("  1/3 ✍️  Script…")
    script = write_script(topic)
    print("  2/3 🎙  Voice + word-by-word animated captions…")
    print("  3/3 🎞  Assembling…")
    final = produce(script, folder, accent)

    print(f"\n✅ DONE:\n   {final}\n   open \"{final}\"\n")

if __name__ == "__main__":
    main()
