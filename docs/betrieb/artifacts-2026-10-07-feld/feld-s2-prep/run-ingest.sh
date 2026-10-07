#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd /home/martin/projects/pidrive
if [[ ! -d .venv-ingest ]]; then
  python3 -m venv .venv-ingest
  .venv-ingest/bin/pip install -q -r tools/ingest/requirements.txt
fi
exec .venv-ingest/bin/python tools/ingest/ingest.py --run "$ROOT"
