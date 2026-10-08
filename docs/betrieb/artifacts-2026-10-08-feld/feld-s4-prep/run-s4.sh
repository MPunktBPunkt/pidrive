#!/usr/bin/env bash
# Feld s4: Audio-Capture mit Feldrate + Zählton (Tonfenster).
#   ./run-s4.sh [SEKUNDEN]
#   BRIDGE_ARGS='--bitrate 32k --target-bps 4000 --marker --marker-period 1' ./run-s4.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
# Auto-Pi: /home/pidrive/pidrive · Dev: …/projects/pidrive
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
# Default laut FELDPROTOKOLL-S4: Audio, 48k, 6000 B/s, Marker 1 s
BRIDGE_ARGS="${BRIDGE_ARGS:---bitrate 48k --target-bps 6000 --marker --marker-period 1}"
SECONDS_MAX="${1:-1800}"
RUN="$ROOT/s4-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN"
echo "$RUN" > "$ROOT/CURRENT_RUN"
: > "$ROOT/marks.jsonl"
: > "$ROOT/OPERATOR-LIVE.txt"

if [[ ! -f "$BRIDGE" ]]; then
  # Fallback Lab-/Dev-Host
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
  echo "  python3 $PROJ/tools/feld_live_window.py --run $RUN"
  echo "  python3 $PROJ/tools/feld_q8_msc_order.py --reads $RUN/msc_reads.jsonl --trace $RUN/trace.jsonl --out-dir $RUN/q8"
  exit 0
}
trap finish INT TERM EXIT

sudo systemctl stop pidrive_pump_bridge 2>/dev/null || true
# Cron/ensure darf nicht sofort wieder starten — manuelle Prozesse killen
pkill -f '/home/pidrive/pump_bridge.py' 2>/dev/null || true
sleep 5
if systemctl is-active --quiet pidrive_pump_bridge 2>/dev/null; then
  echo "ABBRUCH: pidrive_pump_bridge läuft noch (stop fehlgeschlagen)" >&2
  exit 2
fi
if pgrep -f '/home/pidrive/pump_bridge.py' >/dev/null 2>&1; then
  echo "ABBRUCH: fremde pump_bridge noch aktiv" >&2
  pgrep -af pump_bridge.py >&2 || true
  exit 2
fi
: > "$READS"
BRIDGE_LOG="$RUN/bridge-audio.log"
# shellcheck disable=SC2086
python3 "$BRIDGE" --transport tcp --host "$ESP_HOST" $BRIDGE_ARGS > "$BRIDGE_LOG" 2>&1 &
pids+=($!)

sleep 12
if ! kill -0 "${pids[0]}" 2>/dev/null; then
  echo "ABBRUCH: Capture-Bridge nach 12 s tot — Log: $BRIDGE_LOG" >&2
  tail -n 40 "$BRIDGE_LOG" >&2
  exit 3
fi
MY_IP="$(ip route get "$ESP_HOST" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')"
PEER="$(curl -s -m 3 "$ESP/api/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("pumpTcpPeer") or "")' 2>/dev/null)"
if [[ -n "$PEER" && -n "$MY_IP" && "$PEER" != "$MY_IP" && "${ALLOW_FOREIGN_BRIDGE:-0}" != "1" ]]; then
  echo "ABBRUCH: ESP-Pump-Link gehört $PEER, nicht diesem Host ($MY_IP). Fremde Bridge stoppen oder ALLOW_FOREIGN_BRIDGE=1" >&2
  exit 4
fi
echo "   Pump-Link: peer=${PEER:-?} self=${MY_IP:-?} args=$BRIDGE_ARGS"

cd "$PROJ"
python3 tools/feld_status_poll.py --esp "$ESP" --run-id "$(basename "$RUN")" \
  --out "$RUN/status-poll.jsonl" --interval 1 --seconds "$SECONDS_MAX" > "$RUN/status-poll.log" 2>&1 &
pids+=($!)
python3 tools/feld_trace_poll.py --esp "$ESP" --hz 4 \
  --out "$RUN/trace.jsonl" --seconds "$SECONDS_MAX" --print > "$RUN/trace-poll.log" 2>&1 &
pids+=($!)

echo "== Start $(date +%H:%M:%S)  Lauf: $RUN"
echo "   Bridge PID ${pids[0]}, Status-Poll ${pids[1]}, Trace-Poll ${pids[2]}"
echo "   Marken: $ROOT/mark.sh \"K1 BOB tap\""
echo "   Check:  $ROOT/s4-check.sh before-tap"
echo "   Pocket: $ROOT/GO.md"
"$ROOT/mark.sh" "RUN START $(basename "$RUN")" >/dev/null || true

while kill -0 "${pids[1]}" 2>/dev/null; do
  sleep 10
  n=$(wc -l < "$READS" 2>/dev/null || echo 0)
  echo "$(date +%H:%M:%S) msc.reads=$n bridge=$(kill -0 "${pids[0]}" 2>/dev/null && echo up || echo DEAD)"
done
wait || true
