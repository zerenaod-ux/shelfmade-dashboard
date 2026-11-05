#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$RUNTIME" ]]; then
 print 'The configured dashboard Python is missing. See README.md → Dependencies outside the app folder.'
 exit 1
fi
"$RUNTIME" maintenance.py check --live
print '\nThis checks local health and the running build; provider authorization is not tested.'
read '?Press Enter to close.'
