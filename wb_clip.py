"""Cut a vertical Short out of a finished long whiteboard video's script: hook panel + the most surprising middle panel + the ending, 4/3/3 sentences.
Usage: python wb_clip.py LONG_OUTDIR CLIP_OUTDIR   (re-voices and re-renders vertical; same rules as any Short: 40-59 s)."""
import json, sys, copy
from pathlib import Path


def pick(script):
    ps = script['panels']
    mid = ps[1:-1] or ps
    best = max(mid, key=lambda p: sum(any(c.isdigit() for c in s['say']) + s['say'].endswith(('!', '?')) for s in p['sentences']))
    chosen = [(ps[0], slice(0, 5)), (best, slice(0, 4)), (ps[-1], slice(-4, None))]
    out = []
    for p, sl in chosen:
        q = copy.deepcopy(p); q['sentences'] = q['sentences'][sl]
        for s in q['sentences']:
            if s.get('item') and s['item'].get('kind') in ('arrow', 'cross'): s['item'] = None   # references may point at cut sentences
        out.append(q)
    return out


def main(long_dir, clip_dir):
    import wb_writer, wb_build
    s = json.loads((Path(long_dir) / 'script.json').read_text())
    panels = [wb_writer.clean_panel(p) for p in pick(s)]
    script = {'title': s['title'], 'topic': s.get('topic', ''), 'panels': panels}
    print('BUILT', wb_build.build(script, clip_dir, kind='short'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
