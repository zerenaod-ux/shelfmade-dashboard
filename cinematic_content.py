"""Editorial drafts from existing local summaries, with explicit modern applications.
No paid AI and no invented source quotations. Human source review is mandatory.
"""
import json,re,os
ML=os.environ.get('BRAND')=='mindlore'
WLO,WHI=(1100,1500) if ML else (850,1300)
from pathlib import Path
BASE=Path(__file__).resolve().parent
SUMMARY=Path.home()/'Documents'/'ContentEmpire-Studio'/'PRODUCTS'/'ebook_content.json'
if not SUMMARY.exists():SUMMARY=Path(__file__).resolve().parent/'summary-library'/'ebook_content.json'
PROFILES={
 '45109':('One insult can steal your whole day. Why give it that power?','WHO CONTROLS YOUR DAY?','Who controls your day? | The Enchiridion'),
 '2680':('Why can one small insult ruin your whole day?','DON’T GIVE AWAY YOUR CALM','A calmer response | Meditations'),
 '4507':('Which thought are you turning into a habit?','THOUGHTS BECOME HABITS','The habits behind your thoughts | As a Man Thinketh'),
 '132':('What if the smartest victory begins before the fight?','BEFORE THE FIGHT','Think before you fight | The Art of War'),
 '1497':('What if the picture you trust is only part of reality?','QUESTION WHAT YOU SEE','Question what you see | The Republic'),
 '935':('What happens when effort becomes a habit instead of a mood?','EFFORT OVER MOOD','Effort over mood | Self-Help'),
 '216':('When does trying harder make a problem harder?','HARDER ISN’T ALWAYS BETTER','Stop forcing it | Tao Te Ching'),
}
EXERCISES=[
 ('control',('control','anger','emotion','response'), 'Consider an ordinary disagreement. Before answering, distinguish the event from the interpretation you have added to it. What actually happened, and what are you assuming? Write those as separate sentences. Then choose a response you could defend after the emotion has passed. This is our modern exercise, not a quotation or a promise that every situation is within your control. The point is to make a small space for judgment. Notice what changes when that space is available, and what still needs a direct conversation.'),
 ('practice',('habit','practice','discipline','effort','character'), 'Choose one small action that would make this idea visible in your routine. Make it concrete enough to recognize: a page read carefully, a task begun on time, or a promise kept. Decide when you will try it, then observe what makes it easier or harder. This exercise is our application, not a method attributed to the author. One attempt cannot prove a whole philosophy. It can, however, reveal the distance between admiring an idea and arranging your day so that the idea has a chance to matter.'),
 ('perspective',('knowledge','reason','truth','learn','education'), 'Think of a belief you hold with confidence. Ask what experience or evidence led you there, and what you would need to learn before changing your mind. You do not have to abandon the belief to examine it. The exercise is to distinguish understanding a claim from merely recognizing it. Explain the idea in your own words, then name the question that remains. This is our present-day application. A useful question is often more precise than a dramatic answer, and it gives your next conversation or reading a direction.'),
 ('time',('time','death','life','mortality','day'), 'Look at a small part of tomorrow rather than trying to redesign your entire life. Which commitment deserves your attention, and which activity is simply arriving by habit? Protect a short period for the first one. At the end, ask whether the choice matched what you say matters. This is our reflection exercise, not a rule quoted from the book. Time is shared with responsibilities and other people, so the aim is not perfect personal control. It is a clearer decision about the part of the day you can reasonably shape.'),
 ('people',('people','kindness','duty','society','friend','virtue'), 'Imagine a conversation in which you want both honesty and a continuing relationship. What would it mean to take the other person seriously without pretending that you agree? Try stating their concern fairly before explaining your own. This is our modern example, not a historical scene from the book. It may not resolve the disagreement. Its value is that it makes the difference between understanding and winning easier to notice. Afterwards, ask whether your conduct expressed the principle you intended to follow, rather than simply the emotion you felt.'),
 ('attention',('nature','simple','attention','quiet','solitude'), 'Choose a familiar place and ask what you have stopped noticing there. You might watch the light, listen to a sound, or observe a small change in a routine. Do not turn the exercise into another competition to perform well. Give one ordinary thing your undivided attention for a little while. This is our application of the theme, not an exercise claimed by the author. The place does not have to become extraordinary. The experiment is whether your relationship with it changes when recognition gives way to closer observation.'),
 ('strategy',('war','victory','enemy','strategy','planning'), 'Consider a difficult task that does not involve a conflict with another person. Before pushing harder, identify the goal, the constraint, and one assumption you have not tested. Ask whether preparation could remove an avoidable obstacle. This is a modern analogy, not a claim that ordinary relationships should be treated as battles. Strategy can become unhelpful when it encourages manipulation or turns every situation into a contest. Use the comparison carefully: understand the conditions, make a proportionate plan, and revise it when the conditions change.'),
 ('reflection',(), 'Bring the idea into a situation you actually recognize. Describe that situation plainly, without trying to make it fit the book perfectly. What does this perspective help you notice? What does it leave out? Write a possible next step and a reason you might choose differently. These are our discussion questions, not additional claims from the author. An interpretation becomes more useful when it can survive a specific example. Keep the distinction between learning from a text and asking a text to supply every answer to a complicated life.'),
]
FALLBACKS=[
 'Try explaining this idea to a thoughtful friend who has not read the book. Begin with a concrete situation rather than an impressive phrase. What would the idea help your friend notice, and what objection might they raise? You do not need to defeat the objection. Use it to find the part of your explanation that needs more care. An idea becomes clearer when it can be questioned. Notice whether you can describe its limits as honestly as its appeal, and return to the text where your understanding remains uncertain.',
 'Imagine two situations that look similar at first, but differ in one important detail. Would you apply this idea in both? If your answer changes, explain what caused the change. The purpose is not to force every example into the same conclusion. It is to discover which conditions make the principle useful. This kind of comparison can reveal a qualification that a memorable sentence hides. Keep the example modest, distinguish what you know from what you assume, and resist turning a useful insight into an answer for everything.',
 'Recall a small experience that this discussion brings to mind. Describe what happened before deciding what it means. Then compare your first interpretation with another plausible interpretation. What does the idea from the book make more visible? What part of the experience still resists it? You are not trying to prove a philosophy with a personal anecdote. You are practicing a more careful exchange between reading and experience. If the comparison does not fit, that is useful information too. A text can challenge you without describing your situation perfectly.',
 'Compare this point with one of the earlier ideas in the discussion. Do they reinforce each other, or is there a tension between them? Give that tension a specific example. A serious book is often more interesting when its claims are considered together rather than collected as separate slogans. You may discover that one idea needs the qualification supplied by another. Keep the question open long enough to describe it clearly. The aim is a more connected understanding, including the places where your reading is still incomplete.',
 'Choose one question from this idea to carry into the next week. Make it small enough to notice in ordinary life, without turning the week into a test you must pass. At the end, write what you observed and what surprised you. Separate the observation from the conclusion you would like to draw. This gives a reflection something more concrete to work with. You can keep an idea provisionally, revise your interpretation, or decide to read further. Thoughtful attention is more useful than a dramatic promise of instant transformation.'
]
def hook_profile(book,title,ideas):
 if book in PROFILES:return PROFILES[book]
 # Curated rhetorical choices, selected by the actual first lesson, not cut-off titles.
 options=[
  (('control','power','response','anger'),'Why let one moment decide your whole day?','WHO CONTROLS YOUR DAY?'),
  (('truth','knowledge','reason','belief','education'),'How sure are you that you are right?','WHAT IF YOU’RE WRONG?'),
  (('time','mortality','death','hours'),'What keeps taking the time you meant to keep?','WHERE DID TODAY GO?'),
  (('habit','character','thought','effort','practice'),'What are your everyday habits quietly building?','SMALL CHOICES ADD UP'),
  (('nature','simple','simplicity','attention'),'What have you stopped noticing in your own life?','LOOK AGAIN'),
  (('war','victory','strategy','planning'),'Could better preparation change the fight before it starts?','BEFORE THE FIRST MOVE'),
  (('wealth','opportunity','diamond'),'What opportunity are you overlooking because it looks ordinary?','HIDDEN IN PLAIN SIGHT'),
  (('virtue','duty','kindness','people','society'),'What do your choices reveal when nobody is watching?','WHO ARE YOU BECOMING?'),
  (('freedom','liberty','government','rights'),'Who gets to decide how you live?','WHO DECIDES YOUR LIFE?'),
  (('suffering','pain','desire','happiness'),'Why does getting what you want not always feel enough?','WHY ISN’T IT ENOUGH?')]
 first=ideas[0]['title'].lower();context=' '.join(i['title'] for i in ideas).lower()
 def relevance(o):return sum(5*bool(re.search(r'\b'+re.escape(k)+r'\b',first))+bool(re.search(r'\b'+re.escape(k)+r'\b',context)) for k in o[0])
 choice=max(options,key=relevance)
 if not relevance(choice):return ('What would change if you tested one idea instead of just agreeing with it?','PUT ONE IDEA TO WORK','Put one idea to work | '+title)
 return choice[1],choice[2],choice[1].rstrip('?')+' | '+title

def _build(book):
 curated=BASE/('cinematic-scripts-mindlore' if ML else 'cinematic-scripts')/(f'{book}-'+os.environ['ML_VARIANT']+'.json' if ML and os.environ.get('ML_VARIANT') else f'{book}.json')
 if curated.exists():return json.loads(curated.read_text())
 try:source=json.loads(SUMMARY.read_text()).get(book)
 except (OSError,ValueError):raise ValueError('Restore the local summary library first.')
 if not source:raise ValueError('No local summary for this book. Add an editorial script before generation.')
 title=source.get('_title',book);author=source.get('_author','');ideas=[i for i in source.get('ideas',[]) if i.get('title') and i.get('explanation')][:5]
 if len(ideas)<4:raise ValueError('Not enough distinct source material. Add a reviewed script instead of padding a short summary.')
 hook,headline,public_title=hook_profile(book,title,ideas)
 sections=[{'title':'The question','narration':hook+' '+opening_scene(ideas[0])+' Begin with '+ideas[0]['title']+'. '+source.get('overview','')+' We will examine that first idea, then test the remaining lessons against ordinary life. The scenes and exercises are our modern interpretations, not quotations or historical events. Keep the opening question in mind: the first lesson gives us something specific to test, and the ending asks what you would actually do with it.'}]
 used=set()
 for i,idea in enumerate(ideas):
  text=idea['title']+' '+idea['explanation'];words=set(re.findall('[a-z]+',text.lower()));available=[e for e in EXERCISES if e[0] not in used]
  best=max(available,key=lambda e:sum(t in words for t in e[1])) if available else EXERCISES[-1]
  # No keyword match: use a genuinely open reflection, not an unrelated exercise.
  if best[1] and not any(t in words for t in best[1]):best=EXERCISES[-1]
  exercise=FALLBACKS[i%len(FALLBACKS)] if best[0]=='reflection' else best[2]
  used.add(best[0]);sections.append({'title':idea['title'],'narration':idea['explanation']+' '+exercise})
 sections.append({'title':'Carry one idea forward','narration':'Before the next video begins, choose one idea you want to examine more carefully. Do not try to adopt an entire worldview in a single evening. Read the relevant passage, consider the context, and compare it with a specific experience of your own. A classic book can sharpen a question without settling every argument. What would you keep from this discussion, and what would you question? Share one example in the comments. Subscribe to ShelfMade for thoughtful lessons from classic books. Then give yourself a moment to decide what you want to do with the attention you have just spent.'})
 script={'book_id':book,'title':title,'author':author,'public_title':public_title[:100],'hook':hook,'thumbnail_headline':headline if len(headline.split())<=6 else 'SEE IT DIFFERENTLY','sections':sections,'source_kind':'Existing local summary plus explicitly identified modern exercises; owner must verify source accuracy','source_url':'https://www.gutenberg.org/ebooks/'+book}
 count=sum(len(s['narration'].split()) for s in sections)
 if not WLO<=count<=WHI:raise ValueError(f'Script has {count} words. Add an editorial 5–8 minute script; no automatic filler or speed change was used.')
 return script


OPENING_SCENES={
 'control':'A message appears on your screen. Before you answer, notice the story you have already added to it. There is the event, and then there is your judgment. Those are not always the same thing.',
 'learning':'You hear a confident explanation and almost repeat it as a fact. Then someone asks how you know. That pause between recognition and understanding is where this question begins.',
 'nature':'Take the familiar path again, but slow down at the part you normally hurry past. Notice the light and the small movement of water. The place has not changed; the attention you bring to it has.',
 'time':'You open your phone to check one thing. When you look up, the quiet part of your evening has gone. The question is not simply where the minutes went, but what you meant to give them to.',
 'practice':'The task is small enough to begin, yet you wait to feel ready. Tomorrow brings the same choice. Look at the gap between the intention you admire and the action you repeat.',
 'community':'A conversation reaches the point where you could listen, or prepare your next argument. Both people want to be understood. What you do in the next few seconds gives the principle a practical test.',
 'choice':'You pause where two paths divide. Neither comes with a complete explanation of what follows. A choice can look small from the outside and still reveal what you are willing to give up.',
 'strategy':'Before the first move, look at the conditions. The obvious route may be the one that costs the most. Preparation starts by asking what the goal requires, rather than rushing to prove how hard you can push.',
 'wealth':'You pass a worn object and almost discard it. Someone else stops to examine what could be repaired. The scene is our analogy: value and opportunity are not always obvious at first glance.',
 'suffering':'You reach the thing you wanted, but the relief does not last as long as you expected. Sit with that ordinary experience for a moment before deciding what it proves. The book gives us a question, not an instant cure.'}
def opening_scene(idea):
 import footage_director
 try:theme=footage_director.brief(idea['explanation'],idea['title'])['theme']
 except ValueError:theme=None
 return OPENING_SCENES.get(theme,'You finish a passage and pause before turning the page. Which part would still matter in a real situation? That is the small test we will bring to the first lesson, rather than collecting another impressive phrase.')
def build(book):
 import creative_quality as cq
 script=_build(book)
 count=sum(len(section['narration'].split()) for section in script.get('sections',[]))
 if not WLO<=count<=WHI:raise ValueError(f'Script has {count} words. Add an editorial 5–8 minute script; no automatic filler or speed change was used.')
 # The recorded promise must be the words actually spoken, including curated drafts.
 script['hook']=re.split(r'(?<=[.!?])\s+',script['sections'][0]['narration'].strip())[0]
 script.setdefault('public_title',script['title'][:100]);script['creative_policy']=cq.VERSION
 try:source=json.loads(SUMMARY.read_text()).get(book,{})
 except (OSError,ValueError):source={}
 evidence=[];curated=(BASE/('cinematic-scripts-mindlore' if ML else 'cinematic-scripts')/(f'{book}-'+os.environ['ML_VARIANT']+'.json' if ML and os.environ.get('ML_VARIANT') else f'{book}.json')).exists()
 if curated:
  # Curated commentary checkpoints are not presented as independently checked source passages.
  for i,section in enumerate(script['sections']):
   evidence.append({'section':i,'chapter':section['title'],'kind':'curated editorial checkpoint','excerpt':section['narration'][:500],'source_url':script['source_url'],'verification':'Compare this interpretation with the original passage during owner review.'})
 else:
  evidence.append({'section':0,'chapter':'Book context','kind':'local summary','excerpt':source.get('overview',''),'source_url':script['source_url'],'verification':'Local editorial input; original source must be checked by owner.'})
  for i,idea in enumerate(source.get('ideas',[])[:5],1):
   evidence.append({'section':i,'chapter':idea['title'],'kind':'local summary','excerpt':idea['explanation'],'source_url':script['source_url'],'verification':'Summary, not a verified quotation. Exercises in the narration are our applications.'})
 if curated and 'source_passages' in script:
  import retained_editorial
  evidence=retained_editorial.evidence(script,book)
 script['source_evidence']=evidence
 ranked=sorted(range(1,max(2,len(script['sections'])-1)),key=lambda i:len(cq.tokens(script['hook'])&cq.tokens(script['sections'][i]['narration'])),reverse=True)
 payoff=next((i for i in ranked if cq.related(script['hook'],script['sections'][i]['narration'])),1)
 script['opening_payoff']={'section':payoff,'chapter':script['sections'][payoff]['title'],'question':script['hook'],'review':'Does this lesson actually answer or examine the opening question?'}
 cq.require(cq.script_review(script,evidence,full=True))
 import creative_director
 if not ML:script=creative_director.full(script)
 import hook_rules
 if os.environ.get('SHELFMADE_HOOK_RULES','1')=='1' and not ML:script=hook_rules.apply_full(script)
 return script

def available_books():
 books=[]
 for book in json.loads((BASE/'books.json').read_text()):
  try:
   import visual_admission
   visual_admission.require(build(book['id']))
  except ValueError:continue
  books.append(book)
 return books
