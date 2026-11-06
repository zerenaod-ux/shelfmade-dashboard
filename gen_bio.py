"""Builds bio/index.html: the 'link in bio' page (GitHub Pages). Every book from the videos -> Amazon search link with the Associates tag."""
import json, html
from pathlib import Path
import affiliate
ROOT = Path(__file__).resolve().parent
books = {}
for b in json.loads((ROOT / 'books.json').read_text()):
    books[str(b['id'])] = (b.get('title', ''), b.get('author', ''), 'shelfmade')
for f in sorted((ROOT / 'cinematic-scripts-mindlore').glob('*.json')):
    try:
        j = json.loads(f.read_text()); bid = f.stem.split('-')[0]
        if bid not in books and j.get('title'): books[bid] = (j['title'], j.get('author', ''), 'mindlore')
    except Exception: pass
rows = []
for bid, (t, a, br) in sorted(books.items(), key=lambda x: x[1][0].lower()):
    if not t: continue
    rows.append('<a class="b" href="%s" rel="sponsored noopener"><span class="t">%s</span><span class="a">%s</span><span class="g">Get the book &rarr;</span></a>' % (
        html.escape(affiliate.link(t, a, br), True), html.escape(t), html.escape(a)))
page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Books from our videos</title>
<style>:root{--bg:#0f1115;--fg:#f2f2f2;--card:#1b1e25;--mut:#9aa0ab;--acc:#f5b942}@media(prefers-color-scheme:light){:root{--bg:#f6f4ef;--fg:#1b1b1b;--card:#fff;--mut:#666;--acc:#b36b00}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,sans-serif}main{max-width:560px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:24px;margin:0 0 4px}p.s{color:var(--mut);margin:0 0 16px}input{width:100%%;padding:12px 14px;border-radius:12px;border:1px solid #8884;background:var(--card);color:var(--fg);font-size:16px;margin-bottom:14px}
.b{display:block;background:var(--card);border-radius:14px;padding:14px 16px;margin-bottom:10px;text-decoration:none;color:inherit;border:1px solid #8883}.b:active,.b:hover{border-color:var(--acc)}
.t{display:block;font-weight:650}.a{display:block;color:var(--mut);font-size:14px}.g{display:block;color:var(--acc);font-size:14px;margin-top:6px}footer{color:var(--mut);font-size:12px;margin-top:24px}</style></head><body><main>
<h1>Books from our videos</h1><p class="s">ShelfMade &amp; MindLore. Find the book from today's video and tap to get it.</p>
<input id="q" type="search" placeholder="Search a title or author" oninput="f(this.value)">
%s
<footer>As an Amazon Associate I earn from qualifying purchases. Links are affiliate links; the price for you does not change.</footer></main>
<script>function f(v){v=v.toLowerCase();document.querySelectorAll('.b').forEach(function(e){e.style.display=e.textContent.toLowerCase().indexOf(v)<0?'none':'block'})}</script></body></html>''' % '\n'.join(rows)
out = ROOT / 'bio'; out.mkdir(exist_ok=True); (out / 'index.html').write_text(page); (out / '.nojekyll').write_text('')
print('bio page:', len(rows), 'books')
