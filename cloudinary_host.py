"""Server-side signed video hosting; never exposes credentials to the browser."""
import base64, hashlib, json, os, re, time, urllib.request
from pathlib import Path
PRIVATE = Path(__file__).resolve().parent / 'private-cloudinary'

def credentials():
    try:
        data = json.loads((PRIVATE / 'credentials.json').read_text())
    except (OSError, ValueError):
        raise ValueError('Connect Cloudinary before publishing.') from None
    if not all(isinstance(data.get(k), str) and data[k] for k in ('cloud_name','api_key','api_secret')):
        raise ValueError('Cloudinary connection is incomplete.')
    return data

def upload_video(path, fingerprint):
    """Call only after the caller verifies approval and the media fingerprint."""
    data = credentials()
    path = Path(path)
    if not re.fullmatch(r'[a-f0-9]{64}', fingerprint):
        raise ValueError('Invalid reviewed video fingerprint.')
    if path.suffix.lower() != '.mp4' or not path.is_file():
        raise ValueError('A prepared MP4 video is required.')
    if path.stat().st_size > 95 * 1024 * 1024:
        raise ValueError('Video exceeds the current hosting upload limit.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', data['cloud_name']):
        raise ValueError('Invalid Cloudinary cloud name.')
    params = {'public_id':'shelfmade/'+fingerprint, 'timestamp':str(int(time.time())), 'overwrite':'false'}
    signed = '&'.join(k+'='+params[k] for k in sorted(params)) + data['api_secret']
    fields = {**params, 'api_key':data['api_key'], 'signature':hashlib.sha1(signed.encode()).hexdigest()}
    boundary = 'ShelfMade' + os.urandom(16).hex()
    body = bytearray()
    for key, value in fields.items():
        body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+value+'\r\n').encode())
    body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="video.mp4"\r\nContent-Type: video/mp4\r\n\r\n').encode())
    body.extend(path.read_bytes())
    body.extend(('\r\n--'+boundary+'--\r\n').encode())
    req = urllib.request.Request('https://api.cloudinary.com/v1_1/'+data['cloud_name']+'/video/upload', bytes(body), {'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.load(response)
    except Exception:
        raise ValueError('Video hosting failed. No platform post was submitted.') from None
    url = result.get('secure_url','')
    if not url.startswith('https://res.cloudinary.com/'+data['cloud_name']+'/video/upload/'):
        raise ValueError('Hosting did not return a valid video link.')
    return {'url':url, 'public_id':result.get('public_id'), 'bytes':result.get('bytes')}
