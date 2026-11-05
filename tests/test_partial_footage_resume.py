import unittest,tempfile,json,time
from pathlib import Path
from unittest.mock import patch
import footage_director as f,full_checkpoint as checkpoint

class PartialFootageResume(unittest.TestCase):
 def test_saved_unused_clips_resume_without_new_downloads_or_searches(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);cache=root/'cache';cache.mkdir();source=root/'job';source.mkdir();target=root/'job-attempt-2';target.mkdir()
   script={'title':'Book','sections':[{'title':'Decision','narration':'Choose your response.'}]};brief={'theme':'choice','subject':'theme','queries':['writing journal'],'keywords':['choice'],'reason':'A decision metaphor','chapter':'Decision'}
   assets=[]
   for i in (1,2):
    path=cache/f'pexels-{i}.mp4';path.write_bytes(('video '+str(i)).encode());assets.append({'id':f'pexels-{i}','path':str(path),'sha256':checkpoint.file_hash(path),'themes':['choice'],'visual_subject':'theme','query':'writing journal','creator':'Fixture','source_url':'https://www.pexels.com/video/writing-journal-'+str(i)+'/','duration':20})
   with patch.object(f,'DB',root/'footage.sqlite'),patch.object(f,'CACHE',cache),patch.object(f.media_runtime,'require_ready'),patch.object(f,'brief',return_value=brief),patch.object(f,'historical_hashes',return_value=set()),patch('scene_direction.plan',return_value=[{'visual':brief}]*2),patch('scene_direction.receipt',return_value={}),patch.object(f,'search') as search,patch.object(f,'download') as download:
    checkpoint.write(source/'acquisition-progress.json',{'identity':f.progress_identity(script),'assets':assets})
    with f.connect() as c:
     for a in assets:c.execute('insert into reserved values (?,?,?)',(a['id'],str(source.resolve()),time.time()+60))
    f.restore_progress(source,target,script);result=f.acquire(script,target)
    self.assertEqual(len(result),2);search.assert_not_called();download.assert_not_called();self.assertTrue((source/'acquisition-progress.json').exists())
    with f.connect() as c:self.assertEqual(c.execute('select count(*) from used').fetchone()[0],0)
 def test_changed_assets_and_script_are_not_reused(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);cache=root/'cache';cache.mkdir();source=root/'job';source.mkdir();path=cache/'pexels-1.mp4';path.write_bytes(b'original');script={'title':'Original'}
   with patch.object(f,'CACHE',cache):
    checkpoint.write(source/'acquisition-progress.json',{'identity':f.progress_identity(script),'assets':[{'path':str(path),'sha256':checkpoint.file_hash(path),'id':'pexels-1'}]})
    self.assertEqual(f.saved_assets(source,{'title':'Different'}),[]);path.write_bytes(b'changed');self.assertEqual(f.saved_assets(source,script),[])
if __name__=='__main__':unittest.main()
