"""SWEEP: finds Issues that already carry the owner's 'approve' or 'skip' label but are still open (GitHub drops a queued review-decide run when
several labels arrive at once) and records those decisions through review_decide.py. Safe to repeat: approvals are de-duplicated by id."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')


def main():
    r = subprocess.run(['gh', 'issue', 'list', '--repo', REPO, '--label', 'review', '--state', 'open', '--limit', '100', '--json', 'number,body,labels'], capture_output=True, text=True)
    try:
        issues = json.loads(r.stdout or '[]')
    except ValueError:
        issues = []
    for i in issues:
        names = [l['name'] for l in i['labels']]
        dec = 'skip' if 'skip' in names else ('approve' if 'approve' in names else None)
        if not dec:
            continue
        ev = {'label': {'name': dec}, 'issue': {'number': i['number'], 'body': i.get('body') or '', 'labels': [{'name': n} for n in names]}}
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(ev, f); p = f.name
        x = subprocess.run([sys.executable, str(B / 'review_decide.py')], env=dict(os.environ, GITHUB_EVENT_PATH=p), capture_output=True, text=True, cwd=str(B))
        os.unlink(p)
        print('sweep', dec, i['number'], 'ok' if x.returncode == 0 else 'FAILED ' + (x.stdout + x.stderr)[-150:])


if __name__ == '__main__':
    main()
