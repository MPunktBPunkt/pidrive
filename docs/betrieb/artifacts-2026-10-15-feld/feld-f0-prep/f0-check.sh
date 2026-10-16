#!/usr/bin/env bash
# Identity + Stall Freeze Check für F0
#   ./f0-check.sh [label]
#   ./f0-check.sh isolate <serial|label|volume-id> <before.json> <after.json>
set -euo pipefail
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "isolate" ]]; then
  DIM="${2:?dim}"
  BEFORE="${3:?before.json}"
  AFTER="${4:?after.json}"
  exec "$ROOT/f0-identity.sh" verify "$BEFORE" "$AFTER" "$DIM"
fi

LABEL="${1:-check}"
curl -s -m 4 "$ESP/api/status" | python3 -c '
import json,sys,time
label=sys.argv[1]
d=json.load(sys.stdin)
m=d.get("msc") or {}
s=m.get("stream") or {}
stall=m.get("stall") or {}
ver=str(d.get("version") or "")
stall_on=bool(stall.get("enable"))
print(json.dumps({
  "t": time.strftime("%H:%M:%S"),
  "label": label,
  "version": ver,
  "fw_ok_hint": ("0.4.51" in ver) or ver.startswith("0.4.5"),
  "uptime": d.get("uptime"),
  "usbSerial": m.get("usbSerial"),
  "productRevision": m.get("productRevision"),
  "bpbVolumeId": m.get("bpbVolumeId"),
  "bpbLabel": m.get("bpbLabel"),
  "rootLabel": m.get("rootLabel"),
  "volumeLabel": m.get("volumeLabel"),
  "plugged": m.get("plugged"),
  "otgUp": d.get("otgUp"),
  "mscReady": d.get("mscReady"),
  "playingUid": d.get("playingUid"),
  "playingName": d.get("playingName"),
  "stream_active": s.get("active"),
  "absEnd": s.get("absEnd"),
  "stall_enable": stall_on,
  "stall_freeze_ok": (not stall_on),
  "klasse_hint": "A?" if d.get("otgUp") and m.get("plugged") else "check-otg",
}, ensure_ascii=False))
if stall_on:
    print("ABORT: stall_enable=true — Freeze verletzt", file=sys.stderr)
    sys.exit(2)
' "$LABEL"
