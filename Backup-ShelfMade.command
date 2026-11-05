#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$RUNTIME" ]]; then
 print 'The configured dashboard Python is missing. See README.md.'
 exit 1
fi
"$RUNTIME" - <<'PY'
import maintenance
result=maintenance.backup()
print('Private state/source snapshot:',result['snapshot'])
verified=maintenance.verify_snapshot(result['snapshot'])
print('Hash verification:', 'PASS' if verified['verified'] else 'FAILED')
print('This excludes media, voice dependencies and private credential files. See docs/Maintenance.md for complete recovery backups.')
if not verified['verified']:raise SystemExit(1)
PY
read '?Press Enter to close.'
