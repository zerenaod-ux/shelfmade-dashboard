"""MINDLORE SERIES: 'What Your Mind Actually Does' - one numbered franchise of everyday-question full videos (the Ink Explainer pattern:
one repeatable promise, question titles people already ask, every video sells the next). Fails soft: any problem returns '' / does nothing.
brief()  -> prompt text for ml_autoscripts (title rule + today's radar winning pattern + recent titles to avoid)
record(fn, title) -> logs the new script;  footer(script) -> numbered series line + sources block for the video description."""
import json, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
F = B / 'data/mindlore/series.json'
SHOW = 'What Your Mind Actually Does'
def load():
    try: return json.loads(F.read_text())
    except Exception: return {'show': SHOW, 'episodes': []}
def brief():
    try:
        s = load(); recent = [e['title'] for e in s['episodes'][-8:]]
        pat = ''
        try:
            r = json.loads((B / 'data/radar/mindlore.json').read_text())
            pat = '\nTODAY\'S WINNING PATTERN on YouTube right now (borrow the PATTERN, never the words): %s. Angle: %s' % ((r.get('hook_patterns') or [''])[0], r.get('todays_angle', ''))
        except Exception:
            pass
        return ('\nSERIES RULE: this video is episode %d of the MindLore series "%s". The "public_title" question must be an EVERYDAY question a normal person already wonders about '
                '(examples of the pattern: "What does your brain actually do when you walk into a room?", "Why do you replay embarrassing memories at 3am?", "What really happens in your mind when you procrastinate?"). '
                'Start with What / Why / How / When / Do / Does, end with a question mark, keep it under 70 characters before " | Author", and make the old book answer it with honest limits. '
                'Titles already used, do NOT repeat or paraphrase: %s.%s\n') % (len(s['episodes']) + 1, SHOW, recent, pat)
    except Exception:
        return ''
def record(fn, title):
    try:
        s = load(); s['episodes'].append({'n': len(s['episodes']) + 1, 'file': fn, 'title': title, 'date': datetime.date.today().isoformat()})
        s['episodes'] = s['episodes'][-300:]; F.parent.mkdir(parents=True, exist_ok=True); F.write_text(json.dumps(s, indent=1))
    except Exception:
        pass
def footer(script):
    try:
        t = script.get('public_title', ''); e = next((e for e in load()['episodes'] if e['title'] == t), None)
        out = ''
        if e: out += 'Part of the series "%s", episode %d. New videos regularly.\n\n' % (SHOW, e['n'])
        out += 'Sources: %s by %s (original text, %s)' % (script.get('book_title') or script.get('title', ''), script.get('author', ''), script.get('source_url', ''))
        return '\n\n' + out
    except Exception:
        return ''
