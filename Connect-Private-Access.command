#!/bin/zsh
cd "${0:A:h}"
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ -x "$RUNTIME" ]]; then
 "$RUNTIME" connect_remote.py
else
 print 'The dashboard runtime is unavailable. Ask Codex to reconnect it.'
fi
read '?Press Enter to close this window.'
