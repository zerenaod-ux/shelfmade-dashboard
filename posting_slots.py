"""Optional exact-time posting for Buffer. Does nothing unless posting-slots.json has "enabled": true.
Returns the next free slot as an ISO UTC string for Buffer's dueAt, or None (meaning: post immediately as before).
Each reserved slot is remembered so two posts never share one slot."""
import datetime,json
from pathlib import Path
from zoneinfo import ZoneInfo

def _load(path):
 try:return json.loads(Path(path).read_text())
 except (OSError,ValueError):return None

def next_due(config_path,platform,now=None,reserve=False):
 cfg=_load(config_path)
 if not isinstance(cfg,dict) or cfg.get('enabled') is not True:return None
 times=(cfg.get('slots') or {}).get(platform) or []
 if not times:return None
 tz=ZoneInfo(cfg.get('timezone','America/Chicago'))
 utc=datetime.timezone.utc
 now=(now or datetime.datetime.now(utc)).astimezone(tz)
 earliest=now+datetime.timedelta(minutes=int(cfg.get('min_lead_minutes',10)))
 ledger_path=Path(config_path).with_name('posting-slots-used.json')
 ledger=_load(ledger_path)
 taken=set(ledger.get(platform,[])) if isinstance(ledger,dict) else set()
 candidates=[]
 for offset in range(0,15):
  day=(now+datetime.timedelta(days=offset)).date()
  for t in times:
   hour,minute=[int(x) for x in t.split(':')]
   slot=datetime.datetime(day.year,day.month,day.day,hour,minute,tzinfo=tz)
   if slot>=earliest:candidates.append(slot.astimezone(utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'))
 for due in sorted(candidates):
  if due not in taken:
   if reserve:
    kept=[d for d in taken if d>=now.astimezone(utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')]
    data=dict(ledger) if isinstance(ledger,dict) else {}
    data[platform]=sorted(kept+[due]);ledger_path.write_text(json.dumps(data,indent=1))
   return due
 return None
