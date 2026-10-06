#!/usr/bin/env bash
set -euo pipefail
cd /home/martin/projects/pidrive
exec python3 tools/feld_status_poll.py --esp http://192.168.178.89 \
  --run-id feld-s1-1700 \
  --out docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700/status-poll.jsonl \
  --seconds "${1:-120}" --print
