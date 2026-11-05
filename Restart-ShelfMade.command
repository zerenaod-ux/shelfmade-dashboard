#!/bin/zsh
cd "${0:A:h}" || exit 1
RUNTIME="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
"$RUNTIME" '../studio-controls/restart_shared.py'
read '?Press Enter to close.'
