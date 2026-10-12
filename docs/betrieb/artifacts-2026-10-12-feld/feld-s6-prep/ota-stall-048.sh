#!/usr/bin/env bash
# OTA 0.4.48-dev Stall-Build auf Feld-.89 — NUR mit explizitem Operator-Go.
set -euo pipefail
ESP_HOST="${ESP_HOST:-192.168.178.89}"
ESP="http://$ESP_HOST"
ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="${OTA_BIN:-}"
if [[ -z "$BIN" ]]; then
  for cand in \
    "$ROOT/dist/pidrive.0.4.48-dev.ota.esp32s3.bin" \
    /home/pidrive/dist/pidrive.0.4.48-dev.ota.esp32s3.bin \
    /home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.48-dev.ota.esp32s3.bin; do
    [[ -f "$cand" ]] && BIN="$cand" && break
  done
fi
BIN="${BIN:?OTA-Bin nicht gefunden (OTA_BIN=… oder dist/ neben Prep syncen)}"

echo "WARN: flasht $BIN → $ESP"
echo "Soll: version=0.4.48-dev, stallEnable=false nach Boot"
if [[ "${I_MEAN_IT:-}" != "1" ]]; then
  echo "Abbruch: setze I_MEAN_IT=1 zum Flashen (Freeze-Schutz)." >&2
  exit 2
fi

sha256sum "$BIN"
curl -fsS --max-time 180 -F "firmware=@$BIN" "$ESP/ota-upload"
echo
echo "warte auf Reboot…"
sleep 18
for i in $(seq 1 20); do
  if curl -s -m 3 "$ESP/api/status" >/tmp/s6-ota-status.json 2>/dev/null; then
    python3 -c 'import json;d=json.load(open("/tmp/s6-ota-status.json"));m=d.get("msc")or{};s=m.get("stall")or{};print("version",d.get("version"));print("stall.enable",s.get("enable"));print("uptime",d.get("uptime"))'
    break
  fi
  sleep 3
done
# Defaults erzwingen (NVS könnte Stall von Lab-Tests haben — Feld sollte aus sein)
curl -s -X POST "$ESP/api/config" -H 'Content-Type: application/json' \
  -d '{"stallEnable":false}' | python3 -c 'import json,sys;c=json.load(sys.stdin).get("config")or{};print("config.stallEnable",c.get("stallEnable"))'
bash "$ROOT/s6-check.sh" post-ota
