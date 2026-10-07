#!/usr/bin/env bash
set -euo pipefail
curl -sS http://192.168.178.89/api/status -o "docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen/status-gate.json"
curl -sS http://192.168.178.89/api/menu -o "docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen/menu-gate.json" 2>/dev/null || true
python3 - <<'PY'
import json
st=json.load(open("docs/betrieb/artifacts-2026-10-07-feld/feld-s1-morgen/status-gate.json"))
names=[s.get("name") for s in (st.get("slotMap") or (st.get("msc") or {}).get("slotMap") or [])]
print("version", st.get("version"))
print("slotMap", names)
need={"Rock Antenne","Rock Antenne Bayern","Radio BOB!"}
ok=need.issubset(set(names or []))
print("GATE_NAMES", "PASS" if ok else "FAIL")
PY
echo "Bridge: ssh pidrive@192.168.178.105 'grep MSC_MAP_FROZEN /tmp/pump_bridge*.log 2>/dev/null | tail -3; journalctl -u pidrive_pump_bridge -n 30 --no-pager | grep -E FROZEN|frozen'"
