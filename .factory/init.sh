#!/usr/bin/env sh
set -eu

python3 --version >/dev/null

VENV=".factory/runtime/research-addon-venv"

mkdir -p .factory/runtime
mkdir -p /tmp/fotball-analyst-research-addon

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi

printf '%s\n' "research-addon init ready (use per-run subdirs under /tmp/fotball-analyst-research-addon)"
