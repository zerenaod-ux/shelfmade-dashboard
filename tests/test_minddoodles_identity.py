import unittest,tempfile,json,hashlib,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import minddoodles_identity as m
import minddoodles_bridge as bridge
class ApprovedIdentity(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.manifest=self.root/'contract.json';self.scene=self.root/'scene';self.scene.mkdir()
  self.rows=[]
  for role in sorted(m.ROLES):
   file=self.root/(role+'.bin');file.write_bytes(role.encode());self.rows.append({'role':role,'path_relative_to_outputs':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
  self.pin=patch.object(m,'APPROVED_SHA256',{x['role']:x['sha256'] for x in self.rows});self.pin.start();self.addCleanup(self.pin.stop)
  self.data={'schema':1,'brand':'minddoodles','style_id':m.STYLE,'substitute_cast_allowed':False,'still_slideshow_allowed':False,'owner_review_before_publish':True,'assets':self.rows};self.save()
  self.source=b'motion_reference';(self.scene/'source.mp4').write_bytes(self.source)
  self.meta={'brand':'minddoodles','id':'hands-free-v1','source_kind':'edited_approved_reference','counts_as_fresh_daily_output':False,'files':{'source.mp4':hashlib.sha256(self.source).hexdigest()}};self.save_scene()
 def save(self):self.manifest.write_text(json.dumps(self.data))
 def save_scene(self):(self.scene/'scene.json').write_text(json.dumps(self.meta))
 def validate(self):return m.validate_speech_source(self.manifest,self.root,self.scene)
 def test_exact_references_pass_but_not_fresh_daily_identity(self):
  r=self.validate();self.assertFalse(r['new_animation_identity_verified']);self.assertFalse(r['counts_as_fresh_daily_output'])
 def test_changed_bytes_rejected_even_same_size(self):
  row=self.rows[0];p=self.root/row['path_relative_to_outputs'];p.write_bytes(b'X'*p.stat().st_size)
  with self.assertRaises(ValueError):self.validate()
 def test_rewritten_manifest_cannot_redefine_approved_face(self):
  row=self.rows[0];p=self.root/row['path_relative_to_outputs'];p.write_bytes(b'substitute');row.update(bytes=10,sha256=hashlib.sha256(b'substitute').hexdigest());self.save()
  with self.assertRaises(ValueError):self.validate()
 def test_substitute_cast_flag_rejected(self):
  self.data['substitute_cast_allowed']=True;self.save()
  with self.assertRaises(ValueError):self.validate()
 def test_wrong_brand_rejected(self):
  self.data['brand']='mindlore';self.save()
  with self.assertRaises(ValueError):self.validate()
 def test_linked_reference_rejected(self):
  p=self.root/self.rows[0]['path_relative_to_outputs'];other=self.root/'other';p.rename(other);p.symlink_to(other)
  with self.assertRaises(ValueError):self.validate()
 def test_traversal_rejected(self):
  self.rows[0]['path_relative_to_outputs']='../outside';self.save()
  with self.assertRaises(ValueError):self.validate()
 def test_native_scene_cannot_claim_other_motion_as_reference(self):
  (self.scene/'source.mp4').write_bytes(b'other character');self.meta['files']['source.mp4']=hashlib.sha256(b'other character').hexdigest();self.save_scene()
  with self.assertRaises(ValueError):self.validate()
 def test_reference_cannot_count_as_fresh_daily_footage(self):
  self.meta['counts_as_fresh_daily_output']=True;self.save_scene()
  with self.assertRaises(ValueError):self.validate()
 def test_legacy_generator_never_reaches_provider(self):
  with patch.object(bridge.urllib.request,'urlopen') as network:
   for renderer in ['puppet','3d']:
    with self.assertRaises(ValueError):bridge.action({'brand':'minddoodles','action':'generate','renderer':renderer})
   network.assert_not_called()
 def test_failed_integrity_blocks_speech_dispatch_before_provider(self):
  with patch.object(m,'validate_speech_source',side_effect=ValueError('reference changed')),patch.object(bridge.urllib.request,'urlopen') as network:
   with self.assertRaises(ValueError):bridge.action({'brand':'minddoodles','action':'build-speech'})
   network.assert_not_called()
if __name__=='__main__':unittest.main()
