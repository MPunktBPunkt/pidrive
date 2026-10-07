#!/usr/bin/env bash
# Isolated follow-ups: clean C5, C4-GW, C6 G7 (each after soft-RST when needed).
set -euo pipefail
cd /home/martin/projects/pidrive
ESP="${ESP:-http://192.168.178.88}"
SG="${SG:-/dev/sg0}"
STAMP="${STAMP:-$(date +%H%M)}"
BASE="docs/betrieb/artifacts-2026-10-07-lab"

soft_rst() {
  curl -sS --max-time 8 -X POST "$ESP/api/restart" -H 'Content-Type: application/json' -d '{}' >/dev/null || true
  sleep 10
}

wait_sg() {
  local i
  for i in $(seq 1 45); do
    if sg disk -c 'python3 -c "import os; fd=os.open(\"/dev/sg0\", os.O_RDONLY); os.close(fd)"' >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  soft_rst
  for i in $(seq 1 45); do
    if sg disk -c 'python3 -c "import os; fd=os.open(\"/dev/sg0\", os.O_RDONLY); os.close(fd)"' >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

run_one() {
  local name="$1"; shift
  soft_rst
  wait_sg || { echo "ABORT no sg for $name"; return 1; }
  local out="$BASE/lab88-${name}-${STAMP}"
  mkdir -p "$out"
  echo "=== $name → $out ===" | tee "$out/RUN.log"
  set +e
  sg disk -c "$* --out $out" 2>&1 | tee -a "$out/RUN.log"
  local ec=${PIPESTATUS[0]}
  set -e
  echo "DONE $name exit=$ec" | tee -a "$out/RUN.log"
  sleep 3
}

echo "FOLLOWUP_STAMP=$STAMP"

# C5: clean cursor — RST, then live sequential @4.0 ms + 1 Hz poll (no 10 Hz)
OUT5="$BASE/lab88-c5-slope-clean-1hz-${STAMP}"
soft_rst
wait_sg
mkdir -p "$OUT5"
echo "=== c5-slope-clean-1hz → $OUT5 ===" | tee "$OUT5/RUN.log"
sg disk -c "python3 tools/feld_status_poll.py --esp $ESP --interval 1.0 --seconds 75 --out $OUT5/poll-1hz.jsonl" >"$OUT5/poll.log" 2>&1 &
POLL_PID=$!
sleep 2
set +e
sg disk -c "python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 1200 --live fav0 --live-prefill-s 6 --period-ms 4.0 --sg $SG --esp $ESP --out $OUT5" 2>&1 | tee -a "$OUT5/RUN.log"
echo "DONE c5-bench exit=${PIPESTATUS[0]}" | tee -a "$OUT5/RUN.log"
wait "$POLL_PID" 2>/dev/null || true

# C4 GW
run_one "c4-gw-live" \
  "python3 tools/nbt_hu_sim.py --golden GW --live fav0 --period-ms 5.1 --live-prefill-s 8 --sg $SG --esp $ESP"

# C6 G7 bare + autoplay (each fresh RST)
run_one "c6-g7-bare" \
  "python3 tools/nbt_hu_sim.py --golden G7 --period-ms 4.0 --sg $SG --esp $ESP"
run_one "c6-g7-autoplay" \
  "python3 tools/nbt_hu_sim.py --golden G7 --g7-autoplay --period-ms 4.0 --sg $SG --esp $ESP"

echo "FOLLOWUP_DONE stamp=$STAMP"
