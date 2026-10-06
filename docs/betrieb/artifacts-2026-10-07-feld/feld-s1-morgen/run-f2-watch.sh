#!/usr/bin/env bash
# F2: Live-Watcher Hit/Miss während fav1→fav2→fav1 / Remount
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ESP="${ESP:-http://192.168.178.89}"
cd /home/martin/projects/pidrive
exec python3 tools/feld_f2_watch.py --esp "$ESP" --out "$ROOT/f2-watch.jsonl" --seconds "${1:-300}"
