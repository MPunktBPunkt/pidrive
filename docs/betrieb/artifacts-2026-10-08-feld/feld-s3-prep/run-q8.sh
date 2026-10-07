#!/usr/bin/env bash
# Q8 für den letzten s3-Lauf (oder Pfad als $1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="${PROJ:-/home/martin/projects/pidrive}"
if [[ $# -ge 1 ]]; then
  RUN="$1"
else
  RUN="$(ls -d "$ROOT"/s3-* 2>/dev/null | tail -n1 || true)"
fi
[[ -n "${RUN:-}" && -d "$RUN" ]] || { echo "Kein s3-Lauf gefunden. Usage: $0 [lauf-ordner]"; exit 1; }
OUT="$RUN/q8"
mkdir -p "$OUT"
extra=()
[[ -f "$RUN/trace.jsonl" ]] && extra+=(--trace "$RUN/trace.jsonl")
echo "Q8: $RUN → $OUT"
python3 "$PROJ/tools/feld_q8_msc_order.py" --reads "$RUN/msc_reads.jsonl" "${extra[@]}" --out-dir "$OUT"
echo "Fertig. Verdicts:"
python3 - <<PY
import json
from pathlib import Path
p=Path("$OUT")/"Q8-REPORT.json"
rep=json.loads(p.read_text())
for e in rep["episodes"]:
    r=e.get("r10") or {}
    print(f"{e['label']:4} {r.get('verdict','?'):20} head_like={r.get('head_like')}  {(e.get('pattern_kib') or '')[:50]}")
PY
