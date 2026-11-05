"""Extract public captions from studio posting instructions."""
import re
from footage_credit_copy import strip_optional_pexels
SEPARATOR=re.compile(r'^\s*[=═─━_\-]{3,}\s*$')
MARKER=re.compile(r'^\s*(?:[-=═─━_]+\s*)?CAPTION(?:\s*\([^\n]*\))?\s*:?(?:\s*[-=═─━_]+)?\s*$',re.I|re.M)
def clean(value):
 if not isinstance(value,str):raise ValueError('Caption must be text.')
 value=strip_optional_pexels(value).replace('\r\n','\n').replace('\r','\n')
 marker=MARKER.search(value)
 if marker:value=value[marker.end():]
 lines=[]
 skip_title=False
 for line in value.splitlines():
  text=line.strip()
  if re.match(r'^Upload\s+final\.mp4\b',text,re.I):break
  if SEPARATOR.fullmatch(text):continue
  if re.match(r'^READY TO POST\b|^Platforms\s*:',text,re.I):continue
  if re.match(r'^(?:YOUTUBE\s*/\s*TIKTOK\s+)?TITLE\s*\(copy this\)\s*:',text,re.I):skip_title=True;continue
  if skip_title:
   if text:skip_title=False
   continue
  if re.match(r'^Source-supported draft\.\s*Review|^Review facts, wording and length before posting\.',text,re.I):continue
  # An empty author field is an incomplete label, not useful public copy.
  text=re.sub(r'\s+by\s*$','',text)
  lines.append(text)
 result='\n'.join(lines).strip()
 return re.sub(r'\n{3,}','\n\n',result)
