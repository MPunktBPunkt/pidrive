#!/usr/bin/env bash
# Online C1–C7 runner (needs ESP .88 HTTP + /dev/sg0). Sequential — shares sg0.
set -euo pipefail
cd /home/martin/projects/pidrive
ESP="${ESP:-http://192.168.178.88}"
SG="${SG:-/dev/sg0}"
STAMP="${STAMP:-$(date +%H%M)}"
BASE="docs/betrieb/artifacts-2026-10-07-lab"
run() {
  local name="$1"; shift
  local out="$BASE/lab88-${name}-${STAMP}"
  mkdir -p "$out"
  echo "=== $name → $out ===" | tee "$out/RUN.log"
  sg disk -c "$* --out $out" 2>&1 | tee -a "$out/RUN.log"
  echo "DONE $name" | tee -a "$out/RUN.log"
}

# C1 ×3
for i in 1 2 3; do
  run "c1-online-r${i}" \
    "python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 2000 --sg $SG --esp $ESP"
done

# C3
run "c3-online" \
  "python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 512,4096,16384,65536 --bench-n 500 --sg $SG --esp $ESP"

# C2 core cells (2 reps each) — idle / armed-no-prod / armed+prod
for cell in idle armed armedprod; do
  for r in 1 2; do
    case "$cell" in
      idle) extra="" ;;
      armed) extra="--live fav0 --live-no-producer" ;;
      armedprod) extra="--live fav0 --live-prefill-s 3" ;;
    esac
    run "c2-${cell}-r${r}" \
      "python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 2000 --sg $SG --esp $ESP $extra"
  done
done

# C4: G7 + GW with live producer, period 5.1
run "c4-g7-live" \
  "python3 tools/nbt_hu_sim.py --golden G7 --live fav0 --period-ms 5.1 --live-prefill-s 8 --sg $SG --esp $ESP"
run "c4-gw-live" \
  "python3 tools/nbt_hu_sim.py --golden GW --live fav0 --period-ms 5.1 --live-prefill-s 8 --sg $SG --esp $ESP"

# C6: G7 field model + one REPLAY window
run "c6-g7" \
  "python3 tools/nbt_hu_sim.py --golden G7 --period-ms 4.0 --sg $SG --esp $ESP"
run "c6-g7-autoplay" \
  "python3 tools/nbt_hu_sim.py --golden G7 --g7-autoplay --period-ms 4.0 --sg $SG --esp $ESP"
REPLAY="docs/betrieb/artifacts-2026-10-04-feld/p1-run-a/msc_reads.jsonl"
if [[ -f "$REPLAY" ]]; then
  run "c6-replay-resume" \
    "python3 tools/nbt_hu_sim.py --golden REPLAY --period-ms 4.0 --replay $REPLAY --replay-ms-from 364034 --replay-ms-to 376757 --sg $SG --esp $ESP"
fi

# C7: G8 remount ×3 + soft-rst ×1
for r in 1 2 3; do
  run "c7-g8-remount-r${r}" \
    "python3 tools/nbt_hu_sim.py --golden G8 --sg $SG --esp $ESP"
done
run "c7-g8-softrst" \
  "python3 tools/nbt_hu_sim.py --golden G8 --soft-rst --sg $SG --esp $ESP"

# G6 rehearsal (not in ALL)
run "g6-rehearsal" \
  "python3 tools/nbt_hu_sim.py --golden G6 --sg $SG --esp $ESP"

echo "ALL_C_RUNS_DONE stamp=$STAMP"
