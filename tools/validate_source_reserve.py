"""Explicit maintenance source import. Never queues, renders, approves or publishes.
Downloads only selected original Gutenberg texts, retains their fingerprints, and
checks the resulting extractive draft against the original text before admission.
"""
from pathlib import Path
import sys,json,re,html,hashlib,datetime,urllib.request,concurrent.futures
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'generator'))
import content_logic,daily_plan,jobs,booksummary
CANDIDATES=[('10741','The Essays of Arthur Schopenhauer: the Wisdom of Life','Arthur Schopenhauer'),('26716','The Crown of Wild Olive','John Ruskin'),('10715','The Essays of Arthur Schopenhauer; Counsels and Maxims','Arthur Schopenhauer'),('4320','An Enquiry Concerning the Principles of Morals','David Hume'),('3794','L. Annaeus Seneca on Benefits','Lucius Annaeus Seneca'),('3361','Letters to His Son, Complete','Earl of Philip Dormer Stanhope Chesterfield'),('26334','The Map of Life','William Edward Hartpole Lecky'),('39827','The Conduct of Life','Ralph Waldo Emerson'),('23860',"The Young Man's Guide",'William A. Alcott'),('7952','The Pleasures of Life','Sir John Lubbock'),('1293','Sesame and Lilies','John Ruskin'),('23347','Mental Efficiency, and Other Hints to Men and Women','Arnold Bennett'),('2541','Character','Samuel Smiles'),('12811','The Human Machine','Arnold Bennett'),('10417','Love, Life & Work','Elbert Hubbard'),('41901','The Victorious Attitude','Orison Swett Marden'),('51469','Self-Control, Its Kingship and Majesty','William George Jordan'),('44795','Aids to Reflection; and, The Confessions of an Inquiring Spirit','Samuel Taylor Coleridge'),('23092','The Simple Life','Charles Wagner'),('455','The University of Hard Knocks','Ralph Albert Parlette'),('68817','Happiness: Essays on the meaning of life','Karl Hilty')]
CANDIDATES += [('29433','Nature','Ralph Waldo Emerson'),('1022','Walking','Henry David Thoreau'),('20513','How to Succeed; Or, Stepping-Stones to Fame and Fortune','Orison Swett Marden'),('6312','Representative Men: Seven Lectures','Ralph Waldo Emerson'),('17195','A Message to Garcia','Elbert Hubbard'),('13160','An Iron Will','Orison Swett Marden and Abner Bayley'),('64059','How They Succeeded: Life Stories of Successful Men Told by Themselves','Orison Swett Marden'),('21622','Architects of Fate; Or, Steps to Success and Power','Orison Swett Marden'),('37036','The Key to Success','Russell H. Conwell'),('57651','Ambition and Success','Orison Swett Marden'),('14589','Certain Success','Norval A. Hawkins'),('21502','Fundamentals of Prosperity: What They Are and Whence They Come','Roger Ward Babson')]
def normalize(text):return re.sub('[^a-z0-9]','',html.unescape(text).casefold())
def fetch(book):
 ident,title,author=book;url='https://www.gutenberg.org/ebooks/'+ident
 request=lambda u:urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'ShelfMade source validation'}),timeout=45)
 with request(url) as r:page=r.read().decode('utf-8')
 plain=html.unescape(re.sub('<[^>]+>',' ',page));plain=' '.join(plain.split())
 if 'Public domain in the USA' not in plain or not re.search(r'Category\s+Text',plain) or not re.search(r'Language\s+English',plain):raise ValueError('Not an English public-domain text: '+title)
 if normalize(title) not in normalize(plain):raise ValueError('Primary catalogue title mismatch: '+title)
 source='https://www.gutenberg.org/cache/epub/'+ident+'/pg'+ident+'.txt'
 with request(source) as r:raw=r.read(8*1024*1024+1)
 if len(raw)>8*1024*1024:raise ValueError('Source exceeds bounded import size')
 text=raw.decode('utf-8-sig');header=text.split('*** START OF',1)[0]
 if normalize(title) not in normalize(header):raise ValueError('Original text header title mismatch: '+title)
 
 if normalize(author.split()[-1]) not in normalize(header):raise ValueError('Original author header mismatch: '+author)
 body=booksummary.strip_gutenberg(text);record={'id':ident,'title':title,'author':author};script,evidence=content_logic.build(record,body)
 # Mechanically check actual selected excerpts against this retained original.
 for point in script['source_evidence']:
  if normalize(point['excerpt']) not in normalize(body):raise ValueError('Draft excerpt not present in original')
 return record,raw,{'id':ident,'title':title,'author':author,'source_url':source,'canonical_url':url,'file':ident+'.txt','sha256':hashlib.sha256(raw).hexdigest(),'language':'English','copyright':'Public domain in the USA','checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_sentences':len(content_logic.candidates(body)),'requires_owner_review':True,'sample_script':script,'sample_evidence':evidence}
def main():
 report_path=BASE/'docs/source-reserve-import-2026-10-18.json'
 previous=json.loads(report_path.read_text()) if report_path.exists() else {}
 runs=previous.get('runs',[]) or ([previous] if previous else [])
 held={e['id'] for run in runs for e in run.get('rejected',[])}
 catalog=json.loads((BASE/'books.json').read_text());known={b['id'] for b in catalog};prior=daily_plan.history();new=[b for b in CANDIDATES if b[0] not in known and b[0] not in held and daily_plan.normalize(b[1]) not in prior]
 results=[];failures=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(fetch,b):b for b in new}
  for future in concurrent.futures.as_completed(futures):
   book=futures[future]
   try:results.append(future.result());print('VALIDATED',book[0],book[1],flush=True)
   except Exception as e:failures.append({'id':book[0],'title':book[1],'error':str(e)});print('NOT ADMITTED',book[0],str(e),flush=True)
 root=BASE/'sources/shelfmade';root.mkdir(parents=True,exist_ok=True);manifest=[]
 if (root/'catalogue.json').exists():manifest=json.loads((root/'catalogue.json').read_text())
 for book,raw,entry in sorted(results,key=lambda r:CANDIDATES.index((r[0]['id'],r[0]['title'],r[0]['author']))):
  (root/entry['file']).write_bytes(raw);manifest=[e for e in manifest if e['id']!=entry['id']]+[entry];catalog.append(book)
 pending=root/'catalogue.pending';pending.write_text(json.dumps(manifest,indent=2)+'\n');pending.replace(root/'catalogue.json')
 pending=BASE/'books.pending';pending.write_text(json.dumps(catalog,indent=2)+'\n');pending.replace(BASE/'books.json')
 runs.append({'added':len(results),'rejected':failures,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 report={'added_this_run':len(results),'retained_catalogue_total':len(manifest),'supported_total':len(catalog),'review_required':True,'generation_performed':False,'runs':runs};report_path.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='runs'}))
if __name__=='__main__':main()
