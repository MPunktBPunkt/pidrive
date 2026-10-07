#!/usr/bin/env bash
# F1: Poll + interaktiver Timer-Logger (zweites Terminal empfohlen)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ESP="${ESP:-http://192.168.178.89}"
cd /home/martin/projects/pidrive
exec python3 tools/feld_f1_log.py --esp "$ESP" --out "$ROOT/f1-events.jsonl" --uid "${1:-fav0}"
