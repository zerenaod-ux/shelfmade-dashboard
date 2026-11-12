const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const mode = process.argv[2] || 'tune';
  const b = await chromium.launch(process.env.CHROME_CHANNEL ? { channel: process.env.CHROME_CHANNEL } : {});
  const p = await b.newPage({ viewport: { width: 720, height: 1280 } });
  p.on('pageerror', e => console.log('PAGEERR', e.message));
  await p.goto('file://' + path.join(__dirname, 'dam.html'));
  if (mode === 'tune') {
    for (const [q0, lk] of JSON.parse(process.argv[3])) console.log(q0, lk, JSON.stringify(await p.evaluate(([a, c]) => window.dryRun(a, c), [q0, lk])));
  } else {
    const [q0, lk] = JSON.parse(process.argv[3]); await p.evaluate(([a, c]) => window.setQ(a, c), [q0, lk]);
    const only = mode === 'sample' ? new Set(JSON.parse(process.argv[4])) : null;
    fs.mkdirSync(path.join(__dirname, 'fr'), { recursive: true });
    for (let f = 0; f < 900; f++) {
      const d = await p.evaluate(i => window.frame(i), f);
      if (!only || only.has(f)) fs.writeFileSync(path.join(__dirname, 'fr', String(f).padStart(4, '0') + '.jpg'), Buffer.from(d.split(',')[1], 'base64'));
      if (f % 150 === 0) console.log('frame', f);
    }
  }
  await b.close();
})();
