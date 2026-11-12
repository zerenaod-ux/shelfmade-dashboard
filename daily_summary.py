"""ONE DAILY SUMMARY in plain words (owner request 2026-11-11: 'I should only watch a video and say approve or skip').
Reads the real numbers daily_report.py saved (data/daily/history.json), the newest videos, selfcheck problems and the review queue. Posts ONE comment on a persistent issue 'DAILY SUMMARY'
that @mentions the owner (GitHub app push). Public repo: only public numbers go in, never private details."""
import json, os, subprocess, datetime
from pathlib import Path
B = Path(__file__).resolve().parent
OWNER = os.environ.get('DIGEST_OWNER', 'zerenaod-ux'); TITLE = 'DAILY SUMMARY'
NAMES = {'shelfmade': 'ShelfMade', 'mindlore': 'MindLore', 'doodles': 'AnimationDoodles'}
def load(p, d=None):
    try: return json.loads(Path(p).read_text())
    except Exception: return d
def sh(*a): return subprocess.run(a, capture_output=True, text=True)
def n(x): return format(int(x), ',')

def numbers():
    h = load(B / 'data/daily/history.json', {}); days = sorted(h)
    if len(days) < 2: return ['Numbers: collecting (need two days of data).'], None
    a, b = h[days[-2]], h[days[-1]]; lines = []
    for br in NAMES:
        tot, parts = 0, []
        for pl in ('youtube', 'tiktok', 'instagram'):
            k = '%s/%s' % (br, pl)
            if k in a and k in b and a[k].get('views') is not None and b[k].get('views') is not None:
                d = b[k]['views'] - a[k]['views']; nm = {'youtube': 'YouTube', 'tiktok': 'TikTok', 'instagram': 'Instagram'}[pl]
                if d < 0: parts.append('%s n/a (the source list changed)' % nm)   # a drop means posts left the source's list, not lost views
                else: tot += d; parts.append('%s %+d' % (nm, d))
        subs = ''
        ka, kb = '%s/youtube' % br, '%s/youtube' % br
        if a.get(ka, {}).get('subs') is not None and b.get(kb, {}).get('subs') is not None:
            ds = b[kb]['subs'] - a[ka]['subs']; subs = ', subscribers %s (%+d)' % (n(b[kb]['subs']), ds)
        lines.append('- **%s:** %+d views since last check (%s)%s' % (NAMES[br], tot, ', '.join(parts) or 'no data', subs))
    return lines, days[-1]

def best():
    out = []; cut = (datetime.datetime.utcnow() - datetime.timedelta(days=4)).isoformat()
    for br in NAMES:
        v = [x for x in (load(B / ('data/analytics/%s.json' % br), {}) or {}).get('videos', []) if x.get('published', '') >= cut and x.get('privacy', 'public') == 'public']
        if v:
            t = max(v, key=lambda x: x.get('views', 0)); out.append('- %s: "%s" (%s views, last 4 days)' % (NAMES[br], t.get('title', '')[:70], n(t.get('views', 0))))
    return out

def problems():
    c = load(B / 'publish/selfcheck.json', {}) or {}; bad = [x for x in c.get('checks', []) if not x.get('ok')]
    return ['- %s: %s' % (x['name'], x['text']) for x in bad]

def waiting():
    try:
        import review_digest; w = review_digest.waiting(); return len(w), [i['title'].split(':', 1)[-1].strip()[:60] for i in w][:5]
    except Exception: return None, []

def build():
    nums, day = numbers(); w, titles = waiting(); pr = problems(); bt = best()
    L = ['@%s Good morning. Here is your one daily summary (%s).' % (OWNER, datetime.date.today().isoformat()), '', '**Numbers (real data, change since the last check):**'] + nums
    if bt: L += ['', '**Best recent video per channel:**'] + bt
    L += ['', '**Needs you:**']
    L += (['- %d video%s waiting for approve or skip: %s' % (w, '' if w == 1 else 's', '; '.join(titles))] if w else ['- Nothing. No video is waiting for you.'])
    L += ['', '**Problems:**'] + (pr if pr else ['- None. All automatic checks are fine.'])
    L += ['', 'Your only jobs: watch a video, add the label **approve** or **skip**. Everything else runs by itself.']
    return '\n'.join(L)

def main():
    body = build(); print(body)
    ex = json.loads(sh('gh', 'issue', 'list', '--state', 'all', '--search', TITLE + ' in:title', '--json', 'number,title,state', '--limit', '10').stdout or '[]'); ex = [e for e in ex if e['title'] == TITLE]
    if not ex: print(sh('gh', 'issue', 'create', '--title', TITLE, '--body', body).stdout.strip())
    else:
        if ex[0]['state'] != 'OPEN': sh('gh', 'issue', 'reopen', str(ex[0]['number']))
        sh('gh', 'issue', 'comment', str(ex[0]['number']), '--body', body)
if __name__ == '__main__': main()
