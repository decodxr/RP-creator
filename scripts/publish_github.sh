#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if ! command -v gh >/dev/null; then
  echo 'Instale o GitHub CLI (gh) e entre com gh auth login.'
  exit 1
fi
if [ ! -d .git ]; then
  echo 'Primeiro restaure o histórico: git clone RP-creator.bundle RP-creator-com-historico'
  echo 'Depois execute este script dentro do clone.'
  exit 1
fi
gh auth status
gh repo create RP-creator --private --source=. --remote=origin --push
