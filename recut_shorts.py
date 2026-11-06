"""WINNER RE-CUTS / SHORTS->FULL FUNNEL. For every approved full video that is already uploaded to YouTube, cut the best 30-58 s into a vertical Short that ends on a
'Watch the full video' card, and publish it as a release (tag mindlore-recut-/shorts-recut-/doodles-recut-) so review_publish makes a normal Review Issue (manual approve; stem has 'story' so it is never auto-approved).
Picks the chapter with the strongest title (question, number, strong word) after the opening one; when analytics exist later, feed winners first (RECUT_FIRST env = comma list of video ids).
State: gh-state/recut-done.json. Max RECUT_MAX per run (default 2). Needs ffmpeg + gh + GH_TOKEN."""
import json, os, re, subprocess, sys, tempfile, zipfile, datetime, shutil
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
KINDS = [('approved-mlfull.json', 'state-mlfull.json', 'mindlore', 'mindlore-recut-', 'MindLore'),
         ('approved-shfull.json', 'state-shfull.json', 'shelfmade', 'shorts-recut-', 'ShelfMade'),
         ('approved-ddfull.json', 'state-ddfull.json', 'doodles', 'doodles-recut-', 'Doodles')]
DONE = B / 'gh-state' / 'recut-done.json'
MAXN = int(os.environ.get('RECUT_MAX', '2'))
STRONG = re.compile(r"\b(why|how|never|secret|wrong|myth|truth|really|actually|warning|hidden|stop|nobody|real|brain|mind|ancient)\b", re.I)


def sh(*a, check=True):
    r = subprocess.run(a, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-400:])
    return r.stdout


def duration(p):
    return float(sh('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(p)).strip())


def chapters(desc):
    out = []
    for l in (desc or '').splitlines():
        m = re.match(r'^\s*(?:(\d+):)?(\d{1,2}):(\d\d)\s+(.+?)\s*$', l)
        if m:
            h, mi, s, t = m.groups()
            out.append((int(h or 0) * 3600 + int(mi) * 60 + int(s), t))
    return sorted(out)


def pick(desc, dur):
    """-> (start, length, chapter title). Strongest chapter after the opening one; at least 30 s, at most 58 s."""
    ch = chapters(desc)
    if len(ch) >= 3:
        best = None
        for i in range(1, len(ch) - 1):
            s, t = ch[i]
            e = ch[i + 1][0]
            sc = (2 if '?' in t else 0) + (1 if re.search(r'\d', t) else 0) + (1 if STRONG.search(t) else 0) + (0.5 if i <= 3 else 0) + (0.3 if e - s >= 30 else 0)
            if best is None or sc > best[0]:
                best = (sc, s, e, t)
        _, s, e, t = best
        L = min(58.0, e - s)
        if L < 30:
            L = min(45.0, dur - s - 1)
        return float(s), max(20.0, L), t
    s = dur * 0.30
    return s, min(45.0, dur - s - 1), ''


def font():
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'):
        if Path(f).is_file():
            return f
    return sh('fc-match', '-f', '%{file}', 'sans:bold', check=False).strip()


def cut(src, out, start, L, brand, channel):
    fx = font().replace(':', '\\:')
    end = max(0.0, L - 3.5)
    if brand == 'doodles':   # the picture is a vertical frame centred in 16:9: crop it to full screen
        base = "[0:v]crop=ih*9/16:ih,scale=1080:1920,setsar=1[v0];"
    else:                    # 16:9 -> vertical: blurred copy fills the screen, sharp video in the middle
        base = ("[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=28[bg];"
                "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v0];")
    card = ("[v0]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.72:t=fill:enable='gte(t,%.2f)',"
            "drawtext=fontfile='%s':text='Watch the full video':fontsize=92:fontcolor=white:x=(w-text_w)/2:y=h*0.40:enable='gte(t,%.2f)',"
            "drawtext=fontfile='%s':text='on the %s channel':fontsize=60:fontcolor=0xE0BD76:x=(w-text_w)/2:y=h*0.40+130:enable='gte(t,%.2f)'[v]") % (end, fx, end, fx, channel, end)
    sh('ffmpeg', '-v', 'error', '-y', '-ss', '%.2f' % start, '-t', '%.2f' % L, '-i', str(src), '-filter_complex', base + card, '-map', '[v]', '-map', '0:a:0',
       '-af', 'afade=t=out:st=%.2f:d=1.5' % max(0.0, L - 1.5), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-r', '30',
       '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(out))


def main():
    try:
        done = set(json.loads(DONE.read_text()))
    except Exception:
        done = set()
    first = [x for x in os.environ.get('RECUT_FIRST', '').split(',') if x]
    cand = []
    for appf, stf, brand, prefix, channel in KINDS:
        try:
            items = json.loads((B / 'publish' / appf).read_text())['items']
            st = json.loads((B / 'publish' / stf).read_text())['done']
        except Exception:
            continue
        for it in items:
            v = (st.get(it['id']) or {}).get('video')
            if v and it['id'] not in done:
                cand.append((0 if v in first else 1, it, v, brand, prefix, channel))
    cand.sort(key=lambda x: x[0])
    made = 0
    for _, it, vid, brand, prefix, channel in cand:
        if made >= MAXN:
            break
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                sh('gh', 'release', 'download', it['tag'], '--repo', REPO, '--pattern', it['zip'], '--dir', str(tmp))
                with zipfile.ZipFile(tmp / it['zip']) as z:
                    if any(n.startswith('/') or '..' in Path(n).parts for n in z.namelist()):
                        raise RuntimeError('unsafe zip')
                    z.extractall(tmp / 'x')
                vids = sorted((tmp / 'x').rglob('*_LONGFORM.mp4')) or sorted((tmp / 'x').rglob('final.mp4'))
                if not vids:
                    raise RuntimeError('no video in zip')
                src = vids[0]; dur = duration(src)
                s, L, ctitle = pick(it.get('description', ''), dur)
                sid = 'story-recut-%s' % re.sub(r'[^a-z0-9]+', '-', it['id'].lower()).strip('-')
                work = tmp / sid; work.mkdir()
                cut(src, work / 'final.mp4', s, L, brand, channel)
                full = it.get('title', '')
                title = (ctitle if len(ctitle.split()) >= 3 else full.split('|')[0].strip())[:90] or full[:90]
                tags = {'MindLore': '#MindLore #psychology #Shorts', 'ShelfMade': '#BookTok #booksummary #ShelfMade #Shorts', 'Doodles': '#Doodles #LeoAndMia #Shorts'}[channel]
                (work / 'POST_THIS.txt').write_text('%s\n\nFrom the full video: %s\nWatch the full video on the %s YouTube channel: https://youtu.be/%s\n\n%s\n' % (title, full, channel, vid, tags))
                zp = tmp / (sid + '.zip')
                with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
                    z.write(work / 'final.mp4', 'final.mp4'); z.write(work / 'POST_THIS.txt', 'POST_THIS.txt')
                tag = prefix + datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
                sh('gh', 'release', 'create', tag, str(zp), '--repo', REPO, '--title', 'Re-cut Short (%s): %s' % (channel, title[:60]), '--notes', 'Best %.0f s of the full video %s, ends on a Watch-the-full-video card. Review before posting.' % (L, vid))
            done.add(it['id']); made += 1
            print('recut ok', it['id'], 'start %.0f len %.0f' % (s, L), '->', tag, flush=True)
        except Exception as e:
            print('recut failed', it.get('id'), str(e)[:300], flush=True)
    DONE.parent.mkdir(exist_ok=True); DONE.write_text(json.dumps(sorted(done)))
    print('recut: made %d' % made)


if __name__ == '__main__':
    main()
