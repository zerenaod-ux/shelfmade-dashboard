"""Image-led cover from matching local footage, never a generic words page."""
def card(script,load_font):
 import opening_design
 a=opening_design.asset(script)
 return opening_design.graphic(script,(1080,1920),opening_design.footage_frame(a['path'],(1080,1920))).convert('RGB')
