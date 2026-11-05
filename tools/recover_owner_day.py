"""Explicit maintenance CLI. No approval or publication actions."""
from pathlib import Path
import sys,argparse,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import owner_recovery as r
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=['short','full'],required=True);p.add_argument('--job',required=True);p.add_argument('--owner-request',required=True);a=p.parse_args()
print('OWNER RECOVERY AUTHORIZATION',a.kind,a.job,flush=True)
r.authorize(a.kind,a.job,a.owner_request)
print(json.dumps(r.run_one(a.kind,a.job)),flush=True)
