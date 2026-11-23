"""Pack a whiteboard build for the ShelfMade review/publish flow: python wb_pack.py OUTDIR short|long NAME -> out/sm-wb-NAME.zip
short: final.mp4 + POST_THIS.txt   long: NAME_LONGFORM.mp4 + POST_THIS.txt (same shapes review_publish.py already reads)."""
import sys, zipfile
from pathlib import Path

d, kind, name = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
out = Path('out'); out.mkdir(exist_ok=True)
z = out / ('sm-wb-%s.zip' % name)
with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as f:
    f.write(d / 'WHITEBOARD.mp4', 'final.mp4' if kind == 'short' else '%s_LONGFORM.mp4' % name)
    f.write(d / 'POST_THIS.txt', 'POST_THIS.txt')
print(z, z.stat().st_size // 1024, 'KB')
