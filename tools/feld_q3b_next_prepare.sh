#!/usr/bin/env bash
# Prepare next field Q3b run on Auto ESP .89.
# - OTA 0.4.45-dev (seed wins over live in body)
# - truncate traces on .105
# - arm Seed B on fav0 fromOff=348160
# - GO gate: seed must stay active after settle (catches 1738 reboot-after-seed)
# - write EAR + status snapshots
set -euo pipefail
ESP="${ESP:-http://192.168.178.89}"
PI="${PI:-pidrive@192.168.178.105}"
BIN="${BIN:-/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.45-dev.ota.esp32s3.bin}"
SETTLE_S="${SETTLE_S:-8}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP=$(date +%H%M)
OUT="$ROOT/docs/betrieb/artifacts-$(date +%Y-%m-%d)-feld/feld-q3b-next-$STAMP"
mkdir -p "$OUT"

echo "== status pre =="
curl -sS -m5 "$ESP/api/status" | tee "$OUT/status-00-pre.json" | python3 -c \
  'import sys,json;d=json.load(sys.stdin);m=d["msc"];print(d["version"],m.get("usbSerial"),m.get("plugged"),m.get("bodySeed"))'

if [[ ! -f "$BIN" ]]; then
  echo "missing OTA bin: $BIN" >&2
  exit 1
fi

ver=$(python3 -c 'import json;print(json.load(open("'"$OUT"'/status-00-pre.json")).get("version",""))')
if [[ "$ver" != "0.4.45-dev" ]]; then
  echo "== OTA 0.4.45-dev =="
  curl -sS -m180 -F "firmware=@$BIN" "$ESP/ota-upload"
  echo
  for i in $(seq 1 30); do
    v=$(curl -sS -m3 "$ESP/api/status" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true)
    echo "try $i: $v"
    [[ "$v" == "0.4.45-dev" ]] && break
    sleep 2
  done
fi

curl -sS -m5 "$ESP/api/status" > "$OUT/status-01-fw.json"

echo "== truncate traces on $PI =="
ssh -o BatchMode=yes -o ConnectTimeout=5 "$PI" 'bash -s' <<'REMOTE'
: > /tmp/pidrive_msc_reads.jsonl
: > /tmp/pidrive_msc_diag.jsonl
python3 - <<'PY'
import json,time
from pathlib import Path
Path("/tmp/pidrive_msc_lock.jsonl").open("a").write(
    json.dumps({"ts":time.time(),"mark":"FELD_Q3B_NEXT_START","fw":"0.4.45-dev"})+"\n")
print("reads", Path("/tmp/pidrive_msc_reads.jsonl").stat().st_size)
print("diag", Path("/tmp/pidrive_msc_diag.jsonl").stat().st_size)
PY
REMOTE

echo "== lab/stop + seed B (NO remount) =="
curl -sS -m5 -X POST "$ESP/api/lab/stop" -H 'Content-Type: application/json' -d '{}' || true
sleep 0.3
curl -sS -m8 -X POST "$ESP/api/lab/body_seed" -H 'Content-Type: application/json' \
  -d '{"slot":0,"tag":"B","fromOff":348160}' | tee "$OUT/seed-B.json"
echo

python3 - <<PY
import json, urllib.request, hashlib, re, sys, time
from pathlib import Path
esp="$ESP"; out=Path("$OUT"); settle=int("$SETTLE_S")

def get():
    return json.loads(urllib.request.urlopen(f"{esp}/api/status", timeout=5).read())

def uptime_s(text):
    if not text: return None
    s=0
    for n,u in re.findall(r"(\\d+)\\s*(h|min|s)", text):
        n=int(n); s += n*(3600 if u=="h" else 60 if u=="min" else 1)
    return s

raw=urllib.request.urlopen(f"{esp}/api/lab/body_read?slot=0&off=348160&n=8192", timeout=8).read()
(out/"softap_B_lba761.bin").write_bytes(raw)
ok=raw[:5]==b"Q3B1B" and len(raw)==8192
print("oracleA", ok, "sha16", hashlib.sha256(raw).hexdigest()[:16])
st=get()
(out/"status-02-seeded.json").write_text(json.dumps(st, indent=2))
bs=(st.get("msc") or {}).get("bodySeed") or {}
print("seeded", st["version"], st["msc"].get("usbSerial"), "uptime", st.get("uptime"), "seed", bs)
if not bs.get("active"):
    print("GATE FAIL: seed not active immediately after arm", file=sys.stderr)
    sys.exit(2)

up0=uptime_s(st.get("uptime"))
print(f"== settle {settle}s (reboot/seed-death gate) ==")
time.sleep(settle)
st=get()
(out/"status-03-go.json").write_text(json.dumps(st, indent=2))
bs=(st.get("msc") or {}).get("bodySeed") or {}
up1=uptime_s(st.get("uptime"))
print("GO", st.get("uptime"), "seed", bs, "cold", st["msc"].get("coldBodyBurstCount"))
if not bs.get("active"):
    print("GATE FAIL: seed inactive after settle — likely reboot (see 1738)", file=sys.stderr)
    sys.exit(3)
if up0 is not None and up1 is not None and up1 + 15 < up0:
    print(f"GATE FAIL: uptime collapsed {up0}s -> {up1}s", file=sys.stderr)
    sys.exit(3)
print("GATE PASS: seed still active after settle")
PY

cat > "$OUT/EAR.txt" <<EOF
FELD Q3b NEXT — prepared $(date -Iseconds)
FW target: 0.4.45-dev (seed WINS over live in body; bodySeed.bytesServed)
Prefill: fav0 tag=B fromOff=348160 (LBA 761+)
GO gate: seed active after ${SETTLE_S}s settle (status-03-go)
NO remount after seed. NO RST after seed.

OPERATOR:
1) Film UI-Timer + LED
2) Play short track Bayern or BOB
3) Auto-Next → Rock (~87s / LED burst)
4) Note: audible music NOT expected (seed≠MP3)
5) Report: clock of burst/LED, any noise/glitch, then "Ende"
6) Success = bytesServed rises during burst + HU body LBAs in trace

DO NOT: RST, unplug USB, remount, menu rewrite (kills RAM seed)
Watchdog (Haus):
  python3 tools/feld_q3b_seed_watchdog.py --esp $ESP --out $OUT --minutes 4
Artifacts: $OUT
EOF

echo
cat "$OUT/EAR.txt"
echo "OUT=$OUT"
echo "NEXT: python3 $ROOT/tools/feld_q3b_seed_watchdog.py --esp $ESP --out $OUT --minutes 4"
