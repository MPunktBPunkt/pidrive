#!/usr/bin/env bash
set -euo pipefail
cd /home/martin/projects/pidrive
OUT=docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700/status-poll.jsonl
extra=()
if [[ -f "$OUT" && -s "$OUT" ]]; then
  extra+=(--append)
fi
exec python3 tools/feld_status_poll.py --esp http://192.168.178.89 \
  --run-id feld-s1-1700 \
  --out "$OUT" \
  --seconds "${1:-120}" --print "${extra[@]}"
