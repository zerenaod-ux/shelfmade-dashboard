const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const code=fs.readFileSync(require('node:path').join(__dirname,'../docs/app/playback.js'),'utf8');
function fixture(crossTab){const handlers={},events={},media=[{tagName:'VIDEO',paused:false,pause(){this.paused=true;}},{tagName:'VIDEO',paused:false,pause(){this.paused=true;}}];const sent=[];let channel;
 const context={document:{querySelectorAll:()=>media,addEventListener:(key,fn)=>{handlers[key]=fn}},window:{addEventListener:(key,fn)=>{events[key]=fn}}};
 if(crossTab)context.BroadcastChannel=function(){channel=this;this.postMessage=value=>sent.push(value);this.close=()=>{}};
 vm.runInNewContext(code,context);return{handlers,events,media,sent,get channel(){return channel}};}
test('starting one review video pauses the other without changing the active video',()=>{const f=fixture(false);f.handlers.play({target:f.media[1]});assert.equal(f.media[0].paused,true);assert.equal(f.media[1].paused,false);});
test('other Studio tabs and leaving the page stop stale playback',()=>{const f=fixture(true);f.handlers.play({target:f.media[1]});assert.equal(f.sent.length,1);f.channel.onmessage({data:{type:'studio-media-started'}});assert.equal(f.media[1].paused,true);f.media[0].paused=false;f.events.pagehide();assert.equal(f.media[0].paused,true);});
