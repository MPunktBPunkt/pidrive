#!/usr/bin/env bash
set -euo pipefail
cd /home/martin/projects/pidrive
.venv-ingest/bin/python tools/ingest/ingest.py \
  --run docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700
