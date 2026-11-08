"""ShelfMade story Shorts in the ORIGINAL ShelfMade look (stock footage + Kokoro Heart voice + word captions), with the new STRICT story wording.
Reads story-shorts/shelfmade/*.json, turns the narration into hook / points / cta, runs worker.py (STORY_SCRIPT hook), zips final.mp4 + POST_THIS.txt as sm-story-<id>.zip.
MindLore keeps the stick-man engine (gh_story_short.py). The two channels must never share visuals."""
import json, sys, os, re, shutil, subprocess
from pathlib import Path
sys.path.insert(0, '.'); sys.path.insert(0, 'generator')
def load(p, d):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def sents(t): return [s.strip() for s in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', t).strip()) if s.strip()]
def find_book(s):
    books = load('books.json', []); th = (s.get('theme') or '') + ' ' + s.get('title', '')
    for b in books:
        if b['title'].lower() in th.lower(): return b
    for b in books:
        if b['title'].lower() == s.get('title', '').lower(): return b
    return None
def make_script(s, book):
    ss = sents(' '.join(x.get('narration', '') for x in s['sections']))
    hook = ss[0]; i = 1
    while len(hook.split()) < 6 and i < len(ss): hook += ' ' + ss[i]; i += 1
    cta = ss[-1]; mid = ss[i:-1]
    points = [' '.join(mid[j:j + 2]) for j in range(0, len(mid), 2)]
    url = 'https://www.gutenberg.org/ebooks/' + book['id']
    import opening_design
    ev = [{'chapter': 'Evidence', 'kind': 'named research claim', 'excerpt': '%s (%s): %s' % (c.get('who'), c.get('year'), c.get('claim')), 'source_url': url, 'verification': 'Named researcher/year checked against Wikipedia by the story gate.'} for c in s.get('claims', []) if isinstance(c, dict)]
    ev.append({'chapter': 'Book', 'kind': 'editorial paraphrase with source context', 'excerpt': hook, 'source_url': url, 'verification': 'Compare with the linked book.'})
    script = {'hook': hook, 'title': book['title'], 'points': points, 'cta': cta, 'thumbnail_headline': _hl(s.get('thumbnail_headline'), hook),
              'public_title': _ft(s['public_title'])[:100], 'source_evidence': ev, 'source_kind': 'story'}
    evidence = {'version': 'story-v2-shelfmade', 'edition': 1, 'edition_capacity': 1, 'hook': hook, 'source_sentences': [hook], 'source_url': url, 'source_checkpoints': ev}
    return script, evidence
def _hl(h, hook):
    import opening_design
    try:
        import creative_quality as cq
        if h and cq.related(h, hook): return h
    except Exception: return h or opening_design.short_headline(hook)
    return opening_design.short_headline(hook)
def _ft(t):
    try:
        import growth; return growth.fix_title(__import__('os').environ.get('BRAND', 'shelfmade'), t)
    except Exception: return t

def main(n):
    state = Path('gh-state/built-story-shorts-shelfmade-old.json'); state.parent.mkdir(exist_ok=True); built = load(state, [])
    todo = [p for p in sorted(Path('story-shorts/shelfmade').glob('*.json')) if p.stem not in built][:n]
    Path('out').mkdir(exist_ok=True); made = 0
    for p in todo:
        sid = p.stem; s = load(p, {}); book = find_book(s)
        if not book: print('no book match for', sid, s.get('title')); continue
        folder = Path('out/o_' + sid); shutil.rmtree(folder, ignore_errors=True); print('=== Story Short (ShelfMade look)', sid, flush=True)
        script, evidence = make_script(s, book); sj = Path('story_script_%s.json' % sid); sj.write_text(json.dumps([script, evidence]))
        env = dict(os.environ, STORY_SCRIPT=str(sj.resolve()), SHELFMADE_MUSIC_DIR=str(folder.resolve() / '.render'), BRAND='shelfmade')
        r = subprocess.run([sys.executable, 'worker.py', json.dumps(book), '1', str(folder)], capture_output=True, text=True, timeout=1800, env=env)
        print((r.stdout + r.stderr)[-900:], flush=True); sj.unlink(missing_ok=True)
        if r.returncode or not (folder / 'final.mp4').is_file(): print('FAILED', sid); continue
        import story_rules, hashtags
        ev = story_rules.evidence_lines(s); tags = hashtags.shelfmade(s.get('hook', ''), 'short')
        text = _ft(s['public_title']) + '\n\n' + s['hook'] + '\n\n' + ('Evidence: ' + '; '.join(ev) + '\n\n' if ev else '') + 'Book: %s by %s. Classic books, explained on ShelfMade.\n\n' % (book['title'], book['author']) + tags
        z = folder / 'zip'; z.mkdir(exist_ok=True); shutil.copy(folder / 'final.mp4', z / 'final.mp4'); (z / 'POST_THIS.txt').write_text(text)
        subprocess.run('cd %s && zip -q %s final.mp4 POST_THIS.txt' % (z, Path('out').resolve() / ('sm-story-%s.zip' % sid)), shell=True, check=True)
        built.append(sid); state.write_text(json.dumps(built)); made += 1; print('BUILT', sid, flush=True); shutil.rmtree(folder, ignore_errors=True)
    print('made', made); sys.exit(0 if made else 1)
if __name__ == '__main__': main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
