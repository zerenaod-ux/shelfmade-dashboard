"""Optional brand-library and MindLore-only publishing bridge.
Never dispatches MindLore requests to ShelfMade social publishers.
Imported lazily so an absent sibling workspace cannot stop ShelfMade startup.
"""
from pathlib import Path
import importlib,sys,os,stat
BASE=Path(__file__).resolve().parent.parent/'content-empire-studio'

def modules():
 if not (BASE/'workspace.html').is_file() or not (BASE/'studio/brand_context.py').is_file():raise ValueError('The read-only brand workspace is not installed.')
 if str(BASE) not in sys.path:sys.path.insert(0,str(BASE))
 return importlib.import_module('studio.profiles'),importlib.import_module('studio.workspace')

def entrance():
 path=BASE/'entrance.html'
 if not path.is_file():raise ValueError('Studio entrance is not installed.')
 return path.read_bytes()

def page():
 modules();return (BASE/'workspace.html').read_bytes()

def select(query):
 if len(query.get('brand',[]))!=1:raise ValueError('Choose one explicit brand workspace.')
 profiles,workspace=modules();return profiles.installed().select(query['brand'][0]),workspace

def snapshot(query):
 brand,workspace=select(query);return workspace.public_snapshot(brand)

def stream(handler,query):
 brand,workspace=select(query)
 if len(query.get('item',[]))!=1:raise ValueError('Choose one video.')
 path=workspace.video_path(brand,query['item'][0])
 # A mapped existing file only; refuse a last-component symlink at open time.
 descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(descriptor,'rb') as source:
  info=os.fstat(source.fileno())
  if not stat.S_ISREG(info.st_mode):raise ValueError('Video is unavailable.')
  size=info.st_size
  try:start,end,status=workspace.byte_range(handler.headers.get('Range'),size)
  except ValueError:return handler.send('',status=416,extra={'Content-Range':f'bytes */{size}'})
  handler.send_response(status)
  for name,value in [('Content-Type','video/mp4'),('Accept-Ranges','bytes'),('Content-Length',str(end-start+1)),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Cross-Origin-Resource-Policy','same-origin')]:handler.send_header(name,value)
  if status==206:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  handler.end_headers();source.seek(start);remaining=end-start+1
  try:
   while remaining:
    block=source.read(min(65536,remaining))
    if not block:break
    handler.wfile.write(block);remaining-=len(block)
  except (BrokenPipeError,ConnectionResetError):pass

def mindlore_connection_status():
 modules()
 return importlib.import_module('studio.buffer_connection').status()

def connect_mindlore_buffer(body):
 if not isinstance(body,dict) or body.get('brand')!='mindlore' or set(body)!={'brand','token'}:raise ValueError('Explicit MindLore connection request required.')
 modules()
 return importlib.import_module('studio.buffer_connection').connect(body['token'])

def mindlore_get(path,query):
 modules();flow=importlib.import_module('studio.mindlore_workflow')
 if path=='/api/mindlore/workflow':return flow.snapshot()
 if path=='/api/mindlore/item' and len(query.get('item',[]))==1:return flow.detail(query['item'][0])
 raise ValueError('Choose one MindLore item.')

def mindlore_post(path,body):
 if not isinstance(body,dict) or body.get('brand')!='mindlore':raise ValueError('Explicit MindLore request required.')
 modules();flow=importlib.import_module('studio.mindlore_workflow')
 actions={'prepare':flow.prepare,'approve':flow.approve,'publish':flow.enqueue,'retry':flow.retry,'refresh':lambda body:flow.refresh(force=True),'youtube/connect':lambda body:importlib.import_module('studio.mindlore_youtube').begin()}
 action=path.removeprefix('/api/mindlore/')
 if action not in actions:raise ValueError('Unknown MindLore operation.')
 return actions[action](body)

def start_mindlore_publisher():
 modules();importlib.import_module('studio.mindlore_workflow').start()


def cover(handler,query):
 brand,workspace=select(query)
 if len(query.get('item',[]))!=1:raise ValueError('Choose one cover')
 path=workspace.cover_path(brand,query['item'][0]);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  info=os.fstat(f.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_size>2*1024*1024:raise ValueError('Cover unavailable')
  data=f.read(2*1024*1024+1)
 return handler.send(data,'image/jpeg',extra={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


def start_mindlore_daily():
 modules();importlib.import_module('studio.mindlore_daily').start()
