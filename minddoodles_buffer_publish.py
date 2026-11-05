"""AnimationDoodles-only Buffer publishing adapter for reviewed Shorts.

Uses its own Buffer token and its own media-host credentials. No ShelfMade or
MindLore credentials are loaded here. Network writes happen only after the
owner presses the explicit publish action in the studio.
"""
import datetime, fcntl, hashlib, json, os, re, time, urllib.error, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PRIVATE = BASE / 'private-animationdoodles-buffer'
CONNECTION = PRIVATE / 'connection.json'
HOSTING = PRIVATE / 'hosting.json'
POSTS = PRIVATE / 'short-posts.json'
CHANNELS = {'instagram': '6adecbdb2f1f5ed648d318e9', 'tiktok': '6adecb442f1f5ed648d31611'}
HANDLES = {'instagram': 'animationdoodleshq', 'tiktok': 'animationdoodleshq'}
# YouTube channel 'Animation Doodles Studio' in the AnimationDoodles Buffer account (verified 2026-10-29).
ALL_CHANNELS = {**CHANNELS, 'youtube': '6adecc262f1f5ed648d31a5c'}
FIELDS = 'id channelId channelService text status externalLink sentAt error {message} assets {source} createdAt'

def _secure_file(path):
    if PRIVATE.is_symlink() or path.is_symlink():
        raise ValueError('AnimationDoodles private publishing storage is unsafe.')
    if not path.is_file() or PRIVATE.stat().st_mode & 0o077 or path.stat().st_mode & 0o077:
        raise ValueError('AnimationDoodles private publishing setup is incomplete.')
    return json.loads(path.read_text())

def status():
    try:
        connection = _secure_file(CONNECTION)
        rows = connection.get('channels', [])
        connected = connection.get('brand') == 'minddoodles' and all(
            any(row.get('platform') == p and row.get('id') == CHANNELS[p] and row.get('handle') == HANDLES[p] for row in rows)
            for p in CHANNELS)
        connected = connected and isinstance(connection.get('token'), str) and bool(connection['token'])
        hosting = _secure_file(HOSTING)
        host_ready = all(isinstance(hosting.get(k), str) and hosting[k] for k in ('cloud_name', 'api_key', 'api_secret'))
        return {'connected': connected, 'hosting_ready': host_ready,
                'publishing_ready': connected and host_ready,
                'message': ('Ready to publish reviewed Shorts through AnimationDoodles Buffer.' if connected and host_ready else
                            'Buffer channels are connected. Add a separate AnimationDoodles video-host account to finish setup.')}
    except (OSError, ValueError, TypeError):
        try:
            connection = _secure_file(CONNECTION); rows = connection.get('channels', [])
            connected = connection.get('brand') == 'minddoodles' and isinstance(connection.get('token'), str) and bool(connection['token']) and all(
                any(row.get('platform') == p and row.get('id') == CHANNELS[p] and row.get('handle') == HANDLES[p] for row in rows)
                for p in CHANNELS)
        except Exception:
            connected = False
        return {'connected': connected, 'hosting_ready': False, 'publishing_ready': False,
                'message': 'Buffer is connected; a separate AnimationDoodles video-host account is needed before publishing.' if connected else 'Connect AnimationDoodles Buffer first.'}

def save_hosting(body):
    if not isinstance(body, dict) or set(body) != {'cloud_name', 'api_key', 'api_secret'}:
        raise ValueError('Enter the three fields for AnimationDoodles video hosting.')
    values = {k: body[k].strip() if isinstance(body[k], str) else '' for k in body}
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', values['cloud_name']) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', values['api_key']) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', values['api_secret']):
        raise ValueError('Check the AnimationDoodles video-host details. Nothing was saved.')
    PRIVATE.mkdir(mode=0o700, exist_ok=True); PRIVATE.chmod(0o700)
    tmp = PRIVATE / 'hosting.pending'
    if tmp.is_symlink() or HOSTING.is_symlink(): raise ValueError('AnimationDoodles private publishing storage is unsafe.')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(values, out); out.flush(); os.fsync(out.fileno())
    os.replace(tmp, HOSTING); HOSTING.chmod(0o600)
    return status()

def _load_posts():
    try: return _secure_file(POSTS)
    except (OSError, ValueError, TypeError): return {'posts': []}

def _save_posts(data):
    PRIVATE.mkdir(mode=0o700, exist_ok=True); PRIVATE.chmod(0o700)
    tmp = PRIVATE / 'short-posts.pending'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(data, out, indent=2); out.flush(); os.fsync(out.fileno())
    os.replace(tmp, POSTS); POSTS.chmod(0o600)

def _request(token, document, variables=None):
    req = urllib.request.Request('https://api.buffer.com', json.dumps({'query': document, 'variables': variables or {}}).encode(),
        {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response: raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024: raise ValueError()
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get('errors') or not isinstance(result.get('data'), dict): raise ValueError()
        return result['data']
    except Exception:
        raise ValueError('Buffer did not confirm this publishing request. Check the saved result before retrying.') from None

def _upload(path, fingerprint):
    hosting = _secure_file(HOSTING)
    path = Path(path)
    if path.suffix.lower() != '.mp4' or not path.is_file() or path.stat().st_size > 95 * 1024 * 1024:
        raise ValueError('A supported MP4 under 95 MB is required; no post was submitted.')
    if not re.fullmatch('[a-f0-9]{64}', fingerprint): raise ValueError('The reviewed video fingerprint is invalid.')
    params = {'public_id': 'animationdoodles/' + fingerprint, 'timestamp': str(int(time.time())), 'overwrite': 'false'}
    signed = '&'.join(k + '=' + params[k] for k in sorted(params)) + hosting['api_secret']
    import hashlib as _hashlib
    fields = {**params, 'api_key': hosting['api_key'], 'signature': _hashlib.sha1(signed.encode()).hexdigest()}
    boundary = 'AnimationDoodles' + os.urandom(16).hex(); body = bytearray()
    for key, value in fields.items(): body.extend(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + key + '"\r\n\r\n' + value + '\r\n').encode())
    body.extend(('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="short.mp4"\r\nContent-Type: video/mp4\r\n\r\n').encode())
    body.extend(path.read_bytes()); body.extend(('\r\n--' + boundary + '--\r\n').encode())
    req = urllib.request.Request('https://api.cloudinary.com/v1_1/' + hosting['cloud_name'] + '/video/upload', bytes(body), {'Content-Type': 'multipart/form-data; boundary=' + boundary})
    try:
        with urllib.request.urlopen(req, timeout=180) as response: result = json.load(response)
    except Exception: raise ValueError('Video hosting failed; no social post was submitted.') from None
    url = result.get('secure_url', '')
    if not url.startswith('https://res.cloudinary.com/' + hosting['cloud_name'] + '/video/upload/'):
        raise ValueError('The video host did not return a valid public video URL; no social post was submitted.')
    return url

def _payload(platform, title, caption, url, due=None):
    metadata = {'instagram': {'type': 'reel', 'shouldShareToFeed': True, 'isAiGenerated': True},
                'tiktok': {'isAiGenerated': True},
                'youtube': {'title': title[:100], 'privacy': 'public', 'madeForKids': False, 'notifySubscribers': True, 'categoryId': '27'}}
    out = {'channelId': ALL_CHANNELS[platform], 'text': caption, 'schedulingType': 'automatic', 'mode': 'customScheduled' if due else 'shareNow',
            'needsApproval': False, 'saveToDraft': False,
            'assets': [{'video': {'url': url, 'metadata': {'thumbnailOffset': 1000}}}],
            'metadata': {platform: metadata[platform]}}
    if due: out['dueAt'] = due
    return out

def _next_due(platform):
    # Same slot logic as ShelfMade/MindLore. None = post now (slots file off or missing).
    try:
        import posting_slots
        return posting_slots.next_due(BASE / 'posting-slots-doodles.json', platform, reserve=True)
    except Exception:
        return None

def publish(platform, title, caption, path, fingerprint, package_id, key):
    if platform not in ALL_CHANNELS or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:-[a-z0-9-]{1,60})?', str(package_id)) or not re.fullmatch(r'short[1-3]', str(key)):
        raise ValueError('Choose one reviewed AnimationDoodles Short and destination.')
    if not isinstance(title, str) or not title.strip() or len(title) > 100 or not isinstance(caption, str) or len(caption) > 2200:
        raise ValueError('Review the title and caption lengths before publishing.')
    connection = _secure_file(CONNECTION); token = connection.get('token')
    if not isinstance(token, str) or not token: raise ValueError('Reconnect the AnimationDoodles Buffer account.')
    with (PRIVATE / 'publish.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load_posts(); records = data.setdefault('posts', [])
        existing = next((r for r in records if r.get('package_id') == package_id and r.get('key') == key and r.get('platform') == platform and r.get('fingerprint') == fingerprint), None)
        if existing:
            if existing.get('state') in ('submitting', 'unknown', 'sent', 'scheduled', 'queued'):
                return existing
            if existing.get('state') != 'failed': raise ValueError('A saved Buffer submission exists. Check its result before retrying.')
        url = _upload(path, fingerprint)
        record = {'package_id': package_id, 'key': key, 'platform': platform, 'fingerprint': fingerprint,
                  'state': 'submitting', 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if existing: records.remove(existing)
        records.append(record); _save_posts(data)
        document = 'mutation($input:CreatePostInput!){createPost(input:$input){... on PostActionSuccess{post{' + FIELDS + '}} ... on MutationError{message}}}'
        try:
            due = _next_due(platform); record['due_at'] = due
            result = _request(token, document, {'input': _payload(platform, title.strip(), caption.strip(), url, due)})['createPost']
            post = result.get('post') if isinstance(result, dict) else None
            if isinstance(result, dict) and not isinstance(post, dict) and isinstance(result.get('message'), str):
                record.update(state='failed', message=('Buffer rejected the post: ' + result['message'])[:280])
            elif not isinstance(post, dict) or post.get('channelId') != ALL_CHANNELS[platform] or post.get('channelService') != platform:
                record.update(state='unknown', message='Buffer response did not match this exact channel. Check Buffer before retrying.')
            else:
                record.update(remote_id=post.get('id'), state=post.get('status', 'unknown'), url=post.get('externalLink') or '',
                              message='Submitted to Buffer. Check status before retrying.' if post.get('status') not in ('sent', 'scheduled', 'queued', 'buffer') else '')
        except Exception:
            record.update(state='unknown', message='Buffer outcome is not confirmed. Check Buffer before retrying.')
        _save_posts(data)
        return record

def check(package_id):
    connection = _secure_file(CONNECTION); token = connection['token']; changed = False
    with (PRIVATE / 'publish.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load_posts()
        for record in data.get('posts', []):
            if record.get('package_id') != package_id or not record.get('remote_id') or record.get('state') in ('sent', 'failed'): continue
            result = _request(token, '{post(input:{id:' + json.dumps(record['remote_id']) + '}){' + FIELDS + '}}').get('post')
            if not isinstance(result, dict) or result.get('channelId') != ALL_CHANNELS.get(record.get('platform')): continue
            record.update(state=result.get('status', 'unknown'), url=result.get('externalLink') or '', checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            changed = True
        if changed: _save_posts(data)
        return [r for r in data.get('posts', []) if r.get('package_id') == package_id]

def records():
    try: return _load_posts().get('posts', [])
    except Exception: return []

def list_channels():
    """Read-only: which channels the AnimationDoodles Buffer account has (no token returned)."""
    conn = _secure_file(CONNECTION); token = conn['token']; org = conn.get('organization')
    if not isinstance(org, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', org): raise ValueError('Organization missing in connection.')
    d = _request(token, '{channels(input:{organizationId:' + json.dumps(org) + '}){id name displayName service isDisconnected isLocked}}')
    return [{k: c.get(k) for k in ('id', 'service', 'name', 'displayName', 'isDisconnected', 'isLocked')} for c in d.get('channels') or []]


def cancel(package_id):
    """Remove this package's not-yet-published posts from the Buffer queue. Returns one result per platform."""
    connection = _secure_file(CONNECTION); token = connection['token']; out = []
    with (PRIVATE / 'publish.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = _load_posts(); changed = False
        for record in data.get('posts', []):
            if record.get('package_id') != package_id or record.get('state') in ('sent', 'failed', 'cancelled'): continue
            if not record.get('remote_id'):
                record['state'] = 'cancelled'; changed = True; out.append({'platform': record.get('platform'), 'removed': True, 'note': 'never reached Buffer'}); continue
            try:
                r = _request(token, 'mutation{deletePost(input:{id:' + json.dumps(record['remote_id']) + '}){__typename ... on MutationError{message}}}')['deletePost']
                if isinstance(r, dict) and r.get('__typename') != 'MutationError':
                    record['state'] = 'cancelled'; changed = True; out.append({'platform': record.get('platform'), 'removed': True})
                else:
                    out.append({'platform': record.get('platform'), 'removed': False, 'note': str((r or {}).get('message', 'Buffer refused'))[:160]})
            except Exception as e:
                out.append({'platform': record.get('platform'), 'removed': False, 'note': str(e)[:160]})
        if changed: _save_posts(data)
    return out
