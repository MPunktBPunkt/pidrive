#!/usr/bin/env bash
# Wait for Feld-ESP .89 → OTA 0.4.52-dev mess · stall off
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
BIN="${OTA_BIN:-/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.52-dev.ota.esp32s3.bin}"
WANT_VER="${WANT_VER:-0.4.52-dev}"
LOG="$ROOT/ota-052.log"
PIDFILE="$ROOT/ota-052.pid"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

if [[ -f "$PIDFILE" ]]; then
  old="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    echo "bereits aktiv pid=$old" >&2
    exit 0
  fi
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT
[[ -f "$BIN" ]] || { echo "Bin fehlt: $BIN" >&2; exit 1; }
log "Bin $BIN ($(wc -c < "$BIN") B) → $ESP $WANT_VER"

status_json() { curl -fsS --connect-timeout 2 --max-time 4 "$ESP/api/status" 2>/dev/null || true; }

while true; do
  log "Warte auf $ESP_HOST … (Auto WLAN)"
  while true; do
    body="$(status_json)"
    [[ -n "$body" ]] && break
    sleep 2
  done
  echo "$body" > "$ROOT/status-before-ota.json"
  ver="$(python3 -c 'import json;d=json.load(open("'"$ROOT"'/status-before-ota.json"));print(d.get("version")or"")')"
  log "ONLINE fw=$ver"
  if [[ "$ver" != *"$WANT_VER"* ]]; then
    log "OTA $WANT_VER (aktuell $ver)…"
    curl -fsS --max-time 5 -X POST "$ESP/api/lab/stop" -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1 || true
    code="$(curl -sS --max-time 180 -o "$ROOT/ota-body.txt" -w '%{http_code}' \
      -F "firmware=@${BIN};filename=pidrive.${WANT_VER}.ota.esp32s3.bin" \
      "$ESP/ota-upload" || echo fail)"
    log "OTA HTTP $code body=$(head -c 60 "$ROOT/ota-body.txt" 2>/dev/null || true)"
    [[ "$code" == "200" ]] || { sleep 5; continue; }
    sleep 12
  else
    log "bereits $ver — skip flash"
  fi

  ok=0
  for i in $(seq 1 60); do
    body="$(status_json)"
    if [[ -z "$body" ]]; then sleep 2; continue; fi
    echo "$body" > "$ROOT/status-after-ota.json"
    curl -fsS --max-time 8 -X POST "$ESP/api/config" -H 'Content-Type: application/json' \
      -d '{"stallEnable":false}' >/dev/null 2>&1 || true
    sleep 1
    body="$(status_json)"
    [[ -n "$body" ]] || { sleep 2; continue; }
    echo "$body" > "$ROOT/status-final.json"
    if python3 - "$ROOT/status-final.json" "$WANT_VER" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
m=d.get("msc") or {}
ver=str(d.get("version") or "")
stall=bool((m.get("stall") or {}).get("enable"))
want=sys.argv[2]
print(f"AFTER fw={ver} stall={stall} otg={d.get('otgUp')} reset={d.get('resetReason')}")
sys.exit(0 if (want in ver and not stall) else 5)
PY
    then
      ok=1
      break
    fi
    sleep 2
  done

  if [[ "$ok" == "1" ]]; then
    mess="$(curl -fsS --max-time 4 "$ESP/api/lab/mess" 2>/dev/null || true)"
    echo "$mess" > "$ROOT/mess-health.json"
    log "GATE PASS — Capture bereit (OPERATOR.txt)"
    python3 -c 'import json;d=json.load(open("'"$ROOT"'/mess-health.json"));print("cmdCapture",d.get("cmdCapture"),"build",(d.get("mess")or{}).get("build"))' 2>/dev/null | tee -a "$LOG" || true
    exit 0
  fi
  log "Verify noch nicht grün — retry"
  sleep 5
done
