"""Read-only book-series organizer: exact catalog ids and current verified receipts.
Lesson angles are local-summary planning suggestions, never generated videos or approvals.
"""
import json
from pathlib import Path
from audience_learning import identity
VERSION='book-series-v1'
SUMMARY=Path.home()/'Documents'/'ContentEmpire-Studio'/'PRODUCTS'/'ebook_content.json'
NETWORKS=('youtube','instagram','tiktok')

def suggestions(book,source):
 rows=[];seen=set()
 for idea in source.get('ideas',[]):
  title=' '.join(str(idea.get('title','')).split());explanation=' '.join(str(idea.get('explanation','')).split())
  if not title or not explanation or title.casefold() in seen:continue
  seen.add(title.casefold());rows.append({'angle':title,'context':explanation[:500],'source_url':'https://www.gutenberg.org/ebooks/'+book,'review_required':True})
  if len(rows)==3:break
 return rows

def snapshot(items,posts,books,summaries=None):
 if summaries is None:
  try:summaries=json.loads(SUMMARY.read_text())
  except (OSError,ValueError):summaries={}
 catalog={str(b['id']):b for b in books};groups={};unclassified=0
 for item in items:
  if not item.get('ready'):continue
  book=str(item.get('book_id',''));kind=item.get('content_type')
  if book not in catalog or kind not in ('short','full'):
   unclassified+=1;continue
  group=groups.setdefault(book,{'book_id':book,'title':catalog[book]['title'],'full':[],'shorts':[],'angles':suggestions(book,summaries.get(book,{}) or {})})
  receipts=[];seen=set();fingerprint=(item.get('quality') or {}).get('fingerprint')
  for post in posts:
   network=post.get('platform','youtube')
   if network not in NETWORKS or (kind=='full' and network!='youtube'):continue
   if post.get('item')!=item['id'] or not fingerprint or post.get('fingerprint')!=fingerprint or post.get('state')!='published':continue
   key=identity(network,post.get('url'))
   if not key or (network,key) in seen:continue
   seen.add((network,key));receipts.append({'platform':network,'url':post['url']})
  group['full' if kind=='full' else 'shorts'].append({'item':item['id'],'title':item['title'],'review_state':item.get('status','review'),'can_review':bool((item.get('quality') or {}).get('can_approve')),'published':receipts})
 series=list(groups.values())
 for group in series:
  group['has_public_full']=any(i['published'] for i in group['full']);group['has_public_short']=any(i['published'] for i in group['shorts']);group['connected']=group['has_public_full'] and group['has_public_short']
 series.sort(key=lambda g:(not g['connected'],not g['has_public_full'],g['title']))
 return {'available':True,'version':VERSION,'series':series,'unclassified_items':unclassified,'note':'Grouped by explicit book ids, never guessed from titles. Public links require matching current media fingerprints. Three lesson angles are planning suggestions from local summaries, not new videos or proof of unused ideas. Existing daily production and publishing controls are unchanged.'}
