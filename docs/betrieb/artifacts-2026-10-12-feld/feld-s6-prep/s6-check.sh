#!/usr/bin/env bash
# Gültigkeitscheck: Serial/Uptime/Play + Stall-Felder (0.4.47+)
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
stall=m.get("stall") or {}
serial=m.get("usbSerial")
print(json.dumps({
  "t": time.strftime("%H:%M:%S"),
  "label": label,
  "version": d.get("version"),
  "uptime": d.get("uptime"),
  "serial": serial,
  "volumeLabel": m.get("volumeLabel"),
  "plugged": m.get("plugged"),
  "otgUp": d.get("otgUp"),
  "usbEnumerated": d.get("usbEnumerated"),
  "mscReady": d.get("mscReady"),
  "playingUid": d.get("playingUid"),
  "playingName": d.get("playingName"),
  "stream_active": s.get("active"),
  "absEnd": s.get("absEnd"),
  "ring": s.get("size"),
  "pumpTcpPeer": d.get("pumpTcpPeer"),
  "stall_enable": stall.get("enable"),
  "stall_maxMs": stall.get("maxMs"),
  "stall_retries": stall.get("retries"),
  "stall_timeouts": stall.get("timeouts"),
  "stall_cmds": stall.get("cmds"),
  "klasse_hint": "A?" if d.get("otgUp") and m.get("plugged") else "check-otg",
}, ensure_ascii=False))
' "$LABEL"
