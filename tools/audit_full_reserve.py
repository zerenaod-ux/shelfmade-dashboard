"""Offline maintenance audit. Writes a report only; never queues or renders media."""
import argparse,datetime,json,sqlite3,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import cinematic_content,visual_admission,generation_status

def audit():
 state=generation_status.snapshot();passed=[];blocked=[]
 for book in json.loads((BASE/'books.json').read_text()):
  try:
   script=cinematic_content.build(book['id']);coverage=visual_admission.require(script)
   passed.append({'book':book['id'],'title':book['title'],'words':sum(len(s['narration'].split()) for s in script['sections']),'chapters':coverage['chapters'],'original_passages_checked':sum(bool(e.get('exact_passage_verified')) for e in script['source_evidence']),'source_accuracy_requires_owner_review':True})
  except ValueError as error:blocked.append({'book':book['id'],'title':book['title'],'reason':str(error)})
 return {'brand':'shelfmade','checked_at':state['checked_at'],'scope':'Local source, creative and visual planning only','passed':passed,'blocked':blocked,'unused_full_sources_after_jobs_and_collection':state['full']['eligible_books'],'unused_short_sources_after_jobs_and_history':state['shorts']['eligible_books'],'planning_horizon_days':90,'full_source_gap_for_horizon':max(0,90-state['full']['eligible_books']),'short_source_gap_for_horizon':max(0,270-state['shorts']['eligible_books']),'footage_availability_verified':False,'finished_videos_created':0,'approvals_or_publications_created':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 result=audit();args.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['brand','unused_full_sources_after_jobs_and_collection','unused_short_sources_after_jobs_and_history','full_source_gap_for_horizon','short_source_gap_for_horizon','finished_videos_created']}))
