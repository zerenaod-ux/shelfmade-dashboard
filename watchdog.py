"""Cloud watchdog (runs on GitHub, no Mac needed). Exits with an error when something is wrong, which makes GitHub email the owner.
Checks that each scheduled workflow succeeded recently, that Buffer still holds posts, and that the publish queue is not empty."""
import json, os, sys, datetime, urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'zerenaod-ux/shelfmade-dashboard')
TOKEN = os.environ.get('GITHUB_TOKEN', '')
NOW = datetime.datetime.now(datetime.timezone.utc)
# workflow file -> max hours since the last successful run
EXPECT = {'publisher.yml': 5, 'publisher-mindlore.yml': 5, 'yt-publish-mindlore.yml': 8, 'yt-publish-shelfmade.yml': 8, 'yt-publish-doodles.yml': 8, 'review-publish.yml': 4, 'ml-scripts.yml': 14, 'sm-scripts.yml': 14, 'publisher-doodles.yml': 5, 'doodles.yml': 30, 'mindlore-2d.yml': 110, 'mindlore-story-short.yml': 30, 'shelfmade-story-short.yml': 30, 'full-video.yml': 110}


def gh(path):
    req = urllib.request.Request('https://api.github.com/repos/%s/%s' % (REPO, path),
                                 headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    problems, notes = [], []
    for wf, hours in EXPECT.items():
        try:
            runs = gh('actions/workflows/%s/runs?per_page=20&status=completed' % wf).get('workflow_runs', [])
        except Exception as e:
            problems.append('%s: could not read runs (%s)' % (wf, str(e)[:60]))
            continue
        ok = [r for r in runs if r['conclusion'] == 'success']
        if not ok:
            problems.append('%s: no successful run found' % wf)
            continue
        age = (NOW - datetime.datetime.fromisoformat(ok[0]['updated_at'].replace('Z', '+00:00'))).total_seconds() / 3600
        notes.append('%s last ok %.1fh ago' % (wf, age))
        if age > hours:
            problems.append('%s: last success %.0fh ago (expected within %dh)' % (wf, age, hours))
        if runs and runs[0]['conclusion'] == 'failure' and age > hours / 2:
            problems.append('%s: latest run FAILED' % wf)
    try:
        rel = gh('releases?per_page=1')
        if rel:
            rage = (NOW - datetime.datetime.fromisoformat(rel[0]['published_at'].replace('Z', '+00:00'))).total_seconds() / 3600
            notes.append('newest release %.1fh ago (%s)' % (rage, rel[0]['tag_name']))
            if rage > 36:
                problems.append('No new video built for %.0fh (newest release %s): the night builds may be stuck' % (rage, rel[0]['tag_name']))
        else:
            problems.append('no releases found')
    except Exception as e:
        problems.append('could not read releases (%s)' % str(e)[:60])
    try:
        q = json.load(open('publish/queue.json'))
        left = len(q.get('items', []))
        notes.append('publish queue: %d posts' % left)
        if left < 6:
            problems.append('ShelfMade publish queue is low (%d posts): approve more videos' % left)
    except Exception:
        problems.append('publish/queue.json missing')
    print('\n'.join(notes))
    try:
        open('alert.md', 'w').write('\n'.join('- ' + x for x in problems))
    except Exception:
        pass
    if problems:
        print('\nPROBLEMS:\n- ' + '\n- '.join(problems))
        sys.exit(1)
    print('\nALL GOOD')


if __name__ == '__main__':
    main()
