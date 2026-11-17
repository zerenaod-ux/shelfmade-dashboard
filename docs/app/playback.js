/* One active Studio video/audio per browser, including other Studio tabs. */
(function(){
  'use strict';
  var channel=null;
  try{if(typeof BroadcastChannel!=='undefined')channel=new BroadcastChannel('studio-active-media');}catch(e){}
  function pauseOthers(active){document.querySelectorAll('video,audio').forEach(function(media){if(media!==active&&!media.paused)media.pause();});}
  document.addEventListener('play',function(event){
    var media=event.target;
    if(!media||!/^(VIDEO|AUDIO)$/.test(media.tagName))return;
    pauseOthers(media);if(channel)channel.postMessage({type:'studio-media-started'});
  },true);
  if(channel)channel.onmessage=function(event){if(event.data&&event.data.type==='studio-media-started')pauseOthers(null);};
  window.addEventListener('pagehide',function(){pauseOthers(null);if(channel)channel.close();});
})();
