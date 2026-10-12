#!/usr/bin/env bash
# Warte auf Auto-Pi und syncen s5-Prep + Bridge. Safe to re-run.
set -euo pipefail
PI="${PI:-pidrive@192.168.178.105}"
ESP89="${ESP89:-192.168.178.89}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$ROOT/../../../../.." && pwd)"
TAR="$ROOT/../SYNC-TO-PI-S5.tgz"
BRIDGE_SRC="${BRIDGE_SRC:-/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py}"
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

# wait until ssh works
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

"${SSH[@]}" "$PI" 'mkdir -p ~/pidrive ~/dist'
"${SCP[@]}" "$TAR" "$PI:/tmp/SYNC-TO-PI-S5.tgz"
"${SSH[@]}" "$PI" 'tar xzf /tmp/SYNC-TO-PI-S5.tgz -C ~/pidrive && chmod +x ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep/*.sh'
if [[ -f "$BRIDGE_SRC" ]]; then
  "${SCP[@]}" "$BRIDGE_SRC" "$PI:/home/pidrive/pump_bridge.py"
  "${SSH[@]}" "$PI" 'grep -q name-override-file /home/pidrive/pump_bridge.py && echo bridge_override_OK'
fi
# optional git pull if repo exists
"${SSH[@]}" "$PI" 'cd ~/pidrive && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git pull --ff-only || echo "no-git-or-pull-skip"' | tee -a "$LOG"

echo "$(date -Is) sync done" | tee -a "$LOG"
if ping -c1 -W2 "$ESP89" >/dev/null 2>&1; then
  curl -s -m 4 "http://$ESP89/api/status" | python3 -c 'import json,sys;d=json.load(sys.stdin);m=d.get("msc")or{};print("ESP",d.get("version"),"up",d.get("uptime"),"serial",m.get("usbSerial"),"plugged",m.get("plugged"))' | tee -a "$LOG"
  bash "$ROOT/s5-check.sh" before | tee -a "$LOG"
else
  echo "ESP .89 still down — check after power" | tee -a "$LOG"
fi
echo "READY: ssh $PI → cd ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep && ./run-s5.sh 1800"
