"""Keep optional Pexels attribution out of public captions, retain source evidence.
Pexels API attribution belongs in the studio's source-review interface. This only
removes a recognized Pexels block, never book sources or other license credits.
"""
import re
HEADER=re.compile(r'^\s*(?:Videos|Photos|Footage) provided by Pexels(?:\s*[—–-]\s*https?://(?:www\.)?pexels\.com/?)?\s*$',re.I)
CREDIT=re.compile(r'^(?:.+?\s+[—–-]\s+)?https://(?:www\.)?pexels\.com/(?:video|photo)/\S+\s*$',re.I)
def strip_optional_pexels(value):
 if not isinstance(value,str):raise ValueError('Public caption must be text')
 lines=[];inside=False
 for line in value.replace('\r\n','\n').replace('\r','\n').split('\n'):
  text=line.strip()
  if HEADER.fullmatch(text):inside=True;continue
  if inside and not text:continue
  if inside and CREDIT.fullmatch(text) and not re.match(r'^(?:music|license|book|research|source)\s*:',text,re.I):continue
  inside=False;lines.append(line)
 return re.sub(r'\n{3,}','\n\n','\n'.join(lines)).strip()
