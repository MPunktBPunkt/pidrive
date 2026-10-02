#!/usr/bin/env bash
# Prepare for Auto ESP coming online (.89). Safe to re-run.
set -euo pipefail
ESP89="${ESP89:-http://192.168.178.89}"
PI="${PI:-pidrive@192.168.178.105}"
BIN_SRC="${BIN_SRC:-/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.36-dev.ota.esp32s3.bin}"
HUB_FW="${HUB_FW:-/home/martin/projects/esphub/iobroker.esp-hub/firmware/pidrive.0.4.36-dev.ota.esp32s3.bin}"

echo "=== PiDrive homecoming prep ==="

if [[ -f "$BIN_SRC" ]]; then
  scp -o BatchMode=yes "$BIN_SRC" "$PI:/home/pidrive/dist/$(basename "$BIN_SRC")"
  echo "Pi dist: $(basename "$BIN_SRC") OK"
else
  echo "WARN: missing $BIN_SRC"
fi
if [[ -f "$HUB_FW" ]]; then
  echo "Hub firmware copy: $(basename "$HUB_FW") ($(stat -c%s "$HUB_FW") B)"
else
  echo "WARN: hub firmware missing at $HUB_FW"
fi

scp -o BatchMode=yes \
  /home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py \
  "$PI:/home/pidrive/pump_bridge.py"
ssh -o BatchMode=yes "$PI" 'grep -q RAPID_SWITCH_S /home/pidrive/pump_bridge.py && echo bridge_guard_fix_OK'

echo "Waiting for Auto ESP $ESP89 … (Ctrl-C to abort)"
FOUND=0
for _ in $(seq 1 180); do
  if curl -sS --connect-timeout 2 "$ESP89/api/status" >/tmp/esp89_prep_status.json 2>/dev/null; then
    python3 - <<'PY'
import json
d=json.load(open("/tmp/esp89_prep_status.json"))
print(f"ONLINE fw={d.get('version')} serial={d.get('msc',{}).get('usbSerial')} up={d.get('uptime')} rssi={d.get('wifiRssi')}")
PY
    FOUND=1
    break
  fi
  printf "."
  sleep 5
done
echo
if [[ "$FOUND" != "1" ]]; then
  echo "ESP .89 not seen yet — re-run: $0"
  exit 2
fi

NEED_OTA=$(python3 - <<'PY'
import json
d=json.load(open("/tmp/esp89_prep_status.json"))
v=str(d.get("version") or "")
print("no" if "0.4.36" in v else "yes")
PY
)
if [[ "$NEED_OTA" == "yes" ]]; then
  echo "OTA → 0.4.36-dev …"
  ssh -o BatchMode=yes "$PI" \
    "curl -sS -F file=@/home/pidrive/dist/pidrive.0.4.36-dev.ota.esp32s3.bin ${ESP89}/ota-upload"
  echo
  sleep 15
  curl -sS --connect-timeout 5 "$ESP89/api/status" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("post-ota",d.get("version"),d.get("uptime"))'
else
  echo "FW already 0.4.36 — skip OTA"
fi

echo "Switching pump_bridge → 192.168.178.89"
ssh -o BatchMode=yes "$PI" bash <<'REMOTE'
set -e
PIDS=$(ps -eo pid,args | awk '/pump_bridge\.py/ && !/awk/ {print $1}')
if [[ -n "$PIDS" ]]; then kill $PIDS || true; sleep 1; fi
LOG=/tmp/pump_bridge_manual.log
echo "$(date -Is) homecoming → .89" >>"$LOG"
nohup /usr/bin/python3 -u /home/pidrive/pump_bridge.py \
  --transport tcp --host 192.168.178.89 --tcp-port 9090 \
  --interval 0.5 --bitrate 48k >>"$LOG" 2>&1 </dev/null &
echo $! > /tmp/pump_bridge_manual.pid
sleep 3
ps -eo pid,args | awk '/pump_bridge\.py/ && !/awk/'
tail -12 "$LOG" | grep -v menu_set || true
REMOTE

curl -sS "$ESP89/api/status" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("pumpTcp",d.get("pumpTcpUp"),d.get("pumpTcpPeer"),"fw",d.get("version"))'
echo
echo "Ready for B7 (≥150s, FW 0.4.36 — no FW change):"
echo "  python3 tools/feld_150s_slot_pass.py --uid fav1 --note \"HH:MM OTG PDxxxx\""
echo "  # then optional switches in same mount; fill EAR stopwatch"
echo "Legacy 60s tool still available: tools/feld_60s_live_pass.py"
echo "Then: git add docs/betrieb/artifacts-\$(date +%Y-%m-%d)-b7/ + §11 update"
