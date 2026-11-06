"""GitHub side: an Issue labelled 'approve' puts its video in publish/approved.json (3 platform posts); 'skip' just closes it. Posts nothing itself."""
import json, os, re, sys, subprocess
from pathlib import Path

B = Path(__file__).resolve().parent
OUT = B / 'publish' / 'approved.json'
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


def _aff_text(d, plat, text):
    """YouTube copy of a Short gets the Amazon book link (clickable in the description); Instagram/TikTok stay link-free."""
    try:
        if d.get('brand') in ('shelfmade', 'mindlore') and plat in ('instagram', 'tiktok'):
            return text.rstrip() + '\n\nGet the book: link in bio'
        if plat != 'youtube' or d.get('brand') not in ('shelfmade', 'mindlore'): return text
        import affiliate
        for m in re.finditer(r'\d{3,6}', str(d.get('book', ''))):
            if affiliate.book_info(m.group(0))[0]:
                return affiliate.add(text, m.group(0), d['brand'], 4900)
    except Exception as e:
        print('affiliate skipped:', str(e)[:80])
    return text


def _note_skip(issue, num):
    """A skip teaches the writers: keep the skipped video's brand/format/title/opening line in data/learned/skips.json (newest 40 per brand). learner.py shows them to the model as 'the owner rejected these'."""
    m = re.search(r'<!--DATA (.*?) DATA-->', issue.get('body') or '', re.S)
    d = json.loads(m.group(1)) if m else {}
    brand = d.get('brand') or ('mindlore' if d.get('kind') == 'mlfull' else 'shelfmade' if d.get('kind') == 'shfull' else 'doodles' if d.get('kind') == 'ddfull' else '')
    if not brand:
        t = issue.get('title') or ''
        brand = 'mindlore' if ' ML' in t or 'MINDLORE' in t.upper() else 'doodles' if 'DOODLES' in t.upper() else 'shelfmade'
    title = d.get('title') or (issue.get('title') or '').split(':', 1)[-1].strip()
    text = (d.get('text') or d.get('description') or '').strip().split('\n')
    rec = {'issue': num, 'brand': brand, 'kind': 'full' if d.get('kind') in ('mlfull', 'shfull', 'ddfull') else 'short',
           'title': title[:120], 'opening': (text[0] if text else '')[:140], 'date': __import__('datetime').date.today().isoformat()}
    f = B / 'data' / 'learned' / 'skips.json'
    cur = json.loads(f.read_text()) if f.is_file() else []
    cur = [c for c in cur if c.get('issue') != num] + [rec]
    keep = []
    for b in {c['brand'] for c in cur}:
        keep += [c for c in cur if c['brand'] == b][-40:]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sorted(keep, key=lambda c: c['issue']), indent=1))


def main():
    ev = json.load(open(os.environ['GITHUB_EVENT_PATH']))
    label = ev['label']['name']
    issue = ev['issue']
    num = issue['number']
    labels = [l['name'] for l in issue['labels']]
    if 'review' not in labels or label not in ('approve', 'skip'):
        print('not a review decision'); return
    if label == 'skip':
        try:
            _note_skip(issue, num)
        except Exception as e:
            print('skip note failed:', str(e)[:100])
        sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Skipped. Nothing will be posted.')
        sh('gh', 'issue', 'close', str(num), '--repo', REPO); return
    m = re.search(r'<!--DATA (.*?) DATA-->', issue['body'] or '', re.S)
    if not m:
        sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Could not read this video data. Nothing queued.'); return
    d = json.loads(m.group(1))
    if d.get('kind') == 'ddfull':
        out = B / 'publish' / 'approved-ddfull.json'
        cur = json.loads(out.read_text()) if out.is_file() else {'items': []}
        iid = 'gh%d-ddfull' % num
        if iid not in {i['id'] for i in cur['items']}:
            cur['items'].append({'id': iid, 'tag': d['tag'], 'zip': d['zip'], 'title': d['title'], 'description': d['description']})
        out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(cur, indent=1))
        sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Approved. Queued for the Doodles YouTube channel (private, scheduled 18:00 Chicago on the next free day; needs the one-time Doodles YouTube authorization).')
        sh('gh', 'issue', 'close', str(num), '--repo', REPO); print('approved ddfull', num); return
    if d.get('kind') in ('mlfull', 'shfull'):
        suf = d['kind']
        out = B / 'publish' / ('approved-%s.json' % suf)
        cur = json.loads(out.read_text()) if out.is_file() else {'items': []}
        iid = 'gh%d-%s' % (num, suf)
        if iid not in {i['id'] for i in cur['items']}:
            cur['items'].append({'id': iid, 'tag': d['tag'], 'zip': d['zip'], 'title': d['title'], 'description': d['description']})
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(cur, indent=1))
        sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Approved. The full video is uploaded to YouTube and scheduled for the next free 18:00 slot.')
        sh('gh', 'issue', 'close', str(num), '--repo', REPO)
        print('approved full', num)
        return
    ml = d.get('brand') in ('mindlore', 'doodles')
    tagname = {'mindlore': 'ml-', 'doodles': 'dd-'}.get(d.get('brand'), '')
    out = B / 'publish' / ({'mindlore': 'approved-mindlore.json', 'doodles': 'approved-doodles.json'}.get(d.get('brand'), 'approved.json'))
    cur = json.loads(out.read_text()) if out.is_file() else {'items': []}
    have = {i['id'] for i in cur['items']}
    for plat in ('youtube', 'instagram', 'tiktok'):
        iid = 'gh%d-%s%s' % (num, tagname, plat)
        if iid not in have:
            cur['items'].append({'id': iid, 'platform': plat, 'title': d['title'], 'text': _aff_text(d, plat, d['text'].replace('Source-supported draft. Review facts, wording and length before posting.', '').replace('\n\n\n', '\n\n').strip()), 'url': d['url']})   # DRAFTNOTE
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cur, indent=1))
    sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Approved. Queued for YouTube, Instagram and TikTok; the publisher schedules it in the next free slots.')
    sh('gh', 'issue', 'close', str(num), '--repo', REPO)
    print('approved', num)


if __name__ == '__main__':
    main()
