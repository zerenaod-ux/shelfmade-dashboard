"""WEEKLY REPORT in plain words (GitHub, Monday). Opens ONE Issue 'Weekly report <date>' from data/growth/scoreboard.json + history.json + selfcheck.json + deps.json.
Says what grew, what is weak, what the system changed, what needs the owner. Never posts anything public."""
import datetime, json, os, subprocess
from pathlib import Path
B = Path(__file__).resolve().parent
REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')


def jl(p, d):
    try:
        return json.loads((B / p).read_text())
    except (OSError, ValueError):
        return d


def build():
    sb, sc, dp = jl('data/growth/scoreboard.json', {}), jl('publish/selfcheck.json', {}), jl('publish/deps.json', {})
    L = ['## Weekly report - %s\n' % datetime.date.today().isoformat()]
    L.append('### Growth (last 7 days)')
    for b, v in (sb.get('brands') or {}).items():
        t, ch = v.get('totals', {}), v.get('change_7d')
        L.append('- **%s**: %d views, %d subscribers%s.' % (b.title(), t.get('views', 0), t.get('subs', 0),
                 (' (this week: +%d views, +%d subscribers, +%d videos)' % (ch['views'], ch['subs'], ch['videos'])) if ch else ' (week-over-week numbers appear after 7 days of history)'))
        top = (v.get('top') or [None])[0]
        if top: L.append('  - Best video: "%s" (%s views/day).' % (top['title'], top['vpd']))
        mo = v.get('monetization') or {}
        if mo: L.append('  - Pay threshold: %d/1000 subscribers, ~%s/4000 watch hours.' % (mo.get('subs_now', 0), mo.get('est_watch_hours')))
        win = [x for x in v.get('feature_lifts', []) if x['lift'] >= 1.6][:2]
        lose = [x for x in v.get('feature_lifts', []) if x['lift'] <= 0.6][:2]
        if win: L.append('  - Working: ' + '; '.join('%s = %s (%.1fx)' % (x['feature'], x['value'], x['lift']) for x in win))
        if lose: L.append('  - Not working: ' + '; '.join('%s = %s (%.1fx)' % (x['feature'], x['value'], x['lift']) for x in lose))
    lg = [e for e in jl('data/growth/title_log.json', []) if e.get('source') == 'auto' and not e.get('reverted')]
    if lg: L.append('- Titles auto-improved so far: %d Shorts (full list with old titles: data/growth/title_log.json; undo all: run workflow `retitle` with mode revert-all).' % len(lg))
    L.append('\n### System health')
    bad = [c for c in sc.get('checks', []) if not c.get('ok')]
    L.append('- Self-check: ' + ('everything verified.' if not bad else 'NEEDS A LOOK: ' + '; '.join('%s - %s' % (c['name'], c['text']) for c in bad)))
    hot = [r for r in dp.get('rows', []) if (r.get('used_percent') or 0) >= 60 or r.get('status') not in (None, 'up')]
    L.append('- Free services: ' + ('all up, none above 60% used.' if not hot else '; '.join('%s %s%% (%s)' % (r['name'], r.get('used_percent'), r.get('status')) for r in hot)))
    L.append('\n### Needs you')
    L.append('- Approve or skip the pending reviews (or turn Autopilot ON before you travel).')
    L.append('- Title proposals, if any, are in their own issue: add the label `titles-approved` to apply them.')
    return '\n'.join(L)


def main():
    title = 'Weekly report %s' % datetime.date.today().isoformat()
    body = build()
    print(body)
    r = subprocess.run(['gh', 'issue', 'list', '--repo', REPO, '--state', 'all', '--search', title + ' in:title', '--json', 'number'], capture_output=True, text=True)
    if json.loads(r.stdout or '[]'):
        print('already exists'); return
    subprocess.run(['gh', 'issue', 'create', '--repo', REPO, '--title', title, '--body', body, '--label', 'report'], check=False)


if __name__ == '__main__':
    main()
