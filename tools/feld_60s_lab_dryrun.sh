#!/usr/bin/env bash
# Lab dry-run of 60s capture tool with parallel paced MSC reads.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ESP="${ESP:-http://192.168.178.88}"
UID_LABEL="${1:-fav0}"
SECONDS_N="${SECONDS_N:-60}"
PROXMOX="${PROXMOX:-root@192.168.178.108}"
PI="${PI:-pidrive@192.168.178.105}"

echo "== lab dry-run uid=$UID_LABEL ${SECONDS_N}s =="

ssh -o BatchMode=yes "$PI" bash <<'REMOTE'
set -e
HOST=192.168.178.88
if ! ps -eo args | awk '/pump_bridge\.py/ && !/awk/' | grep -q "$HOST"; then
  PIDS=$(ps -eo pid,args | awk '/pump_bridge\.py/ && !/awk/ {print $1}')
  if [[ -n "$PIDS" ]]; then kill $PIDS || true; sleep 1; fi
  nohup /usr/bin/python3 -u /home/pidrive/pump_bridge.py \
    --transport tcp --host $HOST --tcp-port 9090 --interval 0.5 --bitrate 48k \
    >>/tmp/pump_bridge_lab88.log 2>&1 </dev/null &
  sleep 2
fi
ps -eo pid,args | awk '/pump_bridge\.py/ && !/awk/'
REMOTE

curl -sS -X POST "$ESP/api/lab/stop" >/dev/null || true
sleep 1
curl -sS -X POST "$ESP/api/lab/play" -H 'Content-Type: application/json' -d "{\"uid\":\"$UID_LABEL\"}"
echo
python3 - <<PY
import json, time, urllib.request, sys
esp, uid = "$ESP", "$UID_LABEL"
t0 = time.time()
while time.time() - t0 < 35:
    d = json.load(urllib.request.urlopen(esp + "/api/status", timeout=5))
    s = d.get("stream") or (d.get("msc") or {}).get("stream") or {}
    print(f"arm {s.get('uid')} active={s.get('active')} size={s.get('size')}", flush=True)
    if s.get("active") and s.get("uid") == uid and int(s.get("size") or 0) > 0:
        sys.exit(0)
    time.sleep(0.5)
raise SystemExit("arm timeout")
PY

scp -o BatchMode=yes "$ROOT/tools/feld_lab_paced_bg.py" "$PROXMOX:/tmp/feld_lab_paced_bg.py" >/dev/null
ssh -o BatchMode=yes "$PROXMOX" \
  "nohup python3 /tmp/feld_lab_paced_bg.py --esp $ESP --uid $UID_LABEL --seconds $SECONDS_N >/tmp/lab60_paced.log 2>&1 & echo paced_pid=\$!"

python3 "$ROOT/tools/feld_60s_live_pass.py" \
  --uid "$UID_LABEL" \
  --esp "$ESP" \
  --pi "$PI" \
  --seconds "$SECONDS_N" \
  --poll 2 \
  --note "lab-dryrun paced-msc ${SECONDS_N}s" \
  --auto-start

echo "== paced log (tail) =="
ssh -o BatchMode=yes "$PROXMOX" "tail -5 /tmp/lab60_paced.log || true"
echo "== artifacts under docs/betrieb/artifacts-$(date +%Y-%m-%d)-60s/ =="
ls -la "$ROOT/docs/betrieb/artifacts-$(date +%Y-%m-%d)-60s/" 2>/dev/null || true
