#!/usr/bin/env bash
# Kopie der laufenden msc.reads nach jedem Protokoll-Teil (A/B/C/…).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TAG="${1:?Teil-Buchstabe, z.B. A}"
SRC="${MSC_READS:-/tmp/pidrive_msc_reads.jsonl}"
STAMP=$(date +%H%M%S)
DST="$ROOT/msc_reads-${TAG}-${STAMP}.jsonl"
if [[ ! -f "$SRC" ]]; then
  echo "fehlt: $SRC" >&2
  exit 1
fi
cp -a "$SRC" "$DST"
# auch „aktuell“ für diesen Teil
cp -a "$SRC" "$ROOT/msc_reads-${TAG}.jsonl"
lines=$(wc -l < "$DST")
bytes=$(wc -c < "$DST")
echo "snap $TAG → $DST ($lines Zeilen, $bytes B)"
# ov first/last
python3 - <<PY
import json
from pathlib import Path
rows=[]
for line in Path("$DST").read_text(errors="replace").splitlines():
    j=line.find("{")
    if j<0: continue
    try: r=json.loads(line[j:])
    except: continue
    if "ov" in r: rows.append(r)
if not rows:
    print("ov: (keine Zeilen)")
else:
    print(f"ov first={rows[0].get('ov')} last={rows[-1].get('ov')} delta={int(rows[-1].get('ov') or 0)-int(rows[0].get('ov') or 0)}")
PY
