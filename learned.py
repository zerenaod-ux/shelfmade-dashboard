"""Tiny helper for the writers: guidance(brand) returns the latest 'what viewers watch' notes (data/learned/<brand>.json) as prompt text, or '' when none/any problem."""
import json
from pathlib import Path


def _radar(brand):
    """TODAY'S SPIKES: the daily radar (last 48 h). Ignored when older than 3 days."""
    import datetime
    for base in (Path('data/radar'), Path(__file__).resolve().parent / 'data' / 'radar'):
        try:
            d = json.loads((base / (brand + '.json')).read_text())
            if (datetime.date.today() - datetime.date.fromisoformat(d.get('updated', '2000-01-01'))).days > 3:
                return ''
            t = ''
            if d.get('todays_angle'):
                t += "TODAY'S ANGLE (spiking in the last 48 hours): " + d['todays_angle'] + '. '
            if d.get('why'):
                t += 'WHY RECENT SPIKES WORK: ' + ' | '.join('%s - %s' % (x.get('title', '')[:50], x.get('why', '')) for x in d['why'][:3]) + '. '
            if d.get('ideas'):
                t += "TODAY'S IDEAS: " + ' | '.join(d['ideas'][:3]) + '. '
            if d.get('avoid'):
                t += 'TIRED THIS WEEK, AVOID: ' + ' | '.join(d['avoid'][:2]) + '. '
            return ('\nDAILY RADAR (updated %s; inspiration only, never copy titles, scripts, footage or characters): ' % d.get('updated') + t + '\n') if t else ''
        except Exception:
            continue
    return ''


def trending(brand):
    return _radar(brand) + _trending_14d(brand)


def _trending_14d(brand):
    for base in (Path('data/trends'), Path(__file__).resolve().parent / 'data' / 'trends', Path(__file__).resolve().parent.parent / 'data' / 'trends'):
        try:
            d = json.loads((base / (brand + '.json')).read_text())
            t = ''
            if d.get('hot_themes'):
                t += 'RISING THEMES THIS WEEK in our niche: ' + ' | '.join(d['hot_themes'][:6]) + '. '
            if d.get('hook_patterns'):
                t += 'HOOK PATTERNS getting views now: ' + ' | '.join(d['hook_patterns'][:3]) + '. '
            if d.get('ideas_for_us'):
                t += 'IDEAS TO TRY: ' + ' | '.join(d['ideas_for_us'][:4]) + '. '
            return ('\nTRENDING NOW (updated %s; inspiration only, never copy titles, scripts or footage): ' % d.get('updated', '?') + t + '\n') if t else ''
        except Exception:
            continue
    return ''


import re as _re
_LEN = _re.compile(r'narrative|\blong\b|descriptive|\d+\s*[-\u2011 ]?\s*words?\b|word titles|short titles?|concise titles?', _re.I)   # DATAFIX 2026-11-05: length advice contradicted the data (best posts have long person-story titles)


def _keep(items):
    return [x for x in (items or []) if not _LEN.search(str(x))]


def guidance(brand, kind='short'):
    for base in (Path('data/learned'), Path(__file__).resolve().parent / 'data' / 'learned', Path(__file__).resolve().parent.parent / 'data' / 'learned'):
        f = base / (brand + '.json')
        try:
            d = json.loads(f.read_text())
            top = d.get('updated', '?')
            d = d.get(kind) or d.get('full' if kind == 'short' else 'short') or d     # other format's notes when this one has none yet
            d.setdefault('updated', top)
            d = dict(d); d['do_more'] = _keep(d.get('do_more')); d['avoid'] = _keep(d.get('avoid')); d.pop('title_style', None)
            if d.get('do_more') or d.get('avoid'):
                t = '\nLEARNED FROM OUR REAL VIEWERS (updated %s, based on %s videos): ' % (d.get('updated', '?'), d.get('n', '?'))
                if d.get('do_more'):
                    t += 'DO MORE: ' + ' | '.join(d['do_more'][:5]) + '. '
                if d.get('avoid'):
                    t += 'DO LESS: ' + ' | '.join(d['avoid'][:5]) + '. '
                if d.get('title_style'):
                    t += 'TITLE/HOOK STYLE THAT WORKS: ' + d['title_style'] + '. '
                t += 'WHAT OUR NUMBERS SHOW: openings about a named person doing something specific get the most views; warning-style openers get the fewest. '
                return t + 'Apply this, but keep every other rule above.\n' + trending(brand)
        except Exception:
            continue
    return trending(brand)


_base_guidance = guidance


def guidance(brand, kind='short'):
    """Notes from viewers (above) + HARD NUMBERS from growth.py (Shorts only; small data = a nudge)."""
    g = _base_guidance(brand, kind)
    if kind != 'short':
        return g
    try:
        import growth
        return g + growth.guidance(brand)
    except Exception:
        return g


_viral_prev = guidance


def guidance(brand, kind='short'):
    """+ LOW-WEIGHT hints from big hits on other channels (viral.py, roadmap V). Always labelled unproven."""
    g = _viral_prev(brand, kind)
    try:
        import viral
        return g + viral.guidance(brand)
    except Exception:
        return g
