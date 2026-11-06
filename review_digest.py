"""REVIEW DIGEST: tells the owner (GitHub mobile push + email) how many videos wait for approve/skip. One persistent Issue 'REVIEW QUEUE'; each digest is a comment that @mentions the owner.
Silent when nothing waits. Never labelled 'review', so no other workflow touches it."""
import json, os, subprocess, datetime
OWNER = os.environ.get('DIGEST_OWNER', 'zerenaod-ux')
TITLE = 'REVIEW QUEUE'


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


def waiting():
    L = json.loads(sh('gh', 'issue', 'list', '--state', 'open', '--label', 'review', '--limit', '100', '--json', 'number,title,labels,url').stdout or '[]')
    return [i for i in L if not ({'approve', 'skip'} & {l['name'] for l in i['labels']})]


def system(t):
    h = t.split(':')[0]
    return 'MindLore' if 'ML' in h else ('Doodles' if 'DOODLES' in h else 'ShelfMade')


def build(w):
    by = {}
    for i in w:
        by.setdefault(system(i['title']), []).append(i)
    head = ', '.join('%s %d' % (k, len(v)) for k, v in sorted(by.items()))
    lines = ['@%s %d video%s waiting for your review (%s).' % (OWNER, len(w), '' if len(w) == 1 else 's', head), '']
    for i in sorted(w, key=lambda x: x['number']):
        kind = 'FULL' if 'FULL' in i['title'].split(':')[0] else 'Short'
        lines.append('- #%d [%s] %s' % (i['number'], kind, i['title'].split(':', 1)[-1].strip()[:80]))
    lines += ['', 'Approve or skip: on your laptop run the GitHub Review page, or on your phone open the Issue and add the label **approve** or **skip**.']
    return '\n'.join(lines)


def main():
    w = waiting()
    ex = json.loads(sh('gh', 'issue', 'list', '--state', 'all', '--search', TITLE + ' in:title', '--json', 'number,title,state', '--limit', '10').stdout or '[]')
    ex = [e for e in ex if e['title'] == TITLE]
    n = ex[0]['number'] if ex else None
    if not w:
        if n and ex[0]['state'] == 'OPEN':
            sh('gh', 'issue', 'close', str(n), '--comment', 'Queue is empty. Nothing waits for your review.')
        print('digest: nothing waiting'); return
    body = build(w)
    if n is None:
        print(sh('gh', 'issue', 'create', '--title', TITLE, '--body', body).stdout.strip())
    else:
        if ex[0]['state'] != 'OPEN':
            sh('gh', 'issue', 'reopen', str(n))
        sh('gh', 'issue', 'comment', str(n), '--body', body)
    print('digest sent for', len(w), 'video(s)')


if __name__ == '__main__':
    main()
