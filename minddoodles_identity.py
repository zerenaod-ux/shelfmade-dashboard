"""Approved Leo/Mia reference integrity. Hashes do not establish new-scene visual identity."""
import hashlib,json
from pathlib import Path
OUTPUTS=Path(__file__).resolve().parent.parent
CONTRACT=OUTPUTS/'minddoodles-production/Approved-assets.json'
SCENE=Path.home()/'Documents'/'minddoodles-studio'/'data'/'production'/'scenes'/'hands-free-v1'
STYLE='leo-mia-approved-reference-v1'
ROLES={'visual_reference','motion_reference','speaking_reference'}
APPROVED_SHA256={'visual_reference': '75c45a93925d765cea59435466454f3f60eb31760ae416ecf0845e14a8fe3ed5', 'motion_reference': '87f5ba53f57bfe92c1df7b82adc9fb2842ddb3dfaf51dfbd3a8e09c8bf656828', 'speaking_reference': '7ef90f815f1a65d2c9e38c6e70913e97f53a1a3ae90bb450448261ba84f1c139'}
def digest(path):
 result=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):result.update(chunk)
 return result.hexdigest()
def validate_contract(contract=None,outputs=None):
 contract=Path(contract or CONTRACT);outputs=Path(outputs or OUTPUTS).resolve()
 if contract.is_symlink() or not contract.is_file() or contract.stat().st_size>12000:raise ValueError('Approved Leo/Mia reference contract unavailable')
 value=json.loads(contract.read_text())
 if (value.get('schema')!=1 or value.get('brand')!='minddoodles' or value.get('style_id')!=STYLE
  or value.get('substitute_cast_allowed') is not False or value.get('still_slideshow_allowed') is not False
  or value.get('owner_review_before_publish') is not True):raise ValueError('Use the approved Leo/Mia character contract')
 rows=value.get('assets',[])
 if not isinstance(rows,list) or len(rows)!=3 or {x.get('role') for x in rows}!=ROLES:raise ValueError('The three approved references are required')
 for row in rows:
  if row.get('sha256')!=APPROVED_SHA256[row['role']]:raise ValueError('Reference identity is not the pinned Leo/Mia version')
  relative=Path(row['path_relative_to_outputs']);path=outputs/relative
  if relative.is_absolute() or '..' in relative.parts or path.is_symlink() or not path.resolve().is_relative_to(outputs) or not path.is_file():raise ValueError('Approved reference path unavailable')
  if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('Approved Leo/Mia reference changed; restore it or prepare a separately reviewed reference version')
 return value

def validate_speech_source(contract=None,outputs=None,scene=None):
 value=validate_contract(contract,outputs);scene=Path(scene or SCENE);source=scene/'source.mp4';metadata=scene/'scene.json'
 if scene.is_symlink() or source.is_symlink() or metadata.is_symlink() or not source.is_file() or not metadata.is_file() or metadata.stat().st_size>20000:raise ValueError('Approved speaking reference unavailable')
 data=json.loads(metadata.read_text());expected=next(x['sha256'] for x in value['assets'] if x['role']=='motion_reference')
 if (data.get('brand')!='minddoodles' or data.get('id')!='hands-free-v1' or data.get('source_kind')!='edited_approved_reference'
  or data.get('counts_as_fresh_daily_output') is not False or data.get('files',{}).get('source.mp4')!=expected or digest(source)!=expected):
  raise ValueError('This speaking scene does not use the approved Leo/Mia motion reference')
 return {'style_id':STYLE,'reference_integrity':'verified','new_animation_identity_verified':False,'counts_as_fresh_daily_output':False}
