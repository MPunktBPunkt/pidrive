#!/usr/bin/env bash
# Set/remove one pump_bridge --name-override-file entry atomically.
set -euo pipefail

FILE="${NAME_OVERRIDE_FILE:-/tmp/pidrive-name-overrides.json}"
UID_="${1:-}"
NAME="${2-}"
if [[ -z "$UID_" ]]; then
  echo "Nutzung: $0 <uid> <neuer Name>" >&2
  echo "Leerer Name entfernt den Override. OTG vorher abstecken." >&2
  exit 2
fi

python3 - "$FILE" "$UID_" "$NAME" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
uid, name = sys.argv[2], sys.argv[3].strip()
try:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
except Exception as exc:
    raise SystemExit(f"{path}: invalid JSON: {exc}")
if not isinstance(data, dict):
    raise SystemExit(f"{path}: root must be an object")
if name:
    data[uid] = name
else:
    data.pop(uid, None)
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_name(path.name + ".tmp")
tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, path)
print(json.dumps(data, ensure_ascii=False))
PY

echo "Override gespeichert: $FILE"
echo "Bridge liest die Datei laufend; mit --msc-lock wird die Änderung erst bei abgestecktem OTG publiziert."
