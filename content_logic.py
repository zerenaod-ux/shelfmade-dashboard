"""Source-supported, hook-first drafts. No claim that views alone measure quality."""
import re,collections
BAN=('gutenberg','copyright','license','translator','translation','footnote','edition','preface','contents','chapter','editor','vol.','page ')
def candidates(text):
 clean=re.sub(r'\s+',' ',text)
 rows=[]
 for sentence in re.split(r'(?<=[.!?])\s+',clean):
  sentence=sentence.strip(' []0123456789.-')
  sentence=re.sub(r'^Sun Tz[ŭu] said:\s*','',sentence)
  words=sentence.split()
  if not re.search(r'\b(thou|thee|thy|hath|doth|replied|quoth)\b|^O[ ,!]',sentence,re.I) and 7<=len(words)<=26 and sentence[:1].isupper() and not any(mark in sentence for mark in ['"','“','”']) and not any(x in sentence.lower() for x in BAN) and not re.search(r'\[[^]]*\]|\b\d{3,}\b',sentence):rows.append(sentence)
 return list(dict.fromkeys(rows))
def build(book,text,edition=1,used_passages=()):
 rows=candidates(text)
 if len(rows)<3:raise ValueError('Not enough clear source sentences. Choose another book or review the source.')
 def score(s):
  lower=s.lower();action=sum(bool(re.search(r'\b'+w+r'\b',lower)) for w in ['never','must','if','but','learn','knowledge','your','you','wise','cannot','should'])
  themes={'132':['enemy','victory','knowledge','battle','strategy','fight'],'4507':['thought','mind','character','purpose'],'2680':['mind','reason','nature','virtue'],'205':['life','simplicity','nature'],'935':['work','character','effort','perseverance']}
  relevance=sum(bool(re.search(r'\b'+w+r'\b',lower)) for w in themes.get(book['id'],['life','mind','learn','wisdom','truth','knowledge','character']))
  return relevance*5+action*2-abs(len(s.split())-12)/5
 # Select complete filmable lessons before spending time on narration.
 # Unsupported passages are excluded, never illustrated with generic scenery.
 import footage_director
 def filmable(sentence):
  try:footage_director.brief(sentence);return True
  except ValueError:return False
 ranked=[s for s in sorted(rows,key=score,reverse=True) if filmable(s)]
 if len(ranked)<3:raise ValueError('Not enough distinct source sentences with grounded visual briefs. Source planning stopped before narration.')
 distinct=[]
 def overlaps_used(sentence):
  words=set(re.findall(r'\w+',sentence.lower()))
  normalized=' '.join(re.findall(r'\w+',sentence.lower()))
  for prior in used_passages:
   other=set(re.findall(r'\w+',str(prior).lower()))
   if not words or not other:continue
   if normalized==' '.join(re.findall(r'\w+',str(prior).lower())):return True
   if len(words&other)/len(words)>.68:return True
  return False
 ranked=[s for s in ranked if not overlaps_used(s)]
 for s in ranked:
  words=set(re.findall(r'\w+',s.lower()))
  if any(len(words&set(re.findall(r'\w+',other.lower())))/max(1,len(words))>.7 for other in distinct):continue
  distinct.append(s)
 # Pick only evidence not already used by an earlier saved edition of this book.
 # The completed package records how many further three-passage editions remain.
 import os
 N=max(3,int(os.environ.get('SHELFMADE_SHORT_PASSAGES','8')))
 edition=max(1,int(edition));selected=distinct[:N]
 if len(selected)<3:raise ValueError('This source has no remaining set of three distinct, grounded passages for another draft. Choose another book with unused source passages.')
 edition_capacity=edition+max(0,(len(distinct)-3)//3)  # conservative: 3 passages per edition
 short=[s for s in selected if 7<=len(s.split())<=14]
 hook=short[0] if short else selected[0]
 # Hook is an exact source sentence (or cleaned attribution), not an invented claim.
 remaining=[s for s in selected if s!=hook][:N-1]
 hook_kind='source quotation'
 evidence_sentences=[hook,*remaining]
 # Editorial questions are grounded in explicit passages, never presented as quotations.
 profiles={
  '1497':('What if you mistook shadows for reality?',[
   ('shadows of the images','In the cave story, prisoners see shadows on a wall and mistake them for reality.'),
   ('eyes be dazzled','When they face the light, it hurts. Understanding takes time, not just a new view.')]),
  '205':('Is a simpler life a better life?',[
   ('frittered away by detail','Thoreau argues that life gets lost in details. He urges us to simplify our affairs.'),
   ('went to the woods because I wished to live deliberately','He goes to the woods to live deliberately and learn what life can teach him.')]),
 }
 profile=profiles.get(book['id']) if edition==1 else None
 clean_source=re.sub(r'\s+',' ',text)
 if profile and all(needle.lower() in clean_source.lower() for needle,_ in profile[1]):
  hook=profile[0];hook_kind='editorial question'
  remaining=[paraphrase for _,paraphrase in profile[1]]
  evidence_sentences=[]
  for needle,_ in profile[1]:
   at=clean_source.lower().index(needle.lower())
   evidence_sentences.append(clean_source[max(0,at-100):at+len(needle)+250])
 import creative_quality as cq
 import opening_design
 script={'hook':hook,'title':book['title'],'points':remaining,'cta':'One classic. One lesson. Follow ShelfMade.'}
 evidence={'version':'hook-first-v5-passage-editions','edition':edition,'edition_capacity':edition_capacity,'hook_kind':hook_kind,'opening_screen':'moving matched footage with short animated word groups','hook':hook,'source_sentences':evidence_sentences,'source_url':'https://www.gutenberg.org/ebooks/'+book['id'],'review_required':True,'notes':'Each edition uses a separate, non-overlapping set of source passages. Source-backed question or clear quotation first. Editorial questions are paraphrases, not author quotes. Image-led opening; no opaque title page. Performance is not guaranteed.'}
 script['thumbnail_headline']=opening_design.short_headline(hook)
 public_title=hook if len(hook)<=100 else script['thumbnail_headline'].capitalize()+' | '+book['title']
 while len(public_title)>100:public_title=public_title.rsplit(' ',1)[0]
 script['public_title']=public_title.rstrip(' |')
 script['creative_policy']=cq.VERSION
 checkpoints=[{'chapter':'Opening and lessons','kind':'source passage' if hook_kind=='source quotation' else 'editorial paraphrase with source context','excerpt':passage,'source_url':evidence['source_url'],'verification':'Compare wording and interpretation with the linked source.'} for passage in evidence_sentences]
 script['source_evidence']=checkpoints
 evidence['source_checkpoints']=checkpoints
 cq.require(cq.script_review(script,checkpoints))
 import creative_director
 script=creative_director.short(script,ranked)
 import hook_rules
 if os.environ.get('SHELFMADE_HOOK_RULES','1')=='1':script=hook_rules.apply(script,book,edition,evidence['source_url'])
 evidence.update(source_sentences=[point['excerpt'] for point in script['source_evidence'] if point.get('kind')!='editorial hook'],hook=script['hook'],hook_kind=('source quotation' if script['hook']!=hook else hook_kind),hook_type=script.get('hook_type','none'),source_checkpoints=script['source_evidence'],creative_director=script['creative_director'])
 return script,evidence
