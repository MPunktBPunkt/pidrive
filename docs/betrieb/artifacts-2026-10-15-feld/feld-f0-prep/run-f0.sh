#!/usr/bin/env bash
# F0 Status-Poll (Stall aus). Optional stream wie s6.
#   ./run-f0.sh poll [SEKUNDEN]
#   ./run-f0.sh stream [SEKUNDEN]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-poll}"
SECONDS_MAX="${2:-1200}"
if [[ "$MODE" != "poll" && "$MODE" != "stream" ]]; then
  echo "Usage: $0 poll|stream [seconds]" >&2
  exit 1
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
PROJ="${PROJ:?pidrive-Root nicht gefunden}"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
RUN="$ROOT/f0-$(date +%Y%m%d-%H%M%S)-$MODE"
mkdir -p "$RUN"
echo "$RUN" > "$ROOT/CURRENT_RUN"
: > "$ROOT/marks.jsonl"
: > "$ROOT/OPERATOR-LIVE.txt"

# Freeze-Gate
if ! "$ROOT/f0-check.sh" start-gate > "$RUN/status-start.json"; then
  echo "ABORT: stall freeze oder Status fehlgeschlagen — siehe $RUN/status-start.json" >&2
  rm -f "$ROOT/CURRENT_RUN"
  exit 2
fi
cp -a "$RUN/status-start.json" "$ROOT/status-start.json" 2>/dev/null || true

pids=()
finish() {
  trap - INT TERM EXIT
  for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null; done
  sleep 1
  for p in "${pids[@]:-}"; do kill -9 "$p" 2>/dev/null; done
  [[ -f "$ROOT/marks.jsonl" ]] && cp -a "$ROOT/marks.jsonl" "$RUN/marks.jsonl"
  cp -a "$ROOT/OPERATOR-LIVE.txt" "$RUN/OPERATOR-LIVE.txt" 2>/dev/null || true
  for f in identity-before-*.json identity-after-*.json; do
    [[ -f "$ROOT/$f" ]] && cp -a "$ROOT/$f" "$RUN/$f" 2>/dev/null || true
  done
  rm -f "$ROOT/CURRENT_RUN"
  echo "Lauf-Ordner: $RUN"
  echo "Auswertung: PROTOKOLL.md → ERGEBNIS.md (Vorlage kopieren)"
}
trap finish INT TERM EXIT

echo "== F0 $MODE start $(date +%H:%M:%S) ESP=$ESP → $RUN"
python3 "$PROJ/tools/feld_status_poll.py" --esp "$ESP" --interval 1 \
  --out "$RUN/status-poll.jsonl" &
pids+=($!)

if [[ "$MODE" == "stream" ]]; then
  # Bridge nur wenn Operator LIVE-Bytes braucht; sonst poll reicht für Identity/playingUid
  BRIDGE="${BRIDGE:-/home/pidrive/pump_bridge.py}"
  if [[ -f "$BRIDGE" ]]; then
    sudo systemctl stop pidrive_pump_bridge 2>/dev/null || true
    python3 "$BRIDGE" --esp "$ESP_HOST" --bitrate 32k --target-bps 4000 \
      --marker --marker-period 1 >> "$RUN/bridge-audio.log" 2>&1 &
    pids+=($!)
  else
    echo "WARN: Bridge nicht gefunden ($BRIDGE) — nur Poll" >&2
  fi
fi

echo "Marken: ./mark.sh \"B0 control replug\""
echo "Identity: ./f0-identity.sh serial|label|volume-id"
sleep "$SECONDS_MAX"
