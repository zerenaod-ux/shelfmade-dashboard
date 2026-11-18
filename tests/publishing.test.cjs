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
test('review totals cover all four systems and exclude completed decisions',()=>{
 const a=[{title:'SHORT: Example',labels:[]},{title:'ML: Story',labels:[]},{title:'DOODLES: Story',labels:[]},{title:'FULL: approved',labels:[{name:'approve'}]}];
 const b=[{title:'How It Ticks: Ready',labels:[]},{title:'How It Ticks: Filed',labels:[{name:'ce-approve'}]}];
 const summary=model.reviewSummary(a,b);assert.equal(summary.total,4);assert.equal(summary.howitticks,1);assert.equal(summary.shelfmade,1);assert.equal(summary.mindlore,1);assert.equal(summary.doodles,1);
 assert.equal(model.reviewSummary(null,b).total,null);
});

test('job list retains the newest attempt per workflow including running and failed jobs',()=>{
 const runs=[{name:'Daily',created_at:'2026-11-16',status:'completed',conclusion:'success'},{name:'Daily',created_at:'2026-11-17',status:'in_progress',conclusion:null},{name:'Publish',created_at:'2026-11-17',status:'completed',conclusion:'failure'},{name:'Unrelated',created_at:'2026-11-17'}];
 const rows=model.latestJobs(runs,{Daily:'Creation',Publish:'Publisher'});
 assert.equal(rows.length,2);assert.equal(rows.find(x=>x.name==='Daily').status,'in_progress');assert.equal(rows.find(x=>x.name==='Publish').conclusion,'failure');
});
const fs=require('node:fs'),vm=require('node:vm');
const pageSource=fs.readFileSync(require('node:path').join(__dirname,'../docs/app/index.html'),'utf8');
test('review list follows a full first page and fails visibly on a later page error',async()=>{
 const source=pageSource.slice(pageSource.indexOf('function reviewRows('),pageSource.indexOf('function updateReviewCounts('));
 let calls=0;const scope={hdr:()=>({}),fetch:async()=>({ok:true,json:async()=>++calls===1?Array.from({length:100},(_,id)=>({id})):[{id:100}]})};
 vm.runInNewContext(source,scope);assert.equal((await scope.reviewRows('https://example.test','review')).length,101);assert.equal(calls,2);
 calls=0;scope.fetch=async()=>++calls===1?{ok:true,json:async()=>Array(100).fill({})}:{ok:false};assert.equal(await scope.reviewRows('https://example.test','review'),null);
});
test('simultaneous reads share a request but later refreshes make a new request',async()=>{
 const source=pageSource.slice(pageSource.indexOf('var pendingReads='),pageSource.indexOf('function hello('));
 let calls=0,release;const scope={fetch:()=>{calls++;return new Promise(r=>{release=r})}};vm.runInNewContext(source,scope);
 const first=scope.jget('https://example.test/data'),second=scope.jget('https://example.test/data');assert.equal(calls,1);release({ok:true,json:async()=>({value:1})});await Promise.all([first,second]);
 const refresh=scope.jget('https://example.test/data');assert.equal(calls,2);release({ok:true,json:async()=>({value:2})});assert.equal((await refresh).value,2);
});

test('old production stages are reported as last-known information, never current success',()=>{
 const old=model.stageView({label:'Rendering animation',updated_at:'2020-01-01'},Date.now());assert.equal(old.stale,true);assert.match(old.label,/Last reported/);
 assert.equal(model.stageView(null,Date.now()).label,'Production stage unavailable');
 const current=model.stageView({label:'Writing narration',updated_at:new Date().toISOString()},Date.now());assert.equal(current.stale,false);
});
