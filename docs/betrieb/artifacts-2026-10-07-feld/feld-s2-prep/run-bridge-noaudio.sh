#!/usr/bin/env bash
# Bridge mit --no-audio → msc.reads, kein Live-Audio (Feld s2).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
BRIDGE="${BRIDGE:-/home/pidrive/pump_bridge.py}"
LOG="$ROOT/bridge-noaudio.log"
READS="${MSC_READS:-/tmp/pidrive_msc_reads.jsonl}"

if [[ ! -f "$BRIDGE" ]]; then
  echo "Bridge nicht gefunden: $BRIDGE" >&2
  echo "Auf dem Pi: BRIDGE=/pfad/zu/pump_bridge.py $0" >&2
  exit 1
fi

sudo systemctl stop pidrive_pump_bridge 2>/dev/null || true
: > "$READS"
echo "msc.reads → $READS (leer)"
echo "Log → $LOG"
echo "Ctrl-C beendet die Bridge; danach: sudo systemctl start pidrive_pump_bridge"
exec python3 "$BRIDGE" --transport tcp --host "$ESP_HOST" --no-audio 2>&1 | tee "$LOG"
