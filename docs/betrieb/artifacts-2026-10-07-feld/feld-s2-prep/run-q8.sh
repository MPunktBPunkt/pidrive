#!/usr/bin/env bash
# Q8/R10-Auswertung einer msc_reads-Datei (nach dem Termin oder zwischen Teilen).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd /home/martin/projects/pidrive
READS="${1:-$ROOT/msc_reads-A.jsonl}"
OUT="${2:-$ROOT/q8-$(basename "$READS" .jsonl)}"
mkdir -p "$OUT"
extra=()
[[ -n "${TRACE:-}" ]] && extra+=(--trace "$TRACE")
exec python3 tools/feld_q8_msc_order.py --reads "$READS" --out-dir "$OUT" "${extra[@]}"
