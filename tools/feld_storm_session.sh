#!/usr/bin/env bash
# Storm M30 capture harness: poll v2 + MessCapture (--storm) + M31 Q/S + M32 band.
# Lab: soft usb_cycle. Field: --sit none then plug OTG after ARMED.
set -euo pipefail

ESP="${ESP:-http://192.168.178.88}"
OUT=""
UART=""
SIT="usb_cycle"
SECONDS_POLL=90
ARM_TIMEOUT=0   # 0 → match --seconds
INTERVAL=0.5
MARK="storm_m30"

usage() {
  cat <<EOF
Usage: $0 --out DIR [--esp URL] [--uart /dev/ttyACM0] [--sit NAME|none]
          [--seconds N] [--arm-timeout N] [--mark NAME]

M30: poll schema v2 + MessCapture arm --storm (timeout-only stop)
M31: feld_qs_classify → qs.json
M32: mess_band_report → band.json

Default --sit usb_cycle (lab). Field: --sit none then plug OTG after "ARMED".
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --esp) ESP="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --uart) UART="$2"; shift 2 ;;
    --sit) SIT="$2"; shift 2 ;;
    --seconds) SECONDS_POLL="$2"; shift 2 ;;
    --arm-timeout) ARM_TIMEOUT="$2"; shift 2 ;;
    --mark) MARK="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$OUT" ]] || { echo "--out required" >&2; exit 2; }

if [[ "$ARM_TIMEOUT" -eq 0 ]]; then
  ARM_TIMEOUT="$SECONDS_POLL"
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT" "$OUT/uart"
cd "$ROOT"

{
  echo "# OPERATOR — Storm M30"
  echo "start_wall=$(date -Iseconds)"
  echo "esp=$ESP"
  echo "sit=$SIT"
  echo "mark=$MARK"
  echo "uart=${UART:-none}"
  echo "seconds=$SECONDS_POLL"
  echo "arm_timeout=$ARM_TIMEOUT"
  echo "storm_arm=1"
  echo ""
  echo "After ARMED: physical OTG / tip as planned. Do not replug-storm after first tone."
} >"$OUT/OPERATOR.md"

echo "== status check $ESP =="
curl -sS --connect-timeout 3 "$ESP/api/status" >"$OUT/status-start.json"
python3 - <<PY
import json
d=json.load(open("$OUT/status-start.json"))
m=d.get("msc") or {}
print(f"fw={d.get('version')} serial={m.get('usbSerial')} pref={m.get('prefetchHits')} guess={m.get('playGuessCount')} mess={(d.get('mess') or {}).get('enabled')}")
PY

POLL_PID=""
UART_PID=""
finalize() {
  echo "== finalize M31/M32 =="
  if [[ -f "$OUT/poll.jsonl" ]]; then
    python3 tools/feld_qs_classify.py --poll "$OUT/poll.jsonl" --out "$OUT/qs.json" || true
  fi
  # Prefer full dump; fall back to arm.json commands
  if [[ -f "$OUT/mess-cmds.json" ]]; then
    python3 tools/mess_band_report.py "$OUT/mess-cmds.json" -o "$OUT/band.json" || true
  elif [[ -f "$OUT/arm.json" ]]; then
    python3 tools/mess_band_report.py "$OUT/arm.json" -o "$OUT/band.json" || true
  fi
  python3 - <<PY
import json
from pathlib import Path
out = Path("$OUT")
summary = {"out": str(out)}
for name in ("qs.json", "band.json"):
    p = out / name
    if not p.exists():
        continue
    d = json.loads(p.read_text())
    if name == "qs.json":
        summary["qs_counts"] = d.get("label_counts")
        summary["guess_events"] = len(d.get("guess_events") or [])
        summary["invariant_ok"] = d.get("invariant_ok")
        summary["schema_note"] = (d.get("gaps") or {}).get("schema_note")
    else:
        summary["band"] = {
            "read10_n": d.get("read10_n"),
            "file_body_share": d.get("file_body_share"),
            "storm_hint": d.get("storm_hint"),
            "dominant_band": d.get("dominant_band"),
            "bands": d.get("bands"),
        }
(out / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
}

cleanup() {
  local ec=$?
  [[ -n "${POLL_PID:-}" ]] && kill "$POLL_PID" 2>/dev/null || true
  [[ -n "${UART_PID:-}" ]] && kill "$UART_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  curl -sS --connect-timeout 3 "$ESP/api/status" >"$OUT/status-end.json" 2>/dev/null || true
  # dump ring even if arm already stopped
  python3 tools/mess_hu_capture.py --esp "$ESP" dump -o "$OUT/mess-cmds.json" 2>/dev/null || true
  finalize || true
  echo "end_wall=$(date -Iseconds)" >>"$OUT/OPERATOR.md"
  echo "cleanup exit=$ec → $OUT"
}
trap cleanup EXIT

echo "== poll v2 → $OUT/poll.jsonl (${SECONDS_POLL}s @ ${INTERVAL}s) =="
python3 tools/feld_status_poll.py --esp "$ESP" \
  --out "$OUT/poll.jsonl" --interval "$INTERVAL" --seconds "$SECONDS_POLL" \
  --run-id "$(basename "$OUT")" --print \
  >"$OUT/poll.print.log" 2>&1 &
POLL_PID=$!

if [[ -n "$UART" ]]; then
  echo "== uart $UART =="
  python3 tools/lab_uart_reset_log.py --port "$UART" --esp "$ESP" \
    --seconds "$SECONDS_POLL" --out "$OUT/uart" \
    >"$OUT/uart/run.log" 2>&1 &
  UART_PID=$!
else
  echo "uart=skip (pass --uart /dev/ttyACM0 on field host)" | tee "$OUT/uart/SKIPPED.txt"
fi

ARM_ARGS=(--esp "$ESP" arm --storm --timeout "$ARM_TIMEOUT" --mark "$MARK" -o "$OUT/arm.json")
if [[ "$SIT" != "none" ]]; then
  ARM_ARGS+=(--sit "$SIT")
  echo "== MessCapture arm --storm + sit $SIT (timeout=${ARM_TIMEOUT}s) =="
else
  echo "== MessCapture ARMED --storm — plug OTG now (timeout=${ARM_TIMEOUT}s) =="
  echo "ARMED_waiting_otg wall=$(date -Iseconds)" >>"$OUT/OPERATOR.md"
fi

python3 tools/mess_hu_capture.py "${ARM_ARGS[@]}" | tee "$OUT/arm.print.log"

wait "$POLL_PID" 2>/dev/null || true
POLL_PID=""
[[ -n "${UART_PID:-}" ]] && wait "$UART_PID" 2>/dev/null || true
UART_PID=""

echo "DONE $OUT"
