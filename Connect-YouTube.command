#!/bin/zsh
cd "${0:A:h}"
"$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" connect_youtube.py
read '?Press Enter to close.'
