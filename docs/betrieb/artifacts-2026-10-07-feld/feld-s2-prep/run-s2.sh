#!/usr/bin/env bash
# Feld s2: alle Mitschnitte mit einem Befehl (Pi, eigenes Terminal).
#   Bridge --no-audio (msc.reads), Status-Poll 1 Hz, mscTrace-Poll 4 Hz.
#   Ctrl-C beendet alles, kopiert msc.reads in den Lauf-Ordner und startet
#   den Bridge-Dienst wieder (RESTORE_SERVICE=0 verhindert das).
# Marken aus einem zweiten Terminal: ./mark.sh "A1 BOB tap"
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="${PROJ:-/home/martin/projects/pidrive}"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
BRIDGE="${BRIDGE:-/home/pidrive/pump_bridge.py}"
READS="${MSC_READS:-/tmp/pidrive_msc_reads.jsonl}"
SECONDS_MAX="${1:-2400}"
RUN="$ROOT/s2-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN"
echo "$RUN" > "$ROOT/CURRENT_RUN"

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
    python3 - "$RUN/msc_reads.jsonl" <<'PY'
import json, sys
ov = []
for line in open(sys.argv[1], errors="replace"):
    j = line.find("{")
    if j < 0:
        continue
    try:
        r = json.loads(line[j:])
    except Exception:
        continue
    if "ov" in r:
        ov.append(int(r.get("ov") or 0))
print(f"ov first={ov[0]} last={ov[-1]}" if ov else "ov: (keine Zeilen)")
PY
  fi
  [[ -f "$ROOT/marks.jsonl" ]] && cp -a "$ROOT/marks.jsonl" "$RUN/marks.jsonl"
  cp -a "$ROOT/OPERATOR-LIVE.txt" "$RUN/OPERATOR-LIVE.txt" 2>/dev/null
  if [[ "${RESTORE_SERVICE:-1}" == "1" ]]; then
    sudo systemctl start pidrive_pump_bridge 2>/dev/null && echo "pidrive_pump_bridge wieder gestartet"
  fi
  rm -f "$ROOT/CURRENT_RUN"
  echo "Lauf-Ordner: $RUN"
  echo "Auswertung: python3 $PROJ/tools/feld_q8_msc_order.py --reads $RUN/msc_reads.jsonl --trace $RUN/trace.jsonl --out-dir $RUN/q8"
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
echo "   Marken: $ROOT/mark.sh \"Text\"     Stopp: Ctrl-C"
"$ROOT/mark.sh" "RUN START $(basename "$RUN")" >/dev/null

# Lebenszeichen alle 10 s: Zeilen in msc.reads, letzte Trace-Poll-Zeile
while true; do
  sleep 10
  n=$(wc -l < "$READS" 2>/dev/null || echo 0)
  tp=$(tail -n 1 "$RUN/trace.jsonl.polls.jsonl" 2>/dev/null | cut -c1-110)
  alive=""
  for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null || alive="$alive DEAD:$p"; done
  echo "$(date +%H:%M:%S) msc.reads=$n  trace: ${tp:-–}$alive"
done
