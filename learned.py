"""Tiny helper for the writers: guidance(brand) returns the latest 'what viewers watch' notes (data/learned/<brand>.json) as prompt text, or '' when none/any problem."""
import json
from pathlib import Path


def guidance(brand):
    for base in (Path('data/learned'), Path(__file__).resolve().parent / 'data' / 'learned', Path(__file__).resolve().parent.parent / 'data' / 'learned'):
        f = base / (brand + '.json')
        try:
            d = json.loads(f.read_text())
            if d.get('do_more') or d.get('avoid'):
                t = '\nLEARNED FROM OUR REAL VIEWERS (updated %s, based on %s videos): ' % (d.get('updated', '?'), d.get('n', '?'))
                if d.get('do_more'):
                    t += 'DO MORE: ' + ' | '.join(d['do_more'][:5]) + '. '
                if d.get('avoid'):
                    t += 'DO LESS: ' + ' | '.join(d['avoid'][:5]) + '. '
                if d.get('title_style'):
                    t += 'TITLE/HOOK STYLE THAT WORKS: ' + d['title_style'] + '. '
                return t + 'Apply this, but keep every other rule above.\n'
        except Exception:
            continue
    return ''
