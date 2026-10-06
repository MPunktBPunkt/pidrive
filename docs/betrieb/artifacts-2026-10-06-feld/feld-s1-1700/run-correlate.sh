#!/usr/bin/env bash
set -euo pipefail
cd /home/martin/projects/pidrive
CORR="${1:-docs/betrieb/artifacts-2026-10-06-feld/feld-s1-1700/correlate-run}"
mkdir -p "$CORR"
python3 tools/feld_av_correlate.py --esp http://192.168.178.89 --watch-s 90 --interval 0.5 --dense --out "$CORR" \
  2>&1 | tee "$CORR/correlate.log"
python3 tools/feld_av_burst_summary.py "$CORR/correlate-watch.jsonl" > "$CORR/burst-summary.json" 2>/dev/null || true
echo "DONE $CORR"
