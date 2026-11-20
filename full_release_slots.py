"""Owner release cadence: MindLore full videos Wednesday/Saturday at 18:00 Chicago."""
import datetime
from zoneinfo import ZoneInfo
TZ=ZoneInfo('America/Chicago')

def next_release(taken, kind='mlfull', now=None):
    now=(now or datetime.datetime.now(TZ)).astimezone(TZ)
    day=now.date()
    for _ in range(730):
        slot=datetime.datetime.combine(day,datetime.time(18),TZ)
        if (kind!='mlfull' or day.weekday() in (2,5)) and day not in taken and slot>now+datetime.timedelta(minutes=30):
            return day,slot.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        day+=datetime.timedelta(days=1)
    raise ValueError('No release slot within two years')
