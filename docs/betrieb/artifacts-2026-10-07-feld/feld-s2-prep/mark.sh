#!/usr/bin/env bash
# Wanduhr-Marke für das Feldprotokoll: ./mark.sh "A1 BOB tap"
# Schreibt OPERATOR-LIVE.txt (lesbar) und marks.jsonl (für die Auswertung).
# Zuordnung zu ESP-ms über trace.jsonl.polls.jsonl (wall + uptimeMs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TEXT="${*:?Text fehlt, z.B. ./mark.sh \"A1 BOB tap\"}"
WALL=$(date +%s.%N | cut -c1-14)
HMS=$(date +%H:%M:%S)
RUN=""
[[ -f "$ROOT/CURRENT_RUN" ]] && RUN="$(basename "$(cat "$ROOT/CURRENT_RUN")")"
echo "t=$HMS  $TEXT" >> "$ROOT/OPERATOR-LIVE.txt"
python3 -c 'import json,sys; print(json.dumps({"wall": float(sys.argv[1]), "hms": sys.argv[2], "run": sys.argv[3], "text": sys.argv[4]}, ensure_ascii=False))' \
  "$WALL" "$HMS" "$RUN" "$TEXT" >> "$ROOT/marks.jsonl"
echo "mark $HMS  $TEXT"
