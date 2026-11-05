"""GitHub side: an Issue labelled 'approve' puts its video in publish/approved.json (3 platform posts); 'skip' just closes it. Posts nothing itself."""
import json, os, re, sys, subprocess
from pathlib import Path

B = Path(__file__).resolve().parent
OUT = B / 'publish' / 'approved.json'
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


def main():
    ev = json.load(open(os.environ['GITHUB_EVENT_PATH']))
    label = ev['label']['name']
    issue = ev['issue']
    num = issue['number']
    labels = [l['name'] for l in issue['labels']]
    if 'review' not in labels or label not in ('approve', 'skip'):
        print('not a review decision'); return
    if label == 'skip':
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
            cur['items'].append({'id': iid, 'platform': plat, 'title': d['title'], 'text': d['text'], 'url': d['url']})
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cur, indent=1))
    sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Approved. Queued for YouTube, Instagram and TikTok; the publisher schedules it in the next free slots.')
    sh('gh', 'issue', 'close', str(num), '--repo', REPO)
    print('approved', num)


if __name__ == '__main__':
    main()
