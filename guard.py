"""SAFETY GUARD: per-channel KILL SWITCH and a DAILY CAP, read by every publisher. Settings live in publish/guard.json:
  {"kill": {"shelfmade": false, "mindlore": false, "doodles": false}, "max_new_per_day": {"shelfmade": 12, "mindlore": 12, "doodles": 12}}
kill=true stops NEW posts for that channel (posts already waiting in Buffer are not recalled). The cap limits how many new posts one channel can schedule per UTC day,
so a bad batch can never flood a channel. Fails OPEN on a read error (a broken guard must not stop the business) but logs it. Flip it from the Health page or by editing the file."""
import datetime, json
from pathlib import Path
F = Path(__file__).resolve().parent / 'publish' / 'guard.json'
DEFAULT = {'kill': {'shelfmade': False, 'mindlore': False, 'doodles': False}, 'max_new_per_day': {'shelfmade': 12, 'mindlore': 12, 'doodles': 12}}
KINDMAP = {'mlfull': 'mindlore', 'shfull': 'shelfmade', 'ddfull': 'doodles'}


def load():
    try:
        return json.loads(F.read_text())
    except Exception as e:
        print('guard: cannot read guard.json (%s) - using defaults' % str(e)[:60])
        return DEFAULT


def brand(x):
    return KINDMAP.get(x, x)


def killed(b):
    return bool(load().get('kill', {}).get(brand(b), False))


def room_today(b, done):
    """How many more posts this channel may schedule today (UTC). done = the state['done'] dict (entries carry 'at')."""
    cap = int(load().get('max_new_per_day', {}).get(brand(b), 12))
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    used = sum(1 for v in (done or {}).values() if str(v.get('at', ''))[:10] == today)
    return max(0, cap - used)
