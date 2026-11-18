const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const html=fs.readFileSync('docs/app/index.html','utf8');
const source=html.slice(html.indexOf('function trackSceneFiling'),html.indexOf('function decideScene'));
function setup(what,response){
 const timers=[],messages=[],requests=[],card={isConnected:true,__arm:what,appendChild(x){messages.push(x)},remove(){this.isConnected=false}},buttons=[{},{}],item={number:51,labels:['scene-review']};
 const context={CE_API:'https://example.test',cache:{review:1},labels:x=>x.labels,el:(_tag,_cls,text)=>({textContent:text,setAttribute(){}}),updateReviewCounts(){},hdr:()=>({}),Date,fetch:async(url,options)=>{requests.push({url,options});if(response instanceof Error)throw response;return {ok:true,json:async()=>response}},setTimeout:(fn,delay)=>timers.push({fn,delay})};
 vm.createContext(context);vm.runInContext(source,context);context.trackSceneFiling(item,card,what,...buttons);
 return {timers,messages,requests,card,buttons,item,context};
}
for(const decision of ['approve','skip'])test(decision+' waits for durable closure without repeating the decision',async()=>{
 const s=setup(decision,{state:'closed'});assert.ok(s.buttons.every(x=>x.hidden&&x.disabled));assert.ok(s.item.labels.includes('ce-'+decision));assert.equal(s.context.cache.review,0);
 s.timers.shift().fn();await new Promise(setImmediate);assert.equal(s.requests.length,1);assert.equal(s.requests[0].options.method,undefined);assert.match(s.messages[0].textContent,decision==='approve'?/Saved/:/Delete/);s.timers.shift().fn();assert.equal(s.card.isConnected,false);
});
test('a status outage keeps the recorded decision visible and does not resubmit it',async()=>{const s=setup('approve',new Error('offline'));s.timers.shift().fn();await new Promise(setImmediate);assert.match(s.messages[0].textContent,/recorded.*unavailable/);assert.equal(s.card.isConnected,true);assert.equal(s.requests.length,1)});
