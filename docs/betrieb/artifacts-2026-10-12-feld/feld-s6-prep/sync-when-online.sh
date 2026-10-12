#!/usr/bin/env bash
# Warte auf Auto-Pi und syncen s6-Prep + optional OTA-Bin + Bridge.
set -euo pipefail
PI="${PI:-pidrive@192.168.178.105}"
ESP89="${ESP89:-192.168.178.89}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$ROOT/../../../../.." && pwd)"
TAR="$ROOT/../SYNC-TO-PI-S6.tgz"
BRIDGE_SRC="${BRIDGE_SRC:-/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py}"
OTA_SRC="${OTA_SRC:-/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.48-dev.ota.esp32s3.bin}"
LOG="$ROOT/sync-online.log"

echo "$(date -Is) waiting for $PI …" | tee -a "$LOG"
for i in $(seq 1 360); do
  if ping -c1 -W1 192.168.178.105 >/dev/null 2>&1; then
    echo "$(date -Is) Pi ping OK (try $i)" | tee -a "$LOG"
    break
  fi
  sleep 5
  if [[ $i -eq 360 ]]; then
    echo "$(date -Is) TIMEOUT Pi" | tee -a "$LOG"
    exit 2
  fi
done

SSH=(ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
SCP=(scp -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)

for i in $(seq 1 60); do
  if "${SSH[@]}" "$PI" 'echo ssh_ok' >/dev/null 2>&1; then
    echo "$(date -Is) ssh OK" | tee -a "$LOG"
    break
  fi
  sleep 3
  if [[ $i -eq 60 ]]; then
    echo "$(date -Is) TIMEOUT ssh" | tee -a "$LOG"
    exit 3
  fi
done

"${SSH[@]}" "$PI" 'mkdir -p ~/pidrive ~/dist ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep/dist'
"${SCP[@]}" "$TAR" "$PI:/tmp/SYNC-TO-PI-S6.tgz"
"${SSH[@]}" "$PI" 'tar xzf /tmp/SYNC-TO-PI-S6.tgz -C ~/pidrive && chmod +x ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep/*.sh'
if [[ -f "$BRIDGE_SRC" ]]; then
  "${SCP[@]}" "$BRIDGE_SRC" "$PI:/home/pidrive/pump_bridge.py"
fi
if [[ -f "$OTA_SRC" ]]; then
  "${SCP[@]}" "$OTA_SRC" "$PI:/home/pidrive/dist/pidrive.0.4.48-dev.ota.esp32s3.bin"
  "${SCP[@]}" "$OTA_SRC" "$PI:~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep/dist/pidrive.0.4.48-dev.ota.esp32s3.bin"
  echo "$(date -Is) OTA 0.4.48 staged (NOT flashed)" | tee -a "$LOG"
fi
"${SSH[@]}" "$PI" 'cd ~/pidrive && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git pull --ff-only || echo "no-git-or-pull-skip"' | tee -a "$LOG"

echo "$(date -Is) sync done" | tee -a "$LOG"
if ping -c1 -W2 "$ESP89" >/dev/null 2>&1; then
  curl -s -m 4 "http://$ESP89/api/status" | python3 -c 'import json,sys;d=json.load(sys.stdin);m=d.get("msc")or{};print("ESP",d.get("version"),"up",d.get("uptime"),"serial",m.get("usbSerial"),"plugged",m.get("plugged"))' | tee -a "$LOG"
  bash "$ROOT/s6-check.sh" before | tee -a "$LOG"
else
  echo "ESP .89 still down — check after power" | tee -a "$LOG"
fi
echo "READY: ssh $PI → cd ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep && ./run-s6.sh q11 900"
echo "E7 OTA bleibt Freeze bis: I_MEAN_IT=1 ./ota-stall-048.sh"
