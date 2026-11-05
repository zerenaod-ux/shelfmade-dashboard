"""Build label and the source revision loaded by this dashboard process."""
import hashlib
from pathlib import Path
BUILD='content-empire-shelfmade-v47'

def source_revision(root=None):
 """Hash backend code and the MindDoodles worker it dispatches to."""
 root=Path(root) if root is not None else Path(__file__).resolve().parent
 files=[(p,p.relative_to(root).as_posix()) for p in [*root.glob('*.py'),*(root/'generator').glob('*.py')]]
 # MindDoodles' render and resume implementation lives beside the dashboard.
 # Include it in the activation fingerprint so the owner launcher notices
 # worker fixes instead of reporting a healthy but stale long-lived process.
 if root.resolve()==Path(__file__).resolve().parent:
  outputs=root.parent
  worker=outputs/'minddoodles-production'/'short_creator'
  if worker.is_dir():files.extend((p,'minddoodles-production/short_creator/'+p.relative_to(worker).as_posix()) for p in worker.glob('*.py'))
  assembler=outputs/'minddoodles-production'/'toast-password-v1'/'assemble_story.py'
  if assembler.is_file():files.append((assembler,'minddoodles-production/toast-password-v1/assemble_story.py'))
  mindlore_renderer=outputs/'content-empire-studio'/'tools'/'rebuild_mindlore_library.py'
  if mindlore_renderer.is_file():files.append((mindlore_renderer,'content-empire-studio/tools/rebuild_mindlore_library.py'))
 files.sort(key=lambda item:item[1])
 if not files:raise ValueError('No studio backend source files found.')
 digest=hashlib.sha256()
 for file,name in files:
  if file.is_symlink():raise ValueError('Backend source link cannot be verified.')
  relative=name.encode()
  try:data=file.read_bytes()
  except OSError:continue  # cloud-only (iCloud) file: skip instead of hanging
  digest.update(len(relative).to_bytes(8,'big'));digest.update(relative)
  digest.update(len(data).to_bytes(8,'big'));digest.update(data)
 return digest.hexdigest()

# Capture once at process import. Reading the files on every health request would
# report the installed update even though the process still runs earlier code.
SOURCE_REVISION=source_revision()
