#!/usr/bin/env bash
# Gate-Check für feld-s1-morgen (Fahrzeug-ESP .89)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ESP="${ESP:-http://192.168.178.89}"
curl -sS "$ESP/api/status" -o "$ROOT/status-gate.json"
curl -sS "$ESP/api/menu" -o "$ROOT/menu-gate.json" 2>/dev/null || true
python3 - <<PY
import json
st=json.load(open("$ROOT/status-gate.json"))
m=st.get("msc") or {}
names=[s.get("name") for s in (st.get("slotMap") or m.get("slotMap") or [])]
print("version", st.get("version"))
print("fwType", st.get("fwType"))
print("serial", m.get("usbSerial"))
print("slotMap", names)
need={"Rock Antenne","Rock Antenne Bayern","Radio BOB!"}
ok=need.issubset(set(names or []))
print("GATE_NAMES", "PASS" if ok else "FAIL")
print("stall_hint: FW must be 0.4.46-dev, kein Stall-OTA")
PY
echo "Bridge: ssh pidrive@192.168.178.105 'journalctl -u pidrive_pump_bridge -n 40 --no-pager | grep -iE FROZEN|frozen|error || true'"
