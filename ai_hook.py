"""AI-written opening hook + loop line for a book Short (ShelfMade / MindLore). Replaces the fixed template lines ('Almost everyone gets X wrong')
with a line written for THIS passage, guided by the learned viewer notes. Returns (hook, loop) or None: callers then fall back to the old templates,
so a Gemini hiccup can never break a build. Needs GEMINI_API_KEY in the environment."""
import os, re, json

BAD_START = ('almost everyone gets', 'you were taught', 'stop reading', 'everyone quotes', 'nobody warns you', 'read this before you open', 'do not read',
             'the part of', 'forget what you know', 'what the book really asks', 'one line in', 'this line from', 'read this line', 'why does', 'what did', 'what is', 'why is')


def _ok(h, l):
    for t, lo, hi in ((h, 5, 9), (l, 3, 10)):
        if not isinstance(t, str) or not (lo <= len(t.split()) <= hi) or t[-1] not in '.?!':
            return False
        if re.search(r'[\d#@"“”_*\[\]]|[^\x00-\x7f]', t):
            return False
    return not h.lower().startswith(BAD_START)


def _close(h, brand):
    try:
        import variety
        return variety.too_close(h, brand)
    except Exception:
        return False


def _note(h, brand):
    try:
        import variety
        variety.note(brand, h)
    except Exception:
        pass


def generate(title, author, sentences, brand):
    if os.environ.get('AI_HOOKS', '1') == '0':
        return None
    try:
        import llm
    except Exception:
        llm = None
    if not os.environ.get('GEMINI_API_KEY') and not (llm and llm.available()):
        return None
    try:
        import ml_autoscripts as M
        try:
            import learned
            guide = learned.guidance(brand)
        except Exception:
            guide = ''
        passage = ' '.join(s.strip() for s in sentences[:4] if isinstance(s, str))[:900]
        prompt = ('You write the opening line of a 30-second vertical Short built from a public-domain book passage.\nBook: "%s" by %s.\nPassage the Short is built on: %s\n\n'
                  'Write ONE scroll-stopping opening line (5 to 9 words) and ONE loop line (3 to 10 words) that makes the viewer replay from the start. '
                  'The opening line must be specific to THIS passage (never a generic template such as "Almost everyone gets X wrong"), create tension or curiosity in its first three words, '
                  'speak to the viewer, and never put words in the author\'s mouth that the passage does not support. Plain English, no emoji, no hashtags, no digits, no quotation marks. '
                  'Each line must end with . ? or !%s\nReturn ONLY JSON: {"hook":"...","loop":"..."}') % (title, author or 'unknown', passage, guide)
        try:
            models = M._models()[:4] if os.environ.get('GEMINI_API_KEY') else []
        except Exception:
            models = []
        for model in models:
            try:
                d = M._one(model, prompt, True)
            except Exception:
                try:
                    d = M._one(model, prompt, False)
                except Exception:
                    continue
            h, l = (d.get('hook') or '').strip(), (d.get('loop') or '').strip()
            if _ok(h, l) and not _close(h, brand):
                _note(h, brand)
                return h, l
        if llm and llm.available():      # Gemini quota is often used up: free fallbacks (Groq, Cerebras, OpenRouter, Mistral)
            for _ in range(2):
                d = llm.json_call('You write short-form video hooks. Reply with JSON only.', prompt)
                h, l = (d.get('hook') or '').strip(), (d.get('loop') or '').strip()
                if _ok(h, l) and not _close(h, brand):
                    _note(h, brand)
                    return h, l
    except Exception:
        return None
    return None
