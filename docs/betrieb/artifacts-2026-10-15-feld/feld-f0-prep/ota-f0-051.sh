#!/usr/bin/env bash
# F0 Pre-Gate: OTA 0.4.51-dev auf Auto-ESP .89, stallEnable=false.
# Usage:
#   ./ota-f0-051.sh              # warten → flashen → verify (Retry bei Post-OTA-Offline)
#   ./ota-f0-051.sh --once       # nur ein Versuch (kein Wait-/Retry-Loop)
#   ESP_HOST=192.168.178.89 ./ota-f0-051.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
ONCE=0
[[ "${1:-}" == "--once" ]] && ONCE=1

BIN_DEFAULT="/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.51-dev.ota.esp32s3.bin"
BIN="${OTA_BIN:-$BIN_DEFAULT}"
WANT_VER="${WANT_VER:-0.4.51-dev}"
LOG="$ROOT/ota-f0-051.log"
PIDFILE="$ROOT/ota-f0-051.pid"
VERIFY_TRIES="${VERIFY_TRIES:-90}"   # ~3 min @ 2s — Post-OTA oft lange offline
ROUND=0

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

if [[ -f "$PIDFILE" ]]; then
  old="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    echo "bereits aktiv pid=$old (PIDFILE $PIDFILE) — Abbruch" >&2
    exit 0
  fi
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

[[ -f "$BIN" ]] || { echo "Bin fehlt: $BIN" >&2; exit 1; }
log "Bin $BIN ($(wc -c < "$BIN") B)"
log "Ziel $ESP → $WANT_VER · stallEnable=false · verify_tries=$VERIFY_TRIES"

status_json() {
  curl -fsS --connect-timeout 2 --max-time 4 "$ESP/api/status" 2>/dev/null || true
}

new_outdir() {
  OUTDIR="$ROOT/ota-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$OUTDIR"
  log "OUTDIR $OUTDIR"
}

wait_online() {
  log "Warte auf $ESP_HOST … (Auto einschalten)"
  local i=0
  while true; do
    body="$(status_json)"
    if [[ -n "$body" ]]; then
      echo "$body" > "$OUTDIR/status-before.json"
      python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));m=d.get("msc")or{};print("ONLINE fw=%s serial=%s stall=%s"%(d.get("version")or d.get("fw"),m.get("usbSerial"),(m.get("stall")or{}).get("enable")))' \
        "$OUTDIR/status-before.json" | tee -a "$LOG"
      return 0
    fi
    i=$((i + 1))
    if (( i % 6 == 0 )); then log "noch offline ($i)…"; fi
    [[ "$ONCE" == "1" ]] && { log "offline (--once)"; exit 2; }
    sleep 2
  done
}

do_ota() {
  local ver
  ver="$(python3 -c 'import json;d=json.load(open("'"$OUTDIR"'/status-before.json"));print(d.get("version")or d.get("fw")or"")')"
  if [[ "$ver" == *"$WANT_VER"* ]]; then
    log "bereits $ver — OTA übersprungen"
    return 0
  fi
  log "OTA $WANT_VER (aktuell: $ver)…"
  curl -fsS --max-time 5 -X POST "$ESP/api/lab/stop" -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1 || true
  curl -fsS --max-time 5 -X POST "$ESP/api/session/stop" -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1 || true
  local code
  code="$(curl -sS --max-time 180 -o "$OUTDIR/ota-body.txt" -w '%{http_code}' \
    -F "firmware=@${BIN};filename=pidrive.${WANT_VER}.ota.esp32s3.bin" \
    "$ESP/ota-upload" || echo fail)"
  log "OTA HTTP $code body=$(head -c 80 "$OUTDIR/ota-body.txt" 2>/dev/null || true)"
  [[ "$code" == "200" ]] || { log "OTA FAIL"; return 3; }
  sleep 10
  return 0
}

verify() {
  local ok=0
  local i
  for i in $(seq 1 "$VERIFY_TRIES"); do
    body="$(status_json)"
    if [[ -n "$body" ]]; then
      echo "$body" > "$OUTDIR/status-after.json"
      python3 - <<PY | tee -a "$LOG"
import json
d=json.load(open("$OUTDIR/status-after.json"))
m=d.get("msc") or {}
ver=str(d.get("version") or d.get("fw") or "")
stall=(m.get("stall") or {}).get("enable")
print(f"AFTER fw={ver} serial={m.get('usbSerial')} stall={stall} otg={d.get('otgUp')}")
open("$OUTDIR/verify.env","w").write(f"VER={ver}\nSTALL={stall}\n")
PY
      ok=1
      break
    fi
    if (( i % 15 == 0 )); then log "verify noch offline ($i/$VERIFY_TRIES)…"; fi
    sleep 2
  done
  if [[ "$ok" != "1" ]]; then
    log "kein Status nach OTA (verify timeout)"
    return 4
  fi

  curl -fsS --max-time 8 -X POST "$ESP/api/config" -H 'Content-Type: application/json' \
    -d '{"stallEnable":false}' > "$OUTDIR/config-stall-off.json" 2>/dev/null || true
  sleep 1
  body="$(status_json)"
  if [[ -z "$body" ]]; then
    log "Status weg nach stall-off"
    return 4
  fi
  echo "$body" > "$OUTDIR/status-final.json"
  # Args must precede heredoc (otherwise bash treats the JSON path as a command).
  if python3 - "$OUTDIR/status-final.json" "$WANT_VER" <<'PY' | tee -a "$LOG"
import json,sys
d=json.load(open(sys.argv[1]))
m=d.get("msc") or {}
ver=str(d.get("version") or "")
stall=bool((m.get("stall") or {}).get("enable"))
want=sys.argv[2]
ok = (want in ver) and (not stall)
print(f"GATE fw_ok={want in ver} stall_off={not stall} → {'PASS' if ok else 'FAIL'}")
sys.exit(0 if ok else 5)
PY
  then
    return 0
  fi
  return 5
}

# Outer loop: Post-OTA oft HTTP 200 → reboot → Minuten offline (Nacht-Fail).
# Nächste Runde: wait → ggf. schon WANT_VER → skip flash → Gate.
while true; do
  ROUND=$((ROUND + 1))
  new_outdir
  log "Runde $ROUND"
  wait_online
  rc=0
  do_ota || rc=$?
  if [[ "$rc" != "0" ]]; then
    [[ "$ONCE" == "1" ]] && exit "$rc"
    log "OTA-Fehler rc=$rc — warte erneut…"
    sleep 5
    continue
  fi
  rc=0
  verify || rc=$?
  if [[ "$rc" == "0" ]]; then
    log "Fertig. Weiter: ANKUNFT.md / GO.md (F0 Smoke → B0…B3)"
    echo "OUT $OUTDIR"
    exit 0
  fi
  [[ "$ONCE" == "1" ]] && exit "$rc"
  log "Verify rc=$rc — Device bootet ggf. noch; nächste Runde ohne erzwungenen Reflash"
  sleep 5
done
