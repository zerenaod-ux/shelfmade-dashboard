"""Schedule only the owner's named existing private full videos; never upload media."""
import datetime,json,os,re
from pathlib import Path
import yt_publish as Y
from full_release_slots import next_release,TZ
TARGETS=['EPGy8t4XRkI','RwXYKd7gBCE','4qWHmBcx-I4','D2VOAPsZqKw','QNTiEqKvMFM','pnp7OZO0fJA','Ylxy6FpM934','PAXSM0lkgEk','P8P40XX9vbk']
def key(x):return re.sub(r'\W+',' ',x.casefold()).strip()
def seconds(x):
 m=re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',x)
 if not m:return 0
 h,mi,s=[int(a or 0) for a in m.groups()];return h*3600+mi*60+s

def read(access,ids):
 h={'Authorization':'Bearer '+access};rows={}
 for i in range(0,len(ids),50):
  with Y.http('https://www.googleapis.com/youtube/v3/videos?part=status,snippet,contentDetails&id='+','.join(ids[i:i+50]),headers=h) as r:
   rows.update({v['id']:v for v in json.load(r).get('items',[])})
 return rows

def inventory(access):
 h={'Authorization':'Bearer '+access}
 with Y.http('https://www.googleapis.com/youtube/v3/channels?part=id&mine=true',headers=h) as r:
  if [x['id'] for x in json.load(r).get('items',[])]!=[Y.CHANNEL]:raise ValueError('Unexpected YouTube channel; refusing changes')
 ids=list(TARGETS);page=''
 for _ in range(8):
  url='https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId=UU'+Y.CHANNEL[2:]+('&pageToken='+page if page else '')
  with Y.http(url,headers=h) as r:data=json.load(r)
  ids.extend(x['contentDetails']['videoId'] for x in data.get('items',[]));page=data.get('nextPageToken','')
  if not page:break
 return read(access,list(dict.fromkeys(ids)))

def plan(rows,now):
 full=[v for v in rows.values() if seconds(v['contentDetails']['duration'])>=120]
 public={key(v['snippet']['title']) for v in full if v['status']['privacyStatus']=='public'}
 taken={datetime.datetime.fromisoformat(v['status']['publishAt'].replace('Z','+00:00')).astimezone(TZ).date() for v in full if v['status'].get('publishAt')}
 result=[]
 for vid in TARGETS:
  v=rows.get(vid);row={'id':vid}
  if not v:row.update(state='held',reason='Video unavailable to the channel account');result.append(row);continue
  row.update(title=v['snippet']['title'],seconds=seconds(v['contentDetails']['duration']))
  if row['seconds']<120 or v['snippet']['channelId']!=Y.CHANNEL:raise ValueError('Target is not a full video on the expected channel')
  st=v['status'];title=key(row['title'])
  if st['privacyStatus']!='private' or st.get('uploadStatus')!='processed':row.update(state='held',reason='Not an existing processed private upload')
  elif st.get('publishAt'):row.update(state='already_scheduled',publishAt=st['publishAt'])
  else:
   if title in public:row['note']='Owner explicitly approved this existing private upload; same-title public video exists'
   day,stamp=next_release(taken,now=now);taken.add(day);row.update(state='planned',publishAt=stamp,local=stamp_to_local(stamp));public.add(title)
  result.append(row)
 return result

def stamp_to_local(stamp):return datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(TZ).isoformat()
def main():
 access=Y.token();rows=inventory(access);result=plan(rows,datetime.datetime.now(TZ));apply=os.environ.get('APPLY_SCHEDULE')=='1'
 for row in result:
  if row['state']!='planned' or not apply:continue
  current=read(access,[row['id']]).get(row['id'])
  if not current or current['status']['privacyStatus']!='private' or current['status'].get('publishAt'):raise ValueError('Video state changed after preflight; refusing overwrite')
  st=current['status'];body={'id':row['id'],'status':{'privacyStatus':'private','publishAt':row['publishAt'],'selfDeclaredMadeForKids':st.get('selfDeclaredMadeForKids',False)}}
  with Y.http('https://www.googleapis.com/youtube/v3/videos?part=status',json.dumps(body).encode(),{'Authorization':'Bearer '+access,'Content-Type':'application/json'},'PUT') as r:json.load(r)
  actual=read(access,[row['id']])[row['id']]['status']
  if actual.get('publishAt','').replace('.000Z','Z')!=row['publishAt'].replace('.000Z','Z') or actual['privacyStatus']!='private':raise ValueError('YouTube schedule read-back failed')
  row['state']='scheduled_verified'
  Path('mindlore-schedule-report.json').write_text(json.dumps({'applied':apply,'videos':result},indent=2))
 report={'applied':apply,'videos':result};Path('mindlore-schedule-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 if apply:Path('publish/mindlore-private-schedule.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
