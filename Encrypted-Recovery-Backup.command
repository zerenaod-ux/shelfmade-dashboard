#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
"$RUNTIME" - <<'PY'
from pathlib import Path
import getpass,json,secure_backup,datetime,os,shlex
print('Encrypted recovery backup — no uploading or publishing.')
print('Wait for jobs to finish. Prefer an external drive you control.')
print('Includes app state/source and finished draft media. Original studio, external music and voice runtimes/models need separate preservation.')
raw=input('Destination folder (you may drag a folder here): ').strip()
parts=shlex.split(raw)
destination=raw if Path(raw).expanduser().is_dir() else parts[0] if len(parts)==1 else raw
media=input('Include app media and footage library? [y/N]: ').strip().lower()=='y'
credentials=input('Include private provider connection files in the encrypted archive? [y/N]: ').strip().lower()=='y'
password=getpass.getpass('Backup passphrase (at least 16 characters; not stored): ')
if password!=getpass.getpass('Confirm backup passphrase: '):raise SystemExit('Passphrases did not match. Nothing exported.')
try:
 result=secure_backup.create(destination,password,media,credentials)
 print('Encrypted archive created. Testing recovery without changing the live app…')
 verified=secure_backup.restore_check(result['archive'],password)
 receipt_path=secure_backup.BASE/'operations-receipts.json'
 try:receipt=json.loads(receipt_path.read_text())
 except (OSError,ValueError):receipt={}
 receipt['encrypted_backup']={'name':Path(result['archive']).name,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'restore_verified':verified['verified'],'includes_media':media,'includes_credentials':credentials,'different_volume':result['different_volume'],'off_device_copy_verified':False}
 temp=receipt_path.with_suffix('.pending');fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:json.dump(receipt,f,indent=2)
 temp.replace(receipt_path)
 print('Recovery test PASSED. Archive:',result['archive'])
 print('Keep the passphrase in your password manager. Confirm the destination is on a separate physical device for off-device protection.')
except (ValueError,OSError) as error:print('Backup stopped:',error);raise SystemExit(1)
PY
read '?Press Enter to close.'
