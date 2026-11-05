"""Pure editorial visual coverage before allocating a daily full-video slot.
No network, narration, filesystem writes or claim that stock footage is available.
"""
import scene_direction

def chapters(script):
 result=[];cursor=0
 for index,section in enumerate(script.get('sections',[])):
  narration=section['narration'];duration=len(narration.split())/2.6
  if not duration:raise ValueError('An empty chapter cannot be admitted for full-video production.')
  chapter={'index':index,'title':section['title'],'narration':narration,'start':cursor,'duration':duration}
  if section['title']=='cta' and index:chapter['visual_context']=script['sections'][index-1]['narration']
  result.append(chapter);cursor+=duration
 if not result:raise ValueError('Full-video source has no chapters.')
 return result

def require(script):
 beats=scene_direction.plan(chapters(script))
 if not beats:raise ValueError('Full-video source has no filmable scene directions.')
 return {'state':'editorial_visual_coverage_passed','chapters':len(script['sections']),'estimated_shots':len(beats),
         'themes':sorted({b['visual']['theme'] for b in beats}),
         'stock_availability_verified':False,'source_accuracy_verified':False,'owner_review_required':True}
