"""Hook rules v2 (ShelfMade). Pattern-interrupt opening <=9 words, answer held back, loop ending.
v2: 6 hook types, 25+ lines, uses book title OR author surname, and prefers a real short quote from the passage.
Records hook_type so results can be compared later."""
import hashlib,random,re
TYPES=['quote','contrarian','warning','myth','sting','curiosity','author']
LINES={
 'contrarian':['Almost everyone gets {T} wrong.','You were taught {T} wrong.','Stop reading {T} like this.','Everyone quotes {T}. Few get it.'],
 'warning':['Nobody warns you about {T}.','Read this before you open {T}.','Do not read {T} without this.','The part of {T} nobody mentions.'],
 'myth':['{T} is not what you think.','Forget what you know about {T}.','What {T} really asks of you.','You have {T} backwards.'],
 'sting':['One line in {T} hits hard.','This line from {T} stays with you.','Read this line from {T} twice.','This {T} line is uncomfortable.'],
 'curiosity':['Why does {T} still matter?','What did {T} see that we miss?','What is {T} really about?','Why is {T} still read today?'],
 'author':['{A} had a warning for you.','{A} said something uncomfortable.','Listen to what {A} warned about.','{A} would hate how you live.','{A} wrote this for you.'],
}
LOOPS={
 'quote':['Say that line again. Watch it twice.','Read that first line again.','That first line again. Watch it twice.'],
 'contrarian':['Now you see it. Watch the first line again.','Now watch the first line again.'],
 'warning':['That is what nobody warns you about. Watch it again.','Now you know. Watch it again.'],
 'myth':['Not what you thought, right? Watch it again.','Now watch the first line again.'],
 'sting':['Told you it hits hard. Play it again.','Play it again.'],
 'curiosity':['Now you know why. Watch it again.','Watch the first line again.'],
 'author':['Now hear the first line again.','Watch it again. Listen closely.'],
}
def short_title(title):
 t=re.split(r'[:;,(]| or ',title)[0].strip()
 t=re.sub(r'^(the|a|an)\s+','',t,flags=re.I)
 return t if 1<=len(t.split())<=3 else None
def surname(author):
 a=re.sub(r'\(.*?\)','',author or '').strip()
 parts=[p for p in re.split(r'[ ,]+',a) if p]
 if not parts:return None
 return ' '.join(parts) if parts[-1] in ('Tzu','Tse') else parts[-1]
def quote_candidate(sentences):
 best=None
 for s in sentences:
  t=re.sub(r'\s+',' ',s).strip()
  w=t.split()
  if 5<=len(w)<=9 and t[0].isupper() and t[-1] in '.?!':
   if len(w)<=7:return t
   best=best or t
 return best
def make(kind,title,author=None,rng=None):
 rng=rng or random.Random()
 t=short_title(title);a=surname(author)
 if kind=='author' and not a:kind='warning'
 if kind!='author' and not t:
  if a:kind='author'
  else:t='this classic'
 cands=[x.format(T=t,A=a) for x in LINES[kind]]
 short=[x for x in cands if 5<=len(x.split())<=7]
 ok=short or [x for x in cands if 5<=len(x.split())<=9]
 if ok:return kind,rng.choice(ok),rng.choice(LOOPS[kind])
 line=LINES['warning'][0].format(T=t or 'this classic');return 'warning',line,rng.choice(LOOPS['warning'])
def _weights():
 try:
  import json,pathlib
  w=json.loads((pathlib.Path(__file__).resolve().parent/'hook-weights.json').read_text())
  return w['weights'] if w.get('active') else None
 except Exception:return None
def pick(sentences,rng):
 kinds=[k for k in TYPES if k!='quote' or quote_candidate(sentences)]
 w=_weights()
 if w:  # learned from real views (hook_learn.py): better types more often, weak ones still tested
  return rng.choices(kinds,weights=[max(0.4,float(w.get(k,1.0))) for k in kinds])[0]
 if 'curiosity' in kinds and rng.random()<.5:kinds.remove('curiosity')  # measured weakest hook style
 bias={'quote':1.6,'author':1.5,'contrarian':1.0,'curiosity':0.6,'warning':0.3,'sting':0.5,'myth':0.5}   # measured: warning/bold-claim hooks average ~10 views, person/quote hooks 40-58
 return rng.choices(kinds,weights=[bias.get(k,1.0) for k in kinds])[0]
def apply(script,book,edition,evidence_url):
 rng=random.Random()
 old=script['hook'];sentences=[old,*script['points']]
 STORY=re.compile(r"\b(said|quit|begged|refused|drank|died|abandoned|lost|gave up|walked away|wrote|chose)\b",re.I)
 try:
  import footage_director;footage_director.HINT=old
 except Exception:pass
 if STORY.search(old or '') and re.match(r"^[A-Z][\w.' -]{2,25} ",old or '') and len((old or '').split())<=16 and rng.random()<0.9:
  # measured best hook style: a short story about a real person. Keep the script's own hook.
  script['hook_type']='story';script['hook_rules']='v3: kept person-story hook';return script
 kind=pick(sentences,rng)
 try:
  import footage_director;footage_director.HINT=old
 except Exception:pass
 if kind=='quote':
  q=quote_candidate(sentences);hook=q;loop=rng.choice(LOOPS['quote'])
  if q!=old:
   script['points']=[old]+[p for p in script['points'] if p!=q]
 else:
  ai=None
  if rng.random()<0.8:   # most hooks are now written for the passage (original, learned from viewers); templates stay as fallback and variety
   try:
    import ai_hook,os;ai=ai_hook.generate(book['title'],book.get('author'),sentences,'mindlore' if os.environ.get('BRAND')=='mindlore' else 'shelfmade')
   except Exception:ai=None
  if ai:kind,(hook,loop)='ai',ai
  else:
   kind,hook,loop=make(kind,book['title'],book.get('author'),rng)
   try:   # variety guard: do not repeat a hook that is too close to a recent one
    import variety,os;b='mindlore' if os.environ.get('BRAND')=='mindlore' else 'shelfmade'
    for _ in range(8):
     if not variety.too_close(hook,b):break
     kind,hook,loop=make(rng.choice(TYPES[1:]),book['title'],book.get('author'),rng)
   except Exception:pass
  try:
   import variety,os;variety.note('mindlore' if os.environ.get('BRAND')=='mindlore' else 'shelfmade',hook)
  except Exception:pass
  script['points']=[old,*script['points']]
  script['source_evidence']=[{'chapter':'Opening hook','kind':'editorial hook','excerpt':hook,'source_url':evidence_url,'verification':('Editorial hook written for this passage. Not a quotation.' if kind=='ai' else 'Editorial template line. Not a quotation.')+' The source passage follows as lesson 1.'},*script['source_evidence']]
 script['hook']=hook;script['cta']=loop
 words=hook.rstrip('.?!').split()
 script['thumbnail_headline']=' '.join(words[:5]).rstrip('.,').lower()
 script['public_title']=hook
 script['hook_type']=kind;script['hook_rules']='v2: <=9 word hook, answer last, loop ending'
 d=script.get('creative_director')
 if d:
  for c in d['candidates']:
   if c['id']==d['selected_id']:
    c['hook']=hook;c['headline']=script['thumbnail_headline'];c['public_title']=script['public_title']
    c['basis']='Hook rules v2 ('+kind+')'
  d['hook_rules']=kind
 return script

def apply_full(script):
 """Full video: spoken interrupt line first, original opening follows, loop line at the end.
 Safe: if the review check complains, the original script is returned unchanged."""
 import copy,creative_quality as cq
 original=copy.deepcopy(script)
 try:
  title=script.get('title','');author=script.get('author')
  try:
   import json,pathlib
   for b in json.loads((pathlib.Path(__file__).resolve().parent/'books.json').read_text()):
    if str(b.get('id'))==str(script.get('book_id')):title=b['title'];author=b.get('author',author);break
  except Exception:pass
  kind,hook,loop=make(random.choice([k for k in TYPES if k!='quote']),title,author)
  s=script
  s['sections'][0]['narration']=hook+' '+s['sections'][0]['narration']
  s['sections'][-1]['narration']=s['sections'][-1]['narration'].rstrip()+' '+loop
  old=s['hook'];s['hook']=hook
  s['thumbnail_headline']=' '.join(hook.rstrip('.').split()[:5]).lower()
  s['public_title']=hook
  s['hook_type']=kind
  if s.get('opening_payoff'):s['opening_payoff']['question']=old
  url=s.get('source_url','')
  s['source_evidence']=[{'section':0,'chapter':'Opening hook','kind':'editorial hook','excerpt':hook,'source_url':url,'verification':'Editorial template line. Not a quotation.'},*s['source_evidence']]
  for e in s['source_evidence'][1:]:
   if isinstance(e.get('section'),int):e['section']+=0
  d=s.get('creative_director')
  if d:
   for c in d['candidates']:
    if c['id']==d['selected_id']:c['hook']=hook;c['headline']=s['thumbnail_headline'];c['public_title']=s['public_title']
  errors=cq.script_review(s,s['source_evidence'],full=True)['errors']
  if errors:return original
  return s
 except Exception:
  return original
