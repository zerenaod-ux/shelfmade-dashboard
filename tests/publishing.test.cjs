const test=require('node:test'),assert=require('node:assert/strict');
const model=require('../docs/app/publishing.js');
const index={items:[{tag:'one',title:'One',folder:'saved'},{tag:'two',title:'Two',folder:'saved'},{tag:'old',title:'Old',folder:'saved'},{tag:'skipped',title:'Skipped',folder:'delete'}]};
test('past scheduled time never masquerades as publication',()=>{
 const state={done:{'one/youtube':{remote:'remote',due:'2020-01-01'}}};
 const rows=model.platformRows(index,state,null,'youtube');
 assert.equal(rows.find(x=>x.tag==='one').status,'pending');assert.equal(model.counts(rows).published,null);
});
test('verified platform status and owner holds remain distinct',()=>{
 const state={done:{'old/youtube':{remote:'SKIPPED-by-owner'}}};
 const report={complete:true,saved:[{tag:'one',platforms:{youtube:[{status:'sent'}]}},{tag:'two',platforms:{youtube:[{status:'scheduled',due:'2030-01-01'}]}}]};
 assert.deepEqual(model.counts(model.platformRows(index,state,report,'youtube')),{ready:0,scheduled:1,published:1,attention:0,held:1});
 assert.equal(model.counts(model.platformRows(index,state,report,'tiktok')).ready,3);
});
test('unavailable data is not a reassuring zero and stale status is marked',()=>{
 assert.equal(model.counts(model.platformRows(null,null,null,'youtube')),null);
 assert.equal(model.freshness(null,Date.now()),'unavailable');
 assert.equal(model.freshness({checked_at:'2020-01-01'},Date.now()),'stale');
});
