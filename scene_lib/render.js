// Renders a scene spec frame by frame with the scene engine.  node scene_lib/render.js <spec.json> [json list of sample frames]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), only = process.argv[3] ? new Set(JSON.parse(process.argv[3])) : null;
  const b = await chromium.launch(process.env.CHROME_CHANNEL ? { channel: process.env.CHROME_CHANNEL } : {});
  const p = await b.newPage({ viewport: { width: 720, height: 1280 } });
  let bad = 0; p.on('pageerror', e => { bad++; console.log('PAGEERR', e.message); });
  await p.goto('file://' + path.join(__dirname, 'scene.html'));
  const total = await p.evaluate(s => window.loadSpec(s), spec);
  fs.mkdirSync('fr', { recursive: true });
  for (let f = 0; f < total; f++) {
    if (only && !only.has(f)) continue;
    const d = await p.evaluate(i => window.frame(i), f);
    fs.writeFileSync(path.join('fr', String(f).padStart(4, '0') + '.jpg'), Buffer.from(d.split(',')[1], 'base64'));
    if (f % 200 === 0) console.log('frame', f, '/', total);
  }
  await b.close();
  if (bad) process.exit(1);
})();
