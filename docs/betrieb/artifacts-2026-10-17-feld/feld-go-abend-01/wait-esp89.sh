#!/usr/bin/env bash
# Wait until Feld-ESP .89 answers /api/status, dump snapshot, print GO hint.
set -euo pipefail
ESP="${ESP_HOST:-192.168.178.89}"
OUT="${1:-$HOME/feld-go-abend-01/out}"
mkdir -p "$OUT"
echo "[$(date +%H:%M:%S)] warte auf http://$ESP/api/status …"
while true; do
  body=$(curl -fsS --connect-timeout 2 --max-time 4 "http://$ESP/api/status" 2>/dev/null || true)
  if [[ -n "$body" ]]; then
    ts=$(date +%Y%m%dT%H%M%S)
    echo "$body" > "$OUT/status-online-$ts.json"
    python3 - <<PY
import json
d=json.load(open("$OUT/status-online-$ts.json"))
m=d.get("msc") or {}
print("ONLINE", d.get("version"), "reset", d.get("resetReason"),
      "otg", d.get("otgUp"), "vol", m.get("bpbVolumeId"), "serial", m.get("usbSerial"),
      "uptime", d.get("uptime"), "rssi", d.get("wifiRssi"))
PY
    echo "→ GO.md lesen; zuerst M20 Repro, dann optional M24"
    echo "  python3 ~/feld-go-abend-01/tools/feld_status_poll.py --esp http://$ESP --out $OUT/m20-poll.jsonl --interval 0.7 --seconds 90 --print"
    exit 0
  fi
  sleep 2
done
