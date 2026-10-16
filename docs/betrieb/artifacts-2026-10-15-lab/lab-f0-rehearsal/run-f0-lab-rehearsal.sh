#!/usr/bin/env bash
# Overnight Lab F0-Rehearsal: Identity-Isolation B1–B3 auf Debian-Host (kein NBT).
# Beweist Tooling/Isolation für Feld-F0 — nicht Cache/P am Fahrzeug.
#
#   ./run-f0-lab-rehearsal.sh           # ein Durchlauf B0+B1+B2+B3
#   ./run-f0-lab-rehearsal.sh --loop 6  # 6 Zyklen über Nacht
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$ROOT/../../../.." && pwd)"
ESP="${ESP:-http://192.168.178.88}"
SG="${SG:-/dev/sg0}"
DEV="${DEV:-/dev/sda}"
LOOPS=1
[[ "${1:-}" == "--loop" ]] && LOOPS="${2:-6}"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$ROOT/run-$STAMP"
mkdir -p "$OUT"
LOG="$OUT/rehearsal.log"
exec > >(tee -a "$LOG") 2>&1

echo "== F0 Lab-Rehearsal $STAMP ESP=$ESP loops=$LOOPS =="
curl -fsS --max-time 5 -X POST "$ESP/api/config" -H 'Content-Type: application/json' \
  -d '{"stallEnable":false}' >/dev/null
curl -fsS --max-time 5 "$ESP/api/status" > "$OUT/status-start.json"
python3 -c 'import json;d=json.load(open("'"$OUT"'/status-start.json"));m=d.get("msc")or{};print("FW",d.get("version"),"serial",m.get("usbSerial"),"stall",(m.get("stall")or{}).get("enable"))'

cd "$PROJ"
python3 tools/lab_d_campaign.py --self-test

pass_n=0
fail_n=0
for loop in $(seq 1 "$LOOPS"); do
  LDIR="$OUT/loop-$loop"
  mkdir -p "$LDIR"
  echo "== loop $loop/$LOOPS =="

  # B0: control status snapshot (no identity change)
  curl -fsS --max-time 5 "$ESP/api/status" > "$LDIR/b0-status.json"
  echo "B0 control snapshot OK"

  for dim in serial label volume-id; do
    echo "-- identity $dim --"
    if python3 tools/lab_d_campaign.py identity \
      --esp "$ESP" --dimension "$dim" --device "$DEV" \
      --out "$LDIR/identity-$dim"; then
      echo "PASS $dim"
      pass_n=$((pass_n + 1))
    else
      echo "FAIL $dim"
      fail_n=$((fail_n + 1))
      # remount recover
      curl -fsS --max-time 8 -X POST "$ESP/api/lab/remount" \
        -H 'Content-Type: application/json' -d '{"keepIdentity":true}' >/dev/null || true
      sleep 2
    fi
    sleep 1
  done
done

python3 - <<PY
import json
from pathlib import Path
out = Path("$OUT")
rows = []
for p in sorted(out.glob("loop-*/identity-*/IDENTITY-REPORT.json")):
    r = json.loads(p.read_text())
    rows.append({
        "path": str(p.relative_to(out)),
        "dimension": r.get("dimension"),
        "pass": r.get("pass"),
        "changed": r.get("changed_fields"),
        "expected": r.get("expected_changed_fields"),
        "one_dimension_only": r.get("one_dimension_only"),
        "device_matches_status": r.get("device_matches_status"),
    })
summary = {
    "loops": int("$LOOPS"),
    "pass_n": int("$pass_n"),
    "fail_n": int("$fail_n"),
    "all_pass": int("$fail_n") == 0 and int("$pass_n") > 0,
    "rows": rows,
}
(out / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
print("OUT", out)
raise SystemExit(0 if summary["all_pass"] else 1)
PY
