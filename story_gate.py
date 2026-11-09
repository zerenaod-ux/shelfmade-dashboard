"""How many MindLore story Shorts to build now? Inventory = YouTube posts approved-but-unsent + already scheduled in the future. Target 12 (~6 days at 2/day).
Prints a number 0..max. Lets the build workflow run several times a day (GitHub timers are late/skipped) without overbuilding."""
import json, sys, datetime
from pathlib import Path
brand = sys.argv[1] if len(sys.argv) > 1 else 'mindlore'; mx = int(sys.argv[2]) if len(sys.argv) > 2 else 3; target = int(sys.argv[3]) if len(sys.argv) > 3 else 12
def jl(p):
    try: return json.loads(Path(p).read_text())
    except Exception: return {}
sf = {'mindlore': 'state-mindlore.json', 'shelfmade': 'state.json'}[brand]; af = {'mindlore': 'approved-mindlore.json', 'shelfmade': 'approved.json'}[brand]
done = jl('publish/' + sf).get('done', {}); now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
fut = sum(1 for k, v in done.items() if k.endswith('youtube') and v.get('due', '')[:19] > now) if brand == 'mindlore' else 0
wait = sum(1 for i in jl('publish/' + af).get('items', []) if i.get('platform') == 'youtube' and i['id'] not in done)
inv = fut + wait; n = max(0, min(mx, target - inv)); print('inventory', inv, '(scheduled %d + waiting %d) -> build %d' % (fut, wait, n), file=sys.stderr); print(n)
