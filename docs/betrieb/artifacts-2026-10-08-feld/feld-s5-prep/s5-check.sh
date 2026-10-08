#!/usr/bin/env bash
# R28-Gültigkeitscheck: playingUid, Serial, Uptime, Reboot?
set -euo pipefail
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
LABEL="${1:-check}"
curl -s -m 4 "$ESP/api/status" | python3 -c '
import json,sys,time
label=sys.argv[1]
d=json.load(sys.stdin)
m=d.get("msc") or {}
s=m.get("stream") or {}
print(json.dumps({
  "t": time.strftime("%H:%M:%S"),
  "label": label,
  "version": d.get("version"),
  "uptime": d.get("uptime"),
  "serial": m.get("usbSerial"),
  "plugged": m.get("plugged"),
  "otgUp": d.get("otgUp"),
  "playingUid": d.get("playingUid"),
  "playingName": d.get("playingName"),
  "stream_active": s.get("active"),
  "absEnd": s.get("absEnd"),
  "underruns": s.get("underruns"),
  "hostAbs": s.get("hostAbsCursor"),
  "ring": s.get("size"),
}, ensure_ascii=False))
' "$LABEL"
