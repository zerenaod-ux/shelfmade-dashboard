"""GitHub side: turns every new Shorts build into a review Issue you can approve from the GitHub phone app.
For each new release 'shorts-*': upload the video to Cloudinary (30 fps copy, same as the studio), open one Issue per video with the video link and caption.
Label the issue 'approve' to queue it for all 3 platforms, or 'skip' to drop it. Run with --seed once to mark existing releases as already handled."""
import json, os, re, subprocess, sys, tempfile, zipfile, hashlib, time, urllib.request
from pathlib import Path

B = Path(__file__).resolve().parent
SEEN = B / 'review' / 'seen.json'
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')


def sh(*a, check=True, timeout=900):
    r = subprocess.run(a, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-300:])
    return r.stdout


def load(p, d):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return d


def tags():
    out = json.loads(sh('gh', 'release', 'list', '--repo', REPO, '--limit', '40', '--json', 'tagName'))
    return [r['tagName'] for r in out if r['tagName'].startswith(('shorts-', 'mindlore-', 'mlfull-', 'full-', 'doodles-', 'ddfull-'))]


def cloud_upload(video, brand='shelfmade'):
    c = json.loads(os.environ['CLOUDINARY_JSON_DOODLES'] if brand == 'doodles' else os.environ['CLOUDINARY_JSON'])
    fp = hashlib.sha256(Path(video).read_bytes()).hexdigest()
    out = Path(video).with_name(fp + '-30fps.mp4')
    sh('ffmpeg', '-v', 'error', '-y', '-i', str(video), '-map', '0:v:0', '-map', '0:a:0', '-vf', 'fps=30', '-c:v', 'libx264', '-preset', 'fast',
       '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(out))
    dfp = hashlib.sha256(out.read_bytes()).hexdigest()
    params = {'public_id': brand + '/' + dfp, 'timestamp': str(int(time.time())), 'overwrite': 'false'}
    signed = '&'.join(k + '=' + params[k] for k in sorted(params)) + c['api_secret']
    fields = {**params, 'api_key': c['api_key'], 'signature': hashlib.sha1(signed.encode()).hexdigest()}
    boundary = 'RV' + os.urandom(12).hex()
    body = bytearray()
    for k, v in fields.items():
        body.extend(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v)).encode())
    body.extend(('--%s\r\nContent-Disposition: form-data; name="file"; filename="video.mp4"\r\nContent-Type: video/mp4\r\n\r\n' % boundary).encode())
    body.extend(out.read_bytes())
    body.extend(('\r\n--%s--\r\n' % boundary).encode())
    req = urllib.request.Request('https://api.cloudinary.com/v1_1/%s/video/upload' % c['cloud_name'], bytes(body),
                                 {'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.load(r)
    url = res.get('secure_url', '')
    if not url.startswith('https://res.cloudinary.com/'):
        raise RuntimeError('Cloudinary did not return a link')
    return url


def qc(video, title, text, full=False, seen_titles=()):
    """Automatic quality checks shown in the Issue (advice only: a human still approves). Returns (ok, [lines])."""
    out = []
    try:
        j = json.loads(sh('ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height', '-of', 'json', str(video)))
        dur = float(j['format']['duration'])
        vs = [x for x in j['streams'] if x['codec_type'] == 'video']
        has_audio = any(x['codec_type'] == 'audio' for x in j['streams'])
        w, h = (vs[0]['width'], vs[0]['height']) if vs else (0, 0)
    except Exception as e:
        return False, ['FAIL cannot read the video file (%s)' % str(e)[:60]]
    def chk(ok, good, bad):
        out.append(('OK   ' if ok else 'WARN ') + (good if ok else bad))
        return ok
    r = [chk(has_audio, 'has audio', 'NO AUDIO track')]
    if full:
        r.append(chk(dur >= 300, 'length %d:%02d' % (dur // 60, dur % 60), 'shorter than 5 minutes (%d:%02d)' % (dur // 60, dur % 60)))
        r.append(chk(w >= 1280 and w > h, 'landscape %dx%d' % (w, h), 'not landscape HD (%dx%d)' % (w, h)))
        r.append(chk(len(text) <= 4900, 'description %d characters' % len(text), 'description too long (%d)' % len(text)))
    else:
        r.append(chk(15 <= dur <= 75, 'length %.0fs' % dur, 'length %.0fs is outside 15-75s' % dur))
        r.append(chk(h > w and h >= 1280, 'vertical %dx%d' % (w, h), 'not vertical HD (%dx%d)' % (w, h)))
        r.append(chk(len(text) <= 2200, 'caption %d characters (Instagram limit 2200)' % len(text), 'caption too long for Instagram (%d)' % len(text)))
    r.append(chk(0 < len(title) <= 100, 'title %d characters' % len(title), 'title empty or over 100 characters'))
    r.append(chk('_' not in text and 'Source-supported draft' not in text, 'no leftover markup', 'caption has leftover markup (_ or draft note)'))
    r.append(chk(title not in seen_titles, 'title is new', 'same title already reviewed before'))
    return all(r), out


def auto_approve(issue_url, brand, d):
    """Owner chose (2026-11-04, option A): Shorts of ShelfMade and MindLore that pass EVERY automatic check are approved without a manual label.
    Switch off any time:  gh variable set AUTO_APPROVE_SHORTS --body 0   Full videos and Doodles are never auto-approved."""
    num = int(issue_url.rstrip('/').split('/')[-1])
    tagname = {'mindlore': 'ml-'}.get(brand, '')
    out = Path('publish') / ({'mindlore': 'approved-mindlore.json'}.get(brand, 'approved.json'))
    cur = json.loads(out.read_text()) if out.is_file() else {'items': []}
    have = {i['id'] for i in cur['items']}
    for plat in ('youtube', 'instagram', 'tiktok'):
        iid = 'gh%d-%s%s' % (num, tagname, plat)
        if iid not in have and not any(i['platform'] == plat and i['title'] == d['title'] and i['text'] == d['text'] for i in cur['items']):
            cur['items'].append({'id': iid, 'platform': plat, 'title': d['title'], 'text': d['text'], 'url': d['url']})
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cur, indent=1))
    sh('gh', 'label', 'create', 'auto-approved', '--repo', REPO, '--color', '0E8A16', '--force', check=False)
    sh('gh', 'issue', 'edit', str(num), '--repo', REPO, '--add-label', 'auto-approved', check=False)
    sh('gh', 'issue', 'comment', str(num), '--repo', REPO, '--body', 'Auto-approved: every automatic check passed (owner setting for checked Shorts). Queued for YouTube, Instagram and TikTok. To stop auto-approval: gh variable set AUTO_APPROVE_SHORTS --body 0', check=False)
    sh('gh', 'issue', 'close', str(num), '--repo', REPO, check=False)
    print('auto-approved', num)



STYLE_WORDS = {'sm_candle': 'soft candlelit piano', 'sm_library': 'quiet library ambience', 'sm_gothic': 'dark gothic drone', 'sm_adventure': 'light adventurous strings', 'sm_tender': 'tender sad piano',
               'ml_lofi': 'lo-fi beat', 'ml_pulse': 'thinking pulse', 'ml_deep': 'deep mysterious drone', 'ml_wonder': 'airy wonder bells', 'ml_tension': 'tense electronic pulse',
               'dd_bounce': 'bouncy comedy', 'dd_quirky': 'quirky pizzicato comedy', 'dd_sneak': 'sneaky tiptoe comedy', 'dd_chill': 'chill feel-good', 'dd_hype': 'hype upbeat'}


def music_add(body, d):
    """Adds a plain 'Music:' line (what the director chose and why) to a Review Issue body. Never fails the issue."""
    try:
        m = json.loads((Path(d) / 'MUSIC.json').read_text())
        names = []
        for s in m.get('styles', []):
            n = STYLE_WORDS.get(s.replace('ace_', ''), s)
            if n not in names: names.append(n)
        pace = m.get('pace')
        feel = '' if not pace else (' - fast talker, so lighter music' if pace > 3.3 else (' - slow narration, so more melody' if pace < 2.2 else ''))
        ai = ' (AI-composed)' if any(str(t).startswith('ace_') for t in m.get('tracks', [])) else ''
        line = '**Music:** %s%s - mood %s%s' % (' > '.join(names), ai, m.get('mood', '?'), feel)
        return body.replace('\n---\n', '\n' + line + '\n\n---\n', 1) if '\n---\n' in body else body + '\n\n' + line
    except Exception:
        return body


def music_record(d, title):
    """Remembers the music used per video title (review/music-log.json) so music_learn.py can compare real viewer numbers by style."""
    try:
        m = json.loads((Path(d) / 'MUSIC.json').read_text())
        p = Path('review') / 'music-log.json'; log = json.loads(p.read_text()) if p.is_file() else {}
        log[title] = {'styles': m.get('styles', []), 'tracks': m.get('tracks', []), 'mood': m.get('mood'), 'pace': m.get('pace'), 'exp': m.get('exp'), 'brand': m.get('brand'), 'kind': m.get('kind'), 'date': __import__('datetime').date.today().isoformat()}
        p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(log, indent=1))
    except Exception:
        pass


def main():
    seen = load(SEEN, {'tags': [], 'issues': []})
    seen.setdefault('titles', [])
    for lb in ('checks-ok', 'checks-warn'):
        sh('gh', 'label', 'create', lb, '--repo', REPO, '--force', check=False)
    SEEN.parent.mkdir(exist_ok=True)
    if '--seed' in sys.argv:
        seen['tags'] = sorted(set(seen['tags']) | set(tags()))
        SEEN.write_text(json.dumps(seen, indent=1))
        print('seeded', len(seen['tags']), 'releases')
        return
    import captions
    import re as _re
    existing = set()
    try:   # every video that already has a Review Issue (open or closed): rerunning or racing runs must never open a second one
        for _b in json.loads(sh('gh', 'issue', 'list', '--repo', REPO, '--state', 'all', '--limit', '500', '--json', 'body', check=False) or '[]'):
            _m = _re.search(r'<!--DATA (\{.*?\}) DATA-->', _b.get('body') or '', _re.S)
            if _m:
                try:
                    _d = json.loads(_m.group(1)); existing.add(str(_d.get('tag')) + '/' + (str(_d.get('book')) if _d.get('book') else Path(str(_d.get('zip', ''))).stem))
                except Exception: pass
    except Exception as _e:
        print('existing-issue scan skipped:', str(_e)[:100])
    made = 0
    for tag in reversed(tags()):
        if tag in seen['tags']:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            sh('gh', 'release', 'download', tag, '--repo', REPO, '--pattern', '*.zip', '--dir', tmp, check=False)
            for z in sorted(Path(tmp).glob('*.zip')):
                if (tag + '/' + z.stem) in existing:
                    print('already has a Review Issue, skipped:', tag, z.stem)
                    continue
                d = Path(tmp) / ('x_' + z.stem)
                with zipfile.ZipFile(z) as f:
                    if any(n.startswith('/') or '..' in Path(n).parts for n in f.namelist()):
                        continue
                    f.extractall(d)
                video, post = d / 'final.mp4', d / 'POST_THIS.txt'
                if tag.startswith('ddfull-'):
                    if not video.is_file() or not post.is_file():
                        continue
                    raw = post.read_text(errors='ignore'); lines = [l.strip() for l in raw.splitlines() if l.strip()]
                    title = (lines[0] if lines else z.stem)[:100]
                    data = {'kind': 'ddfull', 'brand': 'doodles', 'tag': tag, 'zip': z.name, 'title': title, 'description': (raw.split('\n\n', 1)[1] if '\n\n' in raw else raw)[:4900]}
                    rel = 'https://github.com/%s/releases/tag/%s' % (REPO, tag)
                    body = ('## Review this Doodles FULL video (8-9 min, YouTube)\n\n**Watch:** download `%s` from %s\n\n**Title:** %s\n\n**Post text with chapters:**\n\n%s\n\n---\n'
                            'Label **approve** = keep it; **skip** = drop it. On approve it is uploaded to the Doodles YouTube channel (private, scheduled 18:00 Chicago on the next free day) once the one-time Doodles YouTube authorization is done.\n\n<!--DATA %s DATA-->' % (z.name, rel, title, raw[:3000], json.dumps(data)))
                    (Path(tmp) / 'body.md').write_text(music_add(body, d)); music_record(d, title)
                    out = sh('gh', 'issue', 'create', '--repo', REPO, '--title', 'Review DOODLES FULL: ' + title[:60], '--body-file', str(Path(tmp) / 'body.md'), '--label', 'review', '--label', 'checks-ok')
                    seen['issues'].append(out.strip()); seen['titles'].append(title); made += 1
                    continue
                if tag.startswith(('mlfull-', 'full-')):
                    ml_full = tag.startswith('mlfull-')
                    longs = sorted(d.glob('*_LONGFORM.mp4'))
                    if not longs or not post.is_file():
                        continue
                    raw = post.read_text(errors='ignore')
                    mt = re.search(r'--- TITLE ---\s*(.*?)\s*--- DESCRIPTION ---\s*(.*)', raw, re.S)
                    title = (mt.group(1).strip().splitlines()[0] if mt and mt.group(1).strip() else z.stem)[:100]
                    desc = (mt.group(2).strip() if mt else raw.strip())[:4900]
                    try:
                        import affiliate; desc = affiliate.add(desc, z.stem.split('-', 1)[1] if '-' in z.stem else z.stem, 'mindlore' if ml_full else 'shelfmade')
                    except Exception as _e: print('affiliate skipped:', str(_e)[:80])
                    okq, ql = qc(longs[0], title, desc, True, set(seen['titles']))
                    data = {'kind': 'mlfull' if ml_full else 'shfull', 'brand': 'mindlore' if ml_full else 'shelfmade', 'tag': tag, 'zip': z.name, 'title': title, 'description': desc}
                    rel = 'https://github.com/%s/releases/tag/%s' % (REPO, tag)
                    body = ('## Review this FULL video (%s, YouTube)\n\n**To post it: add the label `approve`. To drop it: add the label `skip`.**\n\n**Watch:** download `%s` from %s\n\n**Title:** %s\n\n**Description:**\n\n%s\n\n---\n'
                            '**Automatic checks:**\n```\n%s\n```\nTo schedule it on YouTube (18:00 Chicago, next free day): add the label **approve**. To drop it: **skip**.\n\n<!--DATA %s DATA-->' % ('MindLore' if ml_full else 'ShelfMade', z.name, rel, title, desc, '\n'.join(ql), json.dumps(data)))
                    (Path(tmp) / 'body.md').write_text(music_add(body, d)); music_record(d, title)
                    out = sh('gh', 'issue', 'create', '--repo', REPO, '--title', ('Review ML FULL: ' if ml_full else 'Review FULL: ') + title[:70], '--body-file', str(Path(tmp) / 'body.md'), '--label', 'review', '--label', 'checks-ok' if okq else 'checks-warn')
                    seen['issues'].append(out.strip())
                    seen['titles'].append(title)
                    made += 1
                    continue
                if not video.is_file() or not post.is_file():
                    continue
                raw = post.read_text(errors='ignore')
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                title = (lines[0] if lines else z.stem)[:100]
                text = __import__('re').sub(r'(?<![\w/])_([^_\n]+?)_(?![\w/])', r'\1', captions.clean(raw))  # book titles come as _Italic_ from Gutenberg
                brand = 'mindlore' if tag.startswith('mindlore-') else ('doodles' if tag.startswith('doodles-') else 'shelfmade')
                try:
                    import engage; text = engage.add(text, brand, title)
                except Exception as _e: print('engage skipped:', str(_e)[:80])
                okq, ql = qc(video, title, text, False, set(seen['titles']))
                url = cloud_upload(video, brand)
                data = {'book': z.stem, 'tag': tag, 'title': title, 'text': text, 'url': url, 'brand': brand}
                body = ('## Review this video\n\n**To post it: add the label `approve`. To drop it: add the label `skip`.**\n\n**Video:** %s\n\n**Title:** %s\n\n**Caption (all platforms):**\n\n%s\n\n**Automatic checks:**\n```\n%s\n```\n---\n'
                        'To publish it on YouTube, Instagram and TikTok: add the label **approve**. To drop it: add the label **skip**.\n\n'
                        '<!--DATA %s DATA-->' % (url, title, text, '\n'.join(ql), json.dumps(data)))
                (Path(tmp) / 'body.md').write_text(music_add(body, d)); music_record(d, title)
                out = sh('gh', 'issue', 'create', '--repo', REPO, '--title', {'mindlore': 'Review ML: ', 'doodles': 'Review DOODLES: '}.get(brand, 'Review: ') + title[:70], '--body-file', str(Path(tmp) / 'body.md'), '--label', 'review', '--label', 'checks-ok' if okq else 'checks-warn')
                seen['issues'].append(out.strip())
                seen['titles'].append(title)
                made += 1
                if okq and brand in ('shelfmade', 'mindlore') and os.environ.get('AUTO_APPROVE_SHORTS') == '1' and 'story' not in z.stem:   # story Shorts stay manual until the owner approves the format
                    try:
                        auto_approve(out.strip(), brand, data)
                    except Exception as e:
                        print('auto-approve skipped:', str(e)[:120])
        seen['tags'].append(tag)
        SEEN.write_text(json.dumps(seen, indent=1))
    print('review issues opened:', made)


if __name__ == '__main__':
    main()
