"""Owner-only, read-only Gumroad summary. Never publishes or returns buyer data."""
import json, math, os, re, threading, time, urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parent
PRIVATE=BASE.parent.parent/'work/gumroad-private'
TOKEN=PRIVATE/'token.json'
CACHE=PRIVATE/'sales-summary.json'
URL='https://mnaod.gumroad.com/l/aboaf'
TTL=300
_lock=threading.Lock()
_last_attempt=0
_last_error=None

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def read_provider():
 if TOKEN.is_symlink() or not TOKEN.is_file() or TOKEN.stat().st_mode & 0o077:raise ValueError('Connection unavailable')
 saved=json.loads(TOKEN.read_text())
 if set(re.split(r'[ ,]+',saved.get('scope','')))!={'edit_products','view_sales'}:raise ValueError('Unexpected permissions')
 token=saved.get('access_token')
 if not isinstance(token,str) or not token or '\n' in token or '\r' in token:raise ValueError('Invalid connection')
 request=urllib.request.Request('https://api.gumroad.com/v2/products/aboaf',headers={'Authorization':'Bearer '+token,'User-Agent':'ShelfMade-Sales/1'})
 with urllib.request.build_opener(NoRedirect()).open(request,timeout=8) as response:raw=response.read(2000001)
 if len(raw)>2000000:raise ValueError('Response too large')
 data=json.loads(raw)
 if not data.get('success'):raise ValueError('Provider unavailable')
 p=data['product']
 if p.get('short_url','').rstrip('/')!=URL:raise ValueError('Product mismatch')
 def count(key):
  v=p.get(key)
  return int(v) if type(v) in (int,float) and math.isfinite(v) and v>=0 and int(v)==v else None
 return {'name':str(p.get('name','Timeless Wisdom'))[:180],'published':p.get('published') is True,'price_cents':count('price'),'currency':str(p.get('currency','')).lower()[:8],'orders':count('sales_count'),'sales_amount_cents':count('sales_usd_cents')}

def snapshot(refresh=False):
 global _last_attempt,_last_error
 with _lock:
  saved={}
  try:
   if not CACHE.is_symlink():saved=json.loads(CACHE.read_text())
   if not isinstance(saved,dict):saved={}
  except (OSError,ValueError):pass
  now=time.time()
  # Both page loads and refresh clicks share a five-minute provider budget.
  if now-max(_last_attempt,saved.get('checked_at',0))>=TTL:
   _last_attempt=now
   try:
    data=read_provider();saved={**data,'checked_at':now}
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    if CACHE.is_symlink():raise ValueError('Unsafe cache')
    temp=CACHE.with_suffix('.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(saved,f)
    os.replace(temp,CACHE);_last_error=None
   except Exception:_last_error='Gumroad could not be checked. Saved totals remain visible; try again in five minutes or check Gumroad settings.'
  keys=('name','published','price_cents','currency','orders','sales_amount_cents','checked_at')
  return {**{k:saved.get(k) for k in keys},'available':bool(saved),'connected':bool(saved) and not _last_error,'stale':not saved or now-saved.get('checked_at',0)>=TTL,'message':_last_error,'product_url':URL,'provider_url':'https://gumroad.com/dashboard','next_check_at':max(_last_attempt,saved.get('checked_at',0))+TTL,'note':'Gumroad aggregate totals may include test orders. Sales amount is provider-reported USD, not net profit. Fees, refunds, taxes and payouts are not reconciled here.'}
