#!/usr/bin/env bash
# Wrapper: gleiche Capture-Pipeline wie Feld s2, Laufordner s3-* hier.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="${PROJ:-/home/martin/projects/pidrive}"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
BRIDGE="${BRIDGE:-/home/pidrive/pump_bridge.py}"
READS="${MSC_READS:-/tmp/pidrive_msc_reads.jsonl}"
SECONDS_MAX="${1:-1200}"
RUN="$ROOT/s3-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN"
echo "$RUN" > "$ROOT/CURRENT_RUN"
: > "$ROOT/marks.jsonl"
: > "$ROOT/OPERATOR-LIVE.txt"

if [[ ! -f "$BRIDGE" ]]; then
  echo "Bridge nicht gefunden: $BRIDGE (BRIDGE=... setzen)" >&2
  exit 1
fi
if ! curl -s -m 3 "$ESP/api/metrics" -o /dev/null; then
  echo "WARN: $ESP/api/metrics nicht erreichbar — Polls laufen trotzdem weiter" >&2
fi

pids=()
finish() {
  trap - INT TERM EXIT
  echo
  echo "== Stopp: $(date +%H:%M:%S)"
  for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done
  sleep 1
  for p in "${pids[@]}"; do kill -9 "$p" 2>/dev/null; done
  if [[ -f "$READS" ]]; then
    cp -a "$READS" "$RUN/msc_reads.jsonl"
    echo "msc.reads → $RUN/msc_reads.jsonl ($(wc -l < "$RUN/msc_reads.jsonl") Zeilen)"
  fi
  [[ -f "$ROOT/marks.jsonl" ]] && cp -a "$ROOT/marks.jsonl" "$RUN/marks.jsonl"
  cp -a "$ROOT/OPERATOR-LIVE.txt" "$RUN/OPERATOR-LIVE.txt" 2>/dev/null || true
  if [[ "${RESTORE_SERVICE:-1}" == "1" ]]; then
    sudo systemctl start pidrive_pump_bridge 2>/dev/null && echo "pidrive_pump_bridge wieder gestartet"
  fi
  rm -f "$ROOT/CURRENT_RUN"
  echo "Lauf-Ordner: $RUN"
  echo "Auswertung:"
  echo "  python3 $PROJ/tools/feld_q8_msc_order.py --reads $RUN/msc_reads.jsonl --trace $RUN/trace.jsonl --out-dir $RUN/q8"
  exit 0
}
trap finish INT TERM EXIT

sudo systemctl stop pidrive_pump_bridge 2>/dev/null || true
: > "$READS"
python3 "$BRIDGE" --transport tcp --host "$ESP_HOST" --no-audio > "$RUN/bridge-noaudio.log" 2>&1 &
pids+=($!)

cd "$PROJ"
python3 tools/feld_status_poll.py --esp "$ESP" --run-id "$(basename "$RUN")" \
  --out "$RUN/status-poll.jsonl" --interval 1 --seconds "$SECONDS_MAX" > "$RUN/status-poll.log" 2>&1 &
pids+=($!)
python3 tools/feld_trace_poll.py --esp "$ESP" --hz 4 \
  --out "$RUN/trace.jsonl" --seconds "$SECONDS_MAX" --print > "$RUN/trace-poll.log" 2>&1 &
pids+=($!)

echo "== Start $(date +%H:%M:%S)  Lauf: $RUN"
echo "   Bridge PID ${pids[0]}, Status-Poll ${pids[1]}, Trace-Poll ${pids[2]}"
echo "   Marken: $ROOT/mark.sh \"A Rock build\""
echo "   Soft-RST: curl -s -m 3 -X POST $ESP/api/restart"
echo "   Pocket: $ROOT/GO.md"
# keep alive
while kill -0 "${pids[1]}" 2>/dev/null; do sleep 2; done
wait || true
