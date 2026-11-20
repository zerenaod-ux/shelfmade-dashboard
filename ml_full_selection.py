"""Select fresh MindLore full-video scripts without a persistent replay override."""
import json
import re
from pathlib import Path


def title_key(value):
    return re.sub(r'\W+', ' ', str(value or '').casefold()).strip()


def select_scripts(root, built, series, requested='', known_titles=()):
    scripts = {}
    for path in sorted(Path(root).glob('*.json')):
        data = json.loads(path.read_text())
        if data.get('story_v2'):
            scripts[path.stem] = data
    used = set(built)
    seen = {title_key(x) for x in known_titles if title_key(x)}
    for sid in used:
        path = Path(root) / (sid + '.json')
        if path.exists():
            data = json.loads(path.read_text())
            key = title_key(data.get('public_title') or data.get('title'))
            if key:
                seen.add(key)
    order = list(dict.fromkeys([x for x in series if x in scripts] + list(scripts)))
    if requested:
        if requested not in scripts:
            raise ValueError('Requested script is missing or not an eligible story script')
        if requested in used:
            raise ValueError('Requested full video was already built; refusing a repeat')
        order = [requested]
    selected = []
    for sid in order:
        key = title_key(scripts[sid].get('public_title') or scripts[sid].get('title'))
        if sid in used or not key or key in seen:
            continue
        selected.append(sid)
        seen.add(key)
    if requested and not selected:
        raise ValueError('Requested full video repeats an existing title')
    return selected
