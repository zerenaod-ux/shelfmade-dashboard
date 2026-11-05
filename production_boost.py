"""Time-boxed extra Shorts production for ShelfMade (builds a review buffer while reach grows).
production-boost.json: {"shorts_per_day": 5, "until": "2026-11-11", "normal": 3}. After the 'until' date it falls back to 'normal'."""
import json,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
CFG=Path(__file__).resolve().parent/'production-boost.json'
def _cfg():
 try:return json.loads(CFG.read_text())
 except (OSError,ValueError):return {}
def shorts_target():
 c=_cfg();normal=int(c.get('normal',3))
 try:
  until=datetime.date.fromisoformat(c['until']);today=datetime.datetime.now(ZoneInfo('America/Chicago')).date()
  return max(normal,min(8,int(c['shorts_per_day']))) if today<=until else normal
 except (KeyError,ValueError,TypeError):return normal
def attempt_limit():return shorts_target()+30 # headroom so deterministic failures never starve the day's quota
