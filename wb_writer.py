"""Topic-explainer script writer for the one-canvas whiteboard look (free AI via llm.json_call, with strict checks).
Shape (measured from the reference channel, see notes): story hook with numbers -> one recurring symbol -> thesis line ->
a real-life analogy every 40-60 s -> feeling payoff -> direct order -> source credit -> next-video line.
Output: {'title':..., 'panels':[{'title','tag','sentences':[{'say','item'|None}]}]}; item anchors are checked words from the sentence."""
import re, json
from wb_icons import NAMES

SYSTEM = 'You write spoken explainer scripts that are drawn on a whiteboard. Return ONLY JSON.'
STYLE = ('Voice: plain everyday words, short sentences (7-18 words), speak to the viewer as "you", concrete numbers and real-life pictures, '
         'no greetings, no "in this video", no filler. One recurring symbol that returns several times. ')
ICON_LIST = ', '.join(NAMES)


def words(s): return re.findall(r"[A-Za-z0-9$%']+", s)


def clean_panel(p, max_items=6):
    """Return a safe panel or raise ValueError."""
    if not isinstance(p, dict) or not isinstance(p.get('sentences'), list) or not p['sentences']:
        raise ValueError('panel without sentences')
    out = {'title': str(p.get('title', '')).strip()[:28] or 'Next idea', 'tag': (str(p['tag']).strip()[:8] or None) if p.get('tag') else None, 'sentences': []}
    n_items = 0
    for s in p['sentences']:
        say = str(s.get('say', '')).strip() if isinstance(s, dict) else ''
        w = words(say)
        if not 5 <= len(w) <= 28:
            continue
        item = s.get('item') if isinstance(s.get('item'), dict) else None
        good = None
        if item and n_items < max_items:
            kind = item.get('kind')
            anchor = str(item.get('anchor', '')).strip().strip('.,!?"')
            if anchor.lower() not in [x.lower() for x in w]:
                anchor = next((x for x in w if len(x) > 3), w[0])
            if kind == 'emoji':
                ch = str(item.get('char', '')).strip()
                try:
                    import wb_emoji
                    ok = bool(ch) and len(ch) <= 8 and wb_emoji.available() and wb_emoji.icon(ch)
                except Exception:
                    ok = False
                if ok:
                    good = {'kind': 'icon', 'name': 'emoji:' + ch, 'label': str(item.get('label', '')).strip()[:14], 'anchor': anchor}
            elif kind == 'icon':
                nm = str(item.get('name', '')).strip().lower()
                if nm in NAMES:
                    good = {'kind': 'icon', 'name': nm, 'label': str(item.get('label', '')).strip()[:14], 'anchor': anchor}
            elif kind in ('text', 'number'):
                t = str(item.get('text', '')).strip()[:18]
                if t:
                    good = {'kind': kind, 'text': t, 'anchor': anchor, 'color': 'r' if item.get('color') == 'r' or kind == 'number' else 'k'}
            elif kind == 'cross' and n_items > 0:
                ref = item.get('ref')
                if isinstance(ref, int) and 0 <= ref < n_items:
                    good = {'kind': 'cross', 'target': ref, 'anchor': anchor}
            elif kind == 'arrow' and n_items > 1:
                a, b = item.get('frm'), item.get('to')
                if isinstance(a, int) and isinstance(b, int) and 0 <= a < n_items and 0 <= b <= n_items and a != b:
                    good = {'kind': 'arrow', 'frm': a, 'to': b, 'anchor': anchor}
        if not good and n_items < max_items:
            cand = [x for x in w if len(x) > 4 and not x.isdigit()] or w
            key = max(cand, key=len)
            good = {'kind': 'text', 'text': key[:18], 'anchor': key, 'color': 'k'}
        if good:
            n_items += 1
            if good['kind'] in ('arrow',) and good['to'] >= n_items:
                good = None; n_items -= 1
        out['sentences'].append({'say': say, 'item': good})
        if len(out['sentences']) >= max_items:
            break
    if len(out['sentences']) < 3:
        raise ValueError('panel too short after checks')
    return out


def outline(topic, minutes, llm):
    n = max(1, round(minutes * 60 / 95))
    p = (STYLE + 'Topic: %s\nPlan a %d-minute explainer in %d chapters (each about 90-100 seconds). '
         'Return {"title":"result-promise title, no question, max 8 words","symbol":"one recurring everyday symbol and what it stands for",'
         '"chapters":[{"title":"plain 2-4 word title","job":"what this chapter says, one sentence","analogy":"one real-life picture used to explain it"}]}. '
         'Chapter 1 opens with a short true story with numbers. A chapter near the middle states the thesis in one line. The last chapter gives one direct action the viewer does today.' % (topic, minutes, n))
    d = llm.json_call(SYSTEM, p, temperature=0.7, max_tokens=2500)
    ch = d.get('chapters')
    if not isinstance(ch, list) or len(ch) < 1:
        raise ValueError('outline too short')
    return d


def write_chapter(topic, out, i, llm, previous_say='', short=False):
    c = out['chapters'][i]
    last = i == len(out['chapters']) - 1
    if short:
        shape = ('with exactly 3 panels. Each panel has exactly 4 sentences of 8-13 words (about 45 words) and EVERY sentence has an item (never null). '
                 'The first sentence is a surprising true fact that hooks in 3 seconds. The last panel ends with one direct action to do today.')
    else:
        shape = ('with 3 panels. Each panel has exactly 6 sentences (about 60-80 words) and EVERY sentence has an item (never null): '
                 'the pen draws what each sentence says, so there is never talking without drawing.')
    p = (STYLE + 'Topic: %s\nSymbol: %s\nWrite chapter %d of %d: "%s". Job: %s Analogy: %s.\n'
         'Return {"panels":[{"title":"2-4 words","tag":"optional year or number or null","sentences":[{"say":"one spoken sentence","item":{...}}]}]} %s '
         'An item is drawn on the whiteboard while that sentence is spoken, so each item shows what the sentence names. '
         'Item kinds: {"kind":"icon","name":ICON,"label":"<=14 chars or empty","anchor":"exact word from the sentence"}; {"kind":"text","text":"<=18 chars","color":"r or k","anchor":...}; '
         '{"kind":"number","text":"$10 or 30%%","anchor":...}; {"kind":"cross","ref":index of an earlier item in this panel,"anchor":...}; {"kind":"arrow","frm":earlier item index,"to":earlier item index,"anchor":...}. '
         'Items are numbered 0,1,2... in the order they appear in the panel. ICON must be one of: %s. '
         'For anything not in that list use {"kind":"emoji","char":"ONE emoji that shows it (any subject: animals, food, places, tools, science, sport, vehicles)","label":...,"anchor":...}. '
         '%s%s Previous chapter ended with: %s'
         % (topic, out.get('symbol', ''), i + 1, len(out['chapters']), c.get('title', ''), c.get('job', ''), c.get('analogy', ''), shape, ICON_LIST,
            'Open with a true story with real numbers, no greeting. ' if i == 0 and not short else '',
            'End with one direct action to do today.' if short and last else ('End with one direct action to do today, then one short sentence crediting where the idea comes from, then one line sending the viewer to the next video.' if last else ''), previous_say[:160] or 'nothing'))
    d = llm.json_call(SYSTEM, p, temperature=0.7, max_tokens=4500)
    panels = []
    for raw in d.get('panels', []):
        try:
            panels.append(clean_panel(raw))
        except ValueError:
            continue
    if len(panels) < 1:
        raise ValueError('chapter %d gave too few usable panels' % (i + 1))
    return panels


def write(topic, minutes=8, llm=None, short=False):
    if llm is None:
        import llm as _l; llm = _l
    out = outline(topic, minutes, llm)
    if short:
        out['chapters'] = out['chapters'][:1]
    panels, prev = [], ''
    for i in range(len(out['chapters'])):
        got, err = None, None
        for _try in range(4):
            try:
                got = write_chapter(topic, out, i, llm, prev, short); break
            except Exception as e:
                err = e; print('chapter %d retry %d: %s' % (i + 1, _try + 1, str(e)[:120]), flush=True)
        if got is None: raise err
        panels += got; prev = got[-1]['sentences'][-1]['say']
    return {'title': str(out.get('title', topic))[:90], 'topic': topic, 'panels': panels}


# TEST FIXTURE ONLY (original wording, not for publishing): lets the renderer/pipeline be tested without any AI call.
DEMO = {'title': 'Why A Small Buffer Saves A Small Bakery', 'topic': 'small cash buffer', 'panels': [
    {'title': 'The Bakery', 'tag': None, 'sentences': [
        {'say': 'A small bakery sells five hundred dollars of bread every single day.', 'item': {'kind': 'icon', 'name': 'house', 'label': 'bakery', 'anchor': 'bakery'}},
        {'say': 'After costs, it keeps about one hundred dollars of that.', 'item': {'kind': 'number', 'text': '$100', 'anchor': 'hundred'}},
        {'say': 'The owner spends every cent, because the shop feels safe.', 'item': {'kind': 'icon', 'name': 'wallet', 'label': 'spent', 'anchor': 'spends'}},
        {'say': 'Then one morning the oven breaks.', 'item': {'kind': 'icon', 'name': 'fire', 'label': 'oven', 'anchor': 'oven'}},
        {'say': 'The repair costs two thousand dollars, due this week.', 'item': {'kind': 'icon', 'name': 'warning', 'label': '$2,000', 'anchor': 'repair'}},
        {'say': 'With no buffer, the shop closes for twelve days.', 'item': {'kind': 'icon', 'name': 'calendar', 'label': '12 days', 'anchor': 'twelve'}}]},
    {'title': 'The Buffer', 'tag': None, 'sentences': [
        {'say': 'Now picture the same shop with one small jar.', 'item': {'kind': 'icon', 'name': 'jar', 'label': 'jar', 'anchor': 'jar'}},
        {'say': 'Each day the owner drops ten dollars into it.', 'item': {'kind': 'number', 'text': '$10', 'anchor': 'ten'}},
        {'say': 'It feels like nothing, and that is the point.', 'item': {'kind': 'icon', 'name': 'clock', 'label': 'daily', 'anchor': 'nothing'}},
        {'say': 'In seven months the jar holds two thousand dollars.', 'item': {'kind': 'icon', 'name': 'coins', 'label': '$2,000', 'anchor': 'jar'}},
        {'say': 'When the oven breaks, the owner pays the bill that day.', 'item': {'kind': 'icon', 'name': 'check', 'label': 'paid', 'anchor': 'pays'}},
        {'say': 'The shop never closes, and the bread keeps coming.', 'item': {'kind': 'icon', 'name': 'heart', 'label': 'open', 'anchor': 'closes'}}]},
    {'title': 'Your Jar', 'tag': None, 'sentences': [
        {'say': 'You can do the same thing this week.', 'item': {'kind': 'icon', 'name': 'person', 'label': 'you', 'anchor': 'you'}},
        {'say': 'Pick one small amount you will not miss.', 'item': {'kind': 'number', 'text': '$5', 'anchor': 'amount'}},
        {'say': 'Move it the moment your pay arrives.', 'item': {'kind': 'icon', 'name': 'phone', 'label': 'payday', 'anchor': 'pay'}},
        {'say': 'Do not wait for a better month.', 'item': {'kind': 'cross', 'ref': 2, 'anchor': 'wait'}},
        {'say': 'Start your jar today, and sleep better on the day something breaks.', 'item': {'kind': 'icon', 'name': 'bulb', 'label': 'start', 'anchor': 'today'}}]}]}
