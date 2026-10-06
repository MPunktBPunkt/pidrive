#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd /home/martin/projects/pidrive
OUT="$ROOT/status-poll.jsonl"
ESP="${ESP:-http://192.168.178.89}"
extra=()
if [[ -f "$OUT" && -s "$OUT" ]]; then
  extra+=(--append)
fi
exec python3 tools/feld_status_poll.py --esp "$ESP" \
  --run-id feld-s1-morgen \
  --out "$OUT" \
  --seconds "${1:-300}" --print "${extra[@]}"
