"""Hashtag sets: the best 5 per video (Instagram limits posts to 5; YouTube and TikTok do best with 3-5 relevant tags).
Order matters: YouTube shows the first three above the title. Broad reach first, topic-specific next, brand last."""
import re
MINDLORE_TOPICS=[
 (r'\b(emotion\w*|face|faces|expression\w*|feeling\w*|anger|fear)\b',['#emotions','#emotionalintelligence']),
 (r'\b(habit\w*|routine|discipline|custom)\b',['#habits','#selfdiscipline']),
 (r'\b(dream\w*|sleep\w*|unconscious|subconscious)\b',['#dreams','#subconscious']),
 (r'\b(crowd\w*|revolution\w*|society|social|speaker|audience|collective)\b',['#socialpsychology','#humanbehavior']),
 (r'\b(attention|concentrat\w*|focus\w*|intention|will)\b',['#focus','#mindfulness']),
 (r'\b(laugh\w*|humou?r|comic|funny)\b',['#humor','#humanbehavior']),
 (r'\b(suggestion|hypnos\w*|influence|persuad\w*)\b',['#persuasion','#humanbehavior']),
 (r'\b(efficien\w*|work|worker\w*|labor|industr\w*|fatigue)\b',['#productivity','#workpsychology']),
 (r'\b(belief|reason\w*|think\w*|thought\w*|logic|mind)\b',['#criticalthinking','#mindset']),
]
SHELF_TOPICS=[
 (r'\b(psycholog\w*|habit\w*|mind|emotion\w*|behavio\w*)\b','#psychology'),
 (r'\b(philosoph\w*|virtue|ethic\w*|stoic\w*|wisdom|meaning)\b','#philosophy'),
 (r'\b(money|wealth|business|success|career|work|invest\w*|rich|poor)\b','#selfimprovement'),
 (r'\b(war|battle|empire|king|history|nation)\b','#history'),
 (r'\b(courage|fear|hope|resilien\w*|struggle|survive\w*)\b','#motivation'),
]
def _pick(patterns,text,n):
 out=[]
 for pat,tags in patterns:
  if re.search(pat,text,re.I):
   for t in (tags if isinstance(tags,list) else [tags]):
    if t not in out:out.append(t)
 return out[:n]
def mindlore(text,fmt='short'):
 topical=_pick(MINDLORE_TOPICS,text or '',2)
 for fill in ('#mindset','#selfimprovement'):
  if len(topical)<2 and fill not in topical:topical.append(fill)
 tags=['#psychology',topical[0],'#Shorts' if fmt=='short' else '#psychologyfacts',topical[1],'#MindLore']
 return ' '.join(dict.fromkeys(tags))
def shelfmade(text,fmt='short'):
 topic=(_pick(SHELF_TOPICS,text or '',1) or ['#classicliterature'])[0]
 tags=['#BookTok','#booksummary',topic,'#Shorts' if fmt=='short' else '#books','#ShelfMade']
 return ' '.join(dict.fromkeys(tags))
