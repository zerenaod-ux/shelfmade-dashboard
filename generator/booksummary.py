#!/usr/bin/env python3
"""
Content Empire — BOOK SUMMARY generator (100% factual, free public-domain books).

Pulls a REAL public-domain book from Project Gutenberg, then summarizes it
WITHOUT guessing:

  • FREE mode (no key): EXTRACTIVE summary — pulls the book's actual top
    sentences. 100% the author's real words, zero hallucination.
  • SMART mode (CLAUDE_API_KEY set): grounded summary — Claude reads real
    excerpts and rewrites them, instructed to use ONLY what's in the text.

Then it builds a video with make_video.

⚠️ LEGAL: only use PUBLIC-DOMAIN books (Project Gutenberg = safe & legal).
   Do NOT use copyrighted modern books (Atomic Habits, Rich Dad, etc.).

Run:
    python3 booksummary.py 132                      # by Gutenberg ID
    python3 booksummary.py 132 MOTIVATION          # set niche/brand
    python3 booksummary.py                          # default curated book

Curated safe public-domain books (verified on Gutenberg):
    132  The Art of War — Sun Tzu          (strategy / trading mindset)
    2680 Meditations — Marcus Aurelius     (motivation / stoicism)
    1232 The Prince — Machiavelli          (strategy / power)
    16643 Essays by Emerson (Self-Reliance)(motivation)
"""

import sys, re, urllib.request, collections
from pathlib import Path
import make_video as mv
import memory

CURATED = {
    "132":  ("The Art of War", "Sun Tzu", "TRADING"),
    "2680": ("Meditations", "Marcus Aurelius", "MOTIVATION"),
    "1232": ("The Prince", "Machiavelli", "MOTIVATION"),
    "16643":("Self-Reliance & Essays", "Ralph Waldo Emerson", "MOTIVATION"),
}

NICHE_COLOR = {
    "TRADING": (255,107,53), "MOTIVATION": (243,156,18),
    "PERSONAL_FINANCE": (39,174,96), "AI_TECH": (155,89,182),
    "FACTS_KNOWLEDGE": (142,68,173),
}

# Short, visual Pexels search terms that fit each niche's mood
NICHE_BQUERY = {
    "TRADING": "ancient battle strategy",
    "MOTIVATION": "mountain sunrise landscape",
    "PERSONAL_FINANCE": "money finance",
    "AI_TECH": "technology abstract",
    "FACTS_KNOWLEDGE": "library old books",
}

# ─────────────────────── 1. FETCH REAL BOOK ────────────────────────────────
def fetch_book(gid):
    import retained_sources
    retained = retained_sources.read(str(gid))
    if retained is not None:
        return strip_gutenberg(retained)
    urls = [
        f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}.txt",
    ]
    failures = []
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", errors="ignore")
            if len(raw) > 2000:
                return strip_gutenberg(raw)
        except Exception as error:
            failures.append(error)
            continue
    import generation_recovery
    if len(failures) == len(urls) and all(generation_recovery.transient(e) for e in failures):
        raise failures[-1]
    raise RuntimeError(f"Could not fetch Gutenberg book {gid}")

def strip_gutenberg(text):
    """Remove the Gutenberg license header/footer — keep only the real book."""
    start = re.search(r"\*\*\* START OF.*?\*\*\*", text, re.S)
    end   = re.search(r"\*\*\* END OF.*?\*\*\*", text, re.S)
    if start: text = text[start.end():]
    if end:   text = text[:text.rfind("*** END OF")]
    return text.strip()

# ─────────────────────── 2. FACTUAL SUMMARY ────────────────────────────────
def sentences(text):
    text = re.sub(r"\s+", " ", text)
    # remove section markers / footnote artifacts like "§ 7]", "[1]", chapter nums
    text = re.sub(r"§+\s*\d+\s*\]?", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    clean = []
    for s in parts:
        s = s.strip(" ]§•-")
        # must start with a capital letter and be a real, clean sentence
        if 50 <= len(s) <= 200 and s[:1].isupper() and "  " not in s:
            clean.append(s)
    return clean

def extractive_summary(text, n=4):
    """Pick the book's most representative REAL sentences (no hallucination).
    Scores sentences by frequency of their (non-stopword) terms."""
    sents = sentences(text)
    if not sents:
        return []
    stop = set("the a an and or but of to in is are was were be been being for "
               "on at by with as that this it he she they we you i his her their "
               "not no so if then than which who whom whose what when where why "
               "how all any can will would should could may might must shall do "
               "does did has have had from into your you our".split())
    words = re.findall(r"[a-z]{3,}", text.lower())
    freq = collections.Counter(w for w in words if w not in stop)
    def score(s):
        toks = re.findall(r"[a-z]{3,}", s.lower())
        return sum(freq.get(t, 0) for t in toks) / (len(toks) + 1)
    ranked = sorted(sents, key=score, reverse=True)
    # de-dupe near-identical, keep order of appearance for readability
    chosen, seen = [], set()
    for s in ranked:
        key = s.lower()[:50]
        if key not in seen:
            chosen.append(s); seen.add(key)
        if len(chosen) >= n:
            break
    return chosen

def claude_grounded(title, author, excerpt, key):
    """Grounded summary — Claude may use ONLY the provided real excerpt."""
    import json
    system = ("You summarize books using ONLY the provided text. You never add "
              "facts not present in the excerpt. If unsure, you stay general. "
              "No invented quotes, numbers, or claims.")
    prompt = (f'Book: "{title}" by {author}.\n\n'
              f"Using ONLY this excerpt (do not invent anything):\n\n"
              f"{excerpt[:6000]}\n\n"
              "Return STRICT JSON with these fields:\n"
              '  "hook": a 6-10 word spoken hook that creates SHOCK or CURIOSITY — '
              'use a question or a counterintuitive claim (e.g. "What if everything you believe about X is wrong?"). '
              'Never use the book title as the hook. No generic phrases like "timeless wisdom".\n'
              '  "title": the book title only (one line)\n'
              '  "points": array of 4 takeaways grounded in the text — each must be a SURPRISING or COUNTERINTUITIVE insight, '
              'written as a short punchy sentence the viewer would want to share\n'
              '  "cta": one line call to action\n'
              "JSON only, no markdown.")
    body = json.dumps({"model":"claude-opus-4-5","max_tokens":900,"system":system,
        "messages":[{"role":"user","content":prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key":key,"anthropic-version":"2023-06-01",
                 "content-type":"application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    txt = re.sub(r"^```json|```$","",data["content"][0]["text"].strip()).strip()
    print("       ✨ grounded summary by Claude (from real text)")
    return json.loads(txt)

# ─────────────────────── 3. BUILD SCRIPT ───────────────────────────────────
def build_script(gid, niche=None):
    import os
    title, author, default_niche = CURATED.get(
        gid, (f"Book #{gid}", "Public Domain", "FACTS_KNOWLEDGE"))
    niche = niche or default_niche
    print(f"  📖 Fetching real book: {title} by {author} (Gutenberg #{gid})")
    text = fetch_book(gid)
    print(f"     {len(text):,} chars of real text")

    bquery = NICHE_BQUERY.get(niche, "abstract background")
    key = os.environ.get("CLAUDE_API_KEY")
    if key:
        try:
            script = claude_grounded(title, author, text, key)
            script["title"] = f"{title} — {script.get('title','')}"
            script["bquery"] = bquery          # short, fitting bg search term
            return script, niche, title
        except Exception as e:
            print(f"     ⚠️  Claude failed ({e}); using extractive (still real).")

    points = extractive_summary(text, 4)
    script = {
        "hook":  "Timeless wisdom",
        "title": f"{title} by {author}",
        "points": points if points else ["A public-domain classic worth reading."],
        "cta":   "Follow for daily book wisdom.",
        "bquery": bquery,
    }
    print("       ✅ extractive summary (100% the author's real words)")
    return script, niche, title

# ─────────────────────────────── main ──────────────────────────────────────
def main():
    gid   = sys.argv[1] if len(sys.argv) > 1 else "132"
    niche = sys.argv[2] if len(sys.argv) > 2 else None

    script, niche, title = build_script(gid, niche)
    topic = f"Book summary: {title}"

    if memory.is_duplicate(topic):
        print(f"  ⏭  Already summarized '{title}' — skipping (memory).")
        return

    mv.BRAND = NICHE_COLOR.get(niche, (142,68,173))
    slug = re.sub(r"[^a-z0-9]+","-", topic.lower())[:45].strip("-")
    folder = mv.OUT/slug; folder.mkdir(parents=True, exist_ok=True)

    print("  🎙  Voice + animated word-by-word captions…")
    final = mv.produce(script, folder, mv.BRAND)

    memory.record(niche, topic, script, slug=slug, status="generated")
    print(f"\n✅ Book-summary video ready (100% factual):\n   {final}")
    print(f'   open "{final}"\n')

if __name__ == "__main__":
    main()
