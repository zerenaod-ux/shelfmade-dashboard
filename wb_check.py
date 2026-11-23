"""Second-opinion reviewer for whiteboard scripts (free AI). One call per chapter: removes invented statistics, softens claims it cannot stand behind,
and fixes items that do not match their sentence. Output is re-validated by wb_writer.clean_panel; on ANY problem the original panels are kept."""
import json
from wb_icons import NAMES

SYSTEM = 'You are a strict fact-checker and visual editor for short explainer videos. Return ONLY JSON.'


def review(topic, panels, llm):
    import wb_writer
    try:
        payload = json.dumps({'panels': panels}, ensure_ascii=False)
        p = ('Topic: %s\nBelow is a script as JSON (panels -> sentences -> say + item). Check it like an editor:\n'
             '1. FACTS: if a sentence states a specific statistic, date, name or study you are NOT sure is real, rewrite it as a true general statement (or a clearly labelled round example such as "imagine 1,000 emails"). '
             'Never invent numbers, studies, quotes or experts. Keep real, well-known facts.\n'
             '2. PICTURES: each sentence has an item that must show what the sentence names. If an icon name/emoji/text does not match, replace it with one that does '
             '(icon names allowed: %s; or {"kind":"emoji","char":"ONE emoji","label":"..","anchor":".."}). Keep arrows/crosses valid.\n'
             '3. VOICE: keep it energetic, friendly, spoken English with contractions; keep every sentence 5-24 words; keep the same number of sentences and panels.\n'
             'Return the SAME JSON shape {"panels":[...]} with fixes applied and nothing else.\n\n%s' % (topic, ', '.join(NAMES), payload))
        d = llm.json_call(SYSTEM, p, temperature=0.2, max_tokens=4500)
        fixed = [wb_writer.clean_panel(x) for x in d.get('panels', [])]
        if len(fixed) == len(panels) and all(len(a['sentences']) >= max(3, len(b['sentences']) - 1) for a, b in zip(fixed, panels)):
            return fixed, True
    except Exception as e:
        print('review skipped:', str(e)[:120], flush=True)
    return panels, False
