#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null; then
  echo 'Instale Python 3.11 ou superior antes de continuar.'
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
if [ ! -f .venv/.rp-installed ]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.rp-installed
fi
exec .venv/bin/python -m rp_creator "$@"
