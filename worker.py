"""Isolated extractive/local-voice worker. No paid API credentials are loaded."""
import os,sys,json,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parent
for key in list(os.environ):
 if any(x in key for x in ('API_KEY','TOKEN','VOICE_ID')): os.environ.pop(key,None)
os.environ['USE_VIDEO_BG']='0';os.environ['SHELFMADE_LOCAL_MOTION']='1';os.environ['USE_STICKMAN']='0'
sys.path.insert(0,str(BASE/'generator'))
import make_video as mv
import booksummary
import source_cache
import content_logic
import creative_quality as cq
book=json.loads(sys.argv[1]);edition=int(sys.argv[2]) if len(sys.argv)>3 else 1;folder=Path(sys.argv[-1]).resolve();folder.mkdir(parents=True,exist_ok=True)
# Keep all output local to this job. Never load or write the original memory ledger.
mv.OUT=folder;mv.ASSETS=BASE/'generator'/'assets'
text=source_cache.read(book['id'],BASE/'decisions.sqlite3',BASE/'generated')
if text is None:text=booksummary.fetch_book(book['id'])
(folder/'source.txt').write_text(text)
used_passages=[]
for evidence_file in sorted((BASE/'generated').glob('*/*/content-review.json')):
 try:
  prior=json.loads(evidence_file.read_text())
  if prior.get('source_url')=='https://www.gutenberg.org/ebooks/'+str(book['id']):used_passages.extend(prior.get('source_sentences',[]))
 except (OSError,ValueError):continue
for _name in ('used-mac.json','used-gh.json','used-mindlore.json'):
 try:used_passages.extend(json.loads((BASE/'gh-state'/_name).read_text()).get('books',{}).get(book['id'],[]))
 except (OSError,ValueError):pass
script,evidence=(json.loads(Path(os.environ['STORY_SCRIPT']).read_text()) if os.environ.get('STORY_SCRIPT') else content_logic.build(book,text,edition=edition,used_passages=used_passages))
(folder/'edition.json').write_text(json.dumps({'book_id':book['id'],'edition':edition,'edition_capacity':evidence['edition_capacity'],'selection_version':'passage-edition-v1'},indent=2))
points=[script['hook'],*script['points']]
(folder/'content-review.json').write_text(json.dumps(evidence,indent=2))
(folder/'script.json').write_text(json.dumps(script,indent=2))
cq.save(folder,cq.require(cq.script_review(script,script['source_evidence'])))
# The owner-approved voice is mandatory; no silent or computer-voice fallback.
import local_voice
if not local_voice.available():raise RuntimeError('Kokoro Heart is unavailable. Restore the local voice runtime.')
mv._voice_segments=local_voice.segments
warning=''
(folder/'voice-settings.json').write_text(json.dumps({'engine':'Kokoro-82M','voice':'af_heart','speed':0.95,'local':True,'provider_cost_usd':0}))
video=mv.produce(script,folder,(96,140,205) if os.environ.get('BRAND')=='mindlore' else (212,160,23))
r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',video],capture_output=True,text=True,check=True)
media=json.loads(r.stdout)
if not any(x['codec_type']=='audio' for x in media['streams']) or not any(x['codec_type']=='video' for x in media['streams']):raise RuntimeError('Output missing audio or video')
(folder/'validation.json').write_text(json.dumps(media,indent=2))
cq.seal(folder,json.loads((folder/'creative-review.json').read_text()),'cover.jpg')
(folder/'POST_THIS.txt').write_text(script['public_title']+'\n\n'+book['title']+' by '+book['author']+'\n\n'+('Follow MindLore for a new psychology lesson every day. Full videos on YouTube: youtube.com/@mindloredaily' if os.environ.get('BRAND')=='mindlore' else 'Follow ShelfMade for a new classic-book lesson every day. Full videos on YouTube: youtube.com/channel/UCI4dLh_Uz4HrNq7NOetzbxQ')+'\n\n'+'\n\n'.join(points[:3])+'\n\nSource: https://www.gutenberg.org/ebooks/'+book['id']+'\n\n'+warning+'\n\nSource-supported draft. Review facts, wording and length before posting.\n'+(__import__('hashtags').mindlore if os.environ.get('BRAND')=='mindlore' else __import__('hashtags').shelfmade)(script['public_title']+' '+' '.join(points),'short'))
import footage_director
selection=json.loads((folder/'footage-selection.json').read_text())
with (folder/'POST_THIS.txt').open('a') as out:out.write('\n\n'+footage_director.credit_block(selection['assets'],2000))
footage_director.commit(folder,selection['assets'])
print('Finished; provider spend $0.00',flush=True)
