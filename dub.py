"""Multi-language dub of a MindLore Short (free): LLM translation + edge-tts voice + the same live-demo look.
  python dub.py <story_id> <lang es|pt> <outdir>     -> <outdir>/final.mp4 + POST_THIS.txt (title/caption in the target language)
Not auto-published: which channel carries dubbed videos is the owner's decision."""
import json, os, sys
from pathlib import Path
LANGS = {'es': ('Spanish (neutral Latin American)', 'es-MX-JorgeNeural'), 'pt': ('Brazilian Portuguese', 'pt-BR-AntonioNeural')}
def main(sid, lang, out):
    name, voice = LANGS[lang]; os.environ['LIVE_LANG'] = lang; os.environ['LIVE_VOICE'] = voice
    src = json.loads(Path('story-shorts/mindlore/%s.json' % sid).read_text()); import llm
    pay = {'title': src['public_title'], 'hook': src['hook'], 'sections': [s['narration'] for s in src['sections']]}
    r = llm.json_call('You are a professional translator and localiser for short videos. Reply JSON only.',
                      'Translate into %s for a spoken psychology Short. Keep every fact, number and study name exactly; natural, conversational, about 15% FEWER words than the English because the target language speaks slower (the video must stay under 70 seconds); the title is 2-6 words, catchy, no emoji. '
                      'Input JSON: %s\nReturn {"title":"...","hook":"...","sections":["...", ...]} with the same number of sections.' % (name, json.dumps(pay, ensure_ascii=False)), temperature=.3, max_tokens=6000)
    assert r and len(r.get('sections', [])) == len(src['sections']), 'translation failed'
    d = dict(src); d['public_title'] = r['title']; d['hook'] = r['hook']; d['sections'] = [dict(s, narration=r['sections'][i]) for i, s in enumerate(src['sections'])]
    out = Path(out); out.mkdir(parents=True, exist_ok=True); tmp = out / 'story.json'; tmp.write_text(json.dumps(d, ensure_ascii=False))
    import live_demo; live_demo.build(str(tmp), str(out / 'final.mp4'))
    (out / 'POST_THIS.txt').write_text('--- TITLE (%s) ---\n%s\n\n--- CAPTION ---\n%s\n\n%s\n\n#psicologia #MindLore #Shorts' % (lang, d['public_title'], d['hook'], '\n\n'.join(s['narration'] for s in d['sections'])[:1500]))
    print('dub done', lang, d['public_title'])
if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3])
