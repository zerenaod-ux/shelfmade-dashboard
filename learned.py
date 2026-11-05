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


def guidance(brand, kind='short'):
    for base in (Path('data/learned'), Path(__file__).resolve().parent / 'data' / 'learned', Path(__file__).resolve().parent.parent / 'data' / 'learned'):
        f = base / (brand + '.json')
        try:
            d = json.loads(f.read_text())
            top = d.get('updated', '?')
            d = d.get(kind) or d.get('full' if kind == 'short' else 'short') or d     # other format's notes when this one has none yet
            d.setdefault('updated', top)
            if d.get('do_more') or d.get('avoid'):
                t = '\nLEARNED FROM OUR REAL VIEWERS (updated %s, based on %s videos): ' % (d.get('updated', '?'), d.get('n', '?'))
                if d.get('do_more'):
                    t += 'DO MORE: ' + ' | '.join(d['do_more'][:5]) + '. '
                if d.get('avoid'):
                    t += 'DO LESS: ' + ' | '.join(d['avoid'][:5]) + '. '
                if d.get('title_style'):
                    t += 'TITLE/HOOK STYLE THAT WORKS: ' + d['title_style'] + '. '
                return t + 'Apply this, but keep every other rule above.\n' + trending(brand)
        except Exception:
            continue
    return trending(brand)
