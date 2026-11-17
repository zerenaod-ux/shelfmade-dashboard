/* Shared phone/desktop publishing model. Never infer publication from a past due time. */
(function(root){
'use strict';
function platformRows(index,state,report,platform){
  if(!index||!Array.isArray(index.items)||!state||!state.done)return null;
  var done=(state&&state.done)||{},verified=(report&&report.saved)||[];
  var rows=index.items.filter(function(x){return x.folder==='saved'}).map(function(item){
    var record=done[item.tag+'/'+platform],remote=verified.filter(function(x){return x.tag?x.tag===item.tag:x.title===item.title})[0];
    var observations=remote&&remote.platforms&&remote.platforms[platform]||[];
    var match=observations.filter(function(x){return x.status!=='not_found_in_buffer'})[0];
    var status='ready',label='Ready to schedule',due=null;
    if(record&&/^SKIPPED/.test(record.remote||'')){status='held';label='Publishing held';}
    else if(match){
      due=match.due||null;
      if(match.status==='sent'){status='published';label='Published';}
      else if(match.status==='scheduled'){status='scheduled';label='Scheduled';}
      else if(match.status==='sending'){status='sending';label='Publishing';}
      else if(match.status==='error'||match.status==='failed'){status='failed';label='Needs attention';}
      else{status='pending';label='Status to confirm';}
    }else if(record&&record.remote){status='pending';label='Sent to publisher · verifying';due=record.due||null;}
    return {tag:item.tag,title:item.title,video:item.video,reviewed_at:item.reviewed_at,status:status,label:label,due:due};
  }).sort(function(a,b){var order={failed:0,ready:1,pending:2,sending:3,scheduled:4,published:5,held:6};return order[a.status]-order[b.status]||String(a.due||a.reviewed_at||'').localeCompare(String(b.due||b.reviewed_at||''));});
  rows.verified=!!(report&&report.complete);return rows;
}
function counts(rows){
  if(rows===null)return null;
  var c={ready:0,scheduled:rows.verified?0:null,published:rows.verified?0:null,attention:0,held:0};
  rows.forEach(function(x){if(x.status==='ready')c.ready++;else if(x.status==='scheduled'||x.status==='sending'){if(c.scheduled!==null)c.scheduled++;}else if(x.status==='published'){if(c.published!==null)c.published++;}else if(x.status==='held')c.held++;else c.attention++;});return c;
}
function freshness(report,now){var checked=Date.parse(report&&report.checked_at||'');return !Number.isFinite(checked)?'unavailable':now-checked>30*60*1000?'stale':'fresh';}
var api={platformRows:platformRows,counts:counts,freshness:freshness};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.StudioPublishing=api;
})(typeof window!=='undefined'?window:this);
