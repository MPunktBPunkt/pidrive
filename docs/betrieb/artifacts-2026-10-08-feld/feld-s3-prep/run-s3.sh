#!/usr/bin/env bash
# Wrapper: gleiche Capture-Pipeline wie Feld s2, Laufordner s3-* hier.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="${PROJ:-/home/martin/projects/pidrive}"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
BRIDGE="${BRIDGE:-/home/pidrive/pump_bridge.py}"
READS="${MSC_READS:-/tmp/pidrive_msc_reads.jsonl}"
# Nutzung: run-s3.sh [--with-audio] [SEKUNDEN]
#   --with-audio  Capture-Bridge liefert selbst Audio (sonst --no-audio, nur Menü/Reads)
#   ALLOW_FOREIGN_BRIDGE=1  nicht abbrechen, wenn ein anderer Host den Pump-Link hält
WITH_AUDIO=0
if [[ "${1:-}" == "--with-audio" ]]; then
  WITH_AUDIO=1
  shift
fi
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
if systemctl is-active --quiet pidrive_pump_bridge 2>/dev/null; then
  echo "ABBRUCH: pidrive_pump_bridge läuft noch (stop fehlgeschlagen)" >&2
  exit 2
fi
: > "$READS"
if [[ "$WITH_AUDIO" == "1" ]]; then
  BRIDGE_LOG="$RUN/bridge-audio.log"
  python3 "$BRIDGE" --transport tcp --host "$ESP_HOST" > "$BRIDGE_LOG" 2>&1 &
else
  BRIDGE_LOG="$RUN/bridge-noaudio.log"
  python3 "$BRIDGE" --transport tcp --host "$ESP_HOST" --no-audio > "$BRIDGE_LOG" 2>&1 &
fi
pids+=($!)

# Liveness: s3 lief 20 min mit sofort toter Capture-Bridge (BrokenPipe), weil ein
# anderer Bridge-Host den sticky Pump-Link hielt → msc_reads leer.
sleep 10
if ! kill -0 "${pids[0]}" 2>/dev/null; then
  echo "ABBRUCH: Capture-Bridge nach 10 s tot — Log: $BRIDGE_LOG" >&2
  tail -n 15 "$BRIDGE_LOG" >&2
  exit 3
fi
MY_IP="$(ip route get "$ESP_HOST" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')"
PEER="$(curl -s -m 3 "$ESP/api/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("pumpTcpPeer") or "")' 2>/dev/null)"
if [[ -n "$PEER" && -n "$MY_IP" && "$PEER" != "$MY_IP" && "${ALLOW_FOREIGN_BRIDGE:-0}" != "1" ]]; then
  echo "ABBRUCH: ESP-Pump-Link gehört $PEER, nicht diesem Host ($MY_IP). Fremde Bridge stoppen oder ALLOW_FOREIGN_BRIDGE=1" >&2
  exit 4
fi
echo "   Pump-Link: peer=${PEER:-?} self=${MY_IP:-?} audio=$WITH_AUDIO"

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
