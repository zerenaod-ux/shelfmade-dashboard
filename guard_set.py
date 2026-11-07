"""Flip a channel's kill switch: python guard_set.py <shelfmade|mindlore|doodles|all> <on|off>. 'on' = KILL (stop new posts)."""
import json, sys
import guard
b, m = sys.argv[1], sys.argv[2]
g = guard.load(); g.setdefault('kill', {})
for k in (['shelfmade', 'mindlore', 'doodles'] if b == 'all' else [b]):
    g['kill'][k] = (m == 'on')
guard.F.write_text(json.dumps(g, indent=1)); print('kill switch', b, m)
