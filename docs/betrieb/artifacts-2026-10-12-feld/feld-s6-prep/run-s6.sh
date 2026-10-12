#!/usr/bin/env bash
# Feld s6: Q11-first (ohne Bridge) oder Stream @32k.
#   ./run-s6.sh q11 [SEKUNDEN]      # Status+Trace, keine Pump-Bridge
#   ./run-s6.sh stream [SEKUNDEN]   # wie s5: Bridge 32k + Polls
#   ./run-s6.sh [SEKUNDEN]          # Alias = stream
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="stream"
SECONDS_MAX=1800
if [[ "${1:-}" == "q11" || "${1:-}" == "stream" ]]; then
  MODE="$1"
  SECONDS_MAX="${2:-1800}"
elif [[ -n "${1:-}" ]]; then
  SECONDS_MAX="$1"
fi
if [[ -z "${PROJ:-}" ]]; then
  for cand in \
    "$(cd "$ROOT/../../../../.." && pwd)" \
    /home/pidrive/pidrive \
    /home/martin/projects/pidrive; do
    if [[ -f "$cand/tools/feld_status_poll.py" ]]; then
      PROJ="$cand"
      break
    fi
  done
fi
PROJ="${PROJ:?pidrive-Root nicht gefunden (PROJ=… setzen)}"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
BRIDGE="${BRIDGE:-/home/pidrive/pump_bridge.py}"
READS="${MSC_READS:-/tmp/pidrive_msc_reads.jsonl}"
BRIDGE_ARGS="${BRIDGE_ARGS:---bitrate 32k --target-bps 4000 --marker --marker-period 1 --msc-lock}"
RUN="$ROOT/s6-$(date +%Y%m%d-%H%M%S)-$MODE"
mkdir -p "$RUN"
echo "$RUN" > "$ROOT/CURRENT_RUN"
: > "$ROOT/marks.jsonl"
: > "$ROOT/OPERATOR-LIVE.txt"

pids=()
finish() {
  trap - INT TERM EXIT
  echo
  echo "== Stopp: $(date +%H:%M:%S) mode=$MODE"
  for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done
  sleep 1
  for p in "${pids[@]}"; do kill -9 "$p" 2>/dev/null; done
  if [[ -f "$READS" ]]; then
    cp -a "$READS" "$RUN/msc_reads.jsonl" 2>/dev/null || true
    echo "msc.reads → $RUN/msc_reads.jsonl ($(wc -l < "$RUN/msc_reads.jsonl" 2>/dev/null || echo 0) Zeilen)"
  fi
  [[ -f "$ROOT/marks.jsonl" ]] && cp -a "$ROOT/marks.jsonl" "$RUN/marks.jsonl"
  cp -a "$ROOT/OPERATOR-LIVE.txt" "$RUN/OPERATOR-LIVE.txt" 2>/dev/null || true
  if [[ "$MODE" == "stream" && "${RESTORE_SERVICE:-1}" == "1" ]]; then
    sudo systemctl start pidrive_pump_bridge 2>/dev/null && echo "pidrive_pump_bridge wieder gestartet"
  fi
  rm -f "$ROOT/CURRENT_RUN"
  echo "Lauf-Ordner: $RUN"
  echo "Auswertung:"
  echo "  python3 $PROJ/tools/feld_live_window.py --run $RUN --bps 4000"
  echo "  python3 $PROJ/tools/feld_q8_msc_order.py --reads $RUN/msc_reads.jsonl --trace $RUN/trace.jsonl --out-dir $RUN/q8"
  exit 0
}
trap finish INT TERM EXIT

if ! curl -s -m 3 "$ESP/api/metrics" -o /dev/null; then
  echo "WARN: $ESP/api/metrics nicht erreichbar — Polls laufen trotzdem weiter" >&2
fi

if [[ "$MODE" == "stream" ]]; then
  if [[ ! -f "$BRIDGE" ]]; then
    for ALT in \
      "$PROJ/../esphub/esp32.pidrive/tools/pump_bridge.py" \
      /home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py; do
      if [[ -f "$ALT" ]]; then
        BRIDGE="$ALT"
        echo "WARN: nutze Bridge $BRIDGE"
        break
      fi
    done
  fi
  if [[ ! -f "$BRIDGE" ]]; then
    echo "Bridge nicht gefunden: $BRIDGE (BRIDGE=… setzen)" >&2
    exit 1
  fi
  sudo systemctl stop pidrive_pump_bridge 2>/dev/null || true
  pkill -f '/home/pidrive/pump_bridge.py' 2>/dev/null || true
  sleep 5
  if systemctl is-active --quiet pidrive_pump_bridge 2>/dev/null; then
    echo "ABBRUCH: pidrive_pump_bridge läuft noch" >&2
    exit 2
  fi
  : > "$READS"
  BRIDGE_LOG="$RUN/bridge-audio.log"
  NAME_OVERRIDE_FILE="${NAME_OVERRIDE_FILE:-/tmp/pidrive-name-overrides.json}"
  [[ -f "$NAME_OVERRIDE_FILE" ]] || echo '{}' > "$NAME_OVERRIDE_FILE"
  # shellcheck disable=SC2086
  python3 "$BRIDGE" --transport tcp --host "$ESP_HOST" $BRIDGE_ARGS \
    --name-override-file "$NAME_OVERRIDE_FILE" > "$BRIDGE_LOG" 2>&1 &
  pids+=($!)
  sleep 12
  if ! kill -0 "${pids[0]}" 2>/dev/null; then
    echo "ABBRUCH: Capture-Bridge tot — $BRIDGE_LOG" >&2
    tail -n 40 "$BRIDGE_LOG" >&2
    exit 3
  fi
  MY_IP="$(ip route get "$ESP_HOST" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')"
  PEER="$(curl -s -m 3 "$ESP/api/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("pumpTcpPeer") or "")' 2>/dev/null)"
  if [[ -n "$PEER" && -n "$MY_IP" && "$PEER" != "$MY_IP" && "${ALLOW_FOREIGN_BRIDGE:-0}" != "1" ]]; then
    echo "ABBRUCH: ESP-Pump-Link gehört $PEER, nicht $MY_IP" >&2
    exit 4
  fi
  echo "   Pump-Link: peer=${PEER:-?} self=${MY_IP:-?} args=$BRIDGE_ARGS"
else
  echo "   MODE=q11 — keine Pump-Bridge (Steckfestigkeit / UART)"
  echo "   Service pidrive_pump_bridge wird nicht angefasst"
fi

cd "$PROJ"
python3 tools/feld_status_poll.py --esp "$ESP" --run-id "$(basename "$RUN")" \
  --out "$RUN/status-poll.jsonl" --interval 1 --seconds "$SECONDS_MAX" > "$RUN/status-poll.log" 2>&1 &
STATUS_PID=$!
pids+=($STATUS_PID)
python3 tools/feld_trace_poll.py --esp "$ESP" --hz 4 \
  --out "$RUN/trace.jsonl" --seconds "$SECONDS_MAX" --print > "$RUN/trace-poll.log" 2>&1 &
pids+=($!)

echo "== Start $(date +%H:%M:%S)  Lauf: $RUN  mode=$MODE"
echo "   Marken: $ROOT/mark.sh \"Q11 …\""
echo "   Check:  $ROOT/s6-check.sh after-plug"
echo "   Pocket: $ROOT/GO.md"
"$ROOT/mark.sh" "RUN START $(basename "$RUN") mode=$MODE" >/dev/null || true

while kill -0 "$STATUS_PID" 2>/dev/null; do
  sleep 10
  if [[ "$MODE" == "stream" ]]; then
    n=$(wc -l < "$READS" 2>/dev/null || echo 0)
    echo "$(date +%H:%M:%S) msc.reads=$n bridge=$(kill -0 "${pids[0]}" 2>/dev/null && echo up || echo DEAD)"
  else
    echo "$(date +%H:%M:%S) q11-polls alive (no bridge)"
  fi
done
wait || true
