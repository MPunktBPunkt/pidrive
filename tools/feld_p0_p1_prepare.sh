#!/usr/bin/env bash
# Safe prep for today's P0+P1 field run. Does NOT OTA firmware.
set -euo pipefail
PI="${PI:-pidrive@192.168.178.105}"
PASS="${PIDRIVE_SSH_PASS:-pidrive}"
ESP89="${ESP89:-http://192.168.178.89}"
BRIDGE_SRC="${BRIDGE_SRC:-/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py}"
OUT="${OUT:-/home/martin/projects/pidrive/docs/betrieb/artifacts-2026-10-04-feld}"

ssh_pi() {
  sshpass -p "$PASS" ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no \
    -o ConnectTimeout=8 "$PI" "$@"
}
scp_pi() {
  sshpass -p "$PASS" scp -o PreferredAuthentications=password -o PubkeyAuthentication=no "$@"
}

echo "=== P0/P1 field prep (no OTA) ==="
mkdir -p "$OUT"/{p0-provokation,p1-run-a,p1-run-b}
date -Is | tee "$OUT/prepared_at.txt"

# Deploy current bridge (lock + connect-retry)
scp_pi "$BRIDGE_SRC" "$PI:/home/pidrive/pump_bridge.py"
ssh_pi 'python3 -m py_compile /home/pidrive/pump_bridge.py && grep -q MscSessionLock /home/pidrive/pump_bridge.py && echo bridge_OK'

# Fresh service + empty traces
ssh_pi 'echo '"$PASS"' | sudo -S systemctl restart pidrive_pump_bridge
sleep 2
: > /tmp/pidrive_msc_reads.jsonl
: > /tmp/pidrive_msc_lock.jsonl
: > /tmp/pidrive_msc_diag.jsonl
systemctl is-active pidrive_pump_bridge
pgrep -af "/home/pidrive/pump_bridge.py" | head -1
echo pidrive | sudo -S journalctl -u pidrive_pump_bridge -n 8 --no-pager | tail -8
'

# EAR stubs
for d in p0-provokation p1-run-a p1-run-b; do
  cat > "$OUT/$d/EAR.txt" <<EOF
# EAR $d — fill during field
date:
fw:
serial:
bridge_hello:
ov:
tcp_up_before_plug:

# P0 only:
menu_before:
menu_after_provoke:
frozen_reject: yes/no

# P1 only:
preflight.warmth.fav0: {bytes, cold, lba0, lba1}
preflight.warmth.fav1:
preflight.warmth.fav2:
started_uid:
nominal_end_s:
first_body_read_s:
delta_s:
delta_rc:
result_bool_cold_next:
class_A_to_E:
notes:
EOF
done

cp -f /home/martin/projects/pidrive/docs/betrieb/FELD-P0-P1-CHECKLISTE-2026-10-04.md "$OUT/CHECKLISTE.md"

echo "=== probe .89 (optional) ==="
if curl -sS --connect-timeout 3 "$ESP89/api/status" -o "$OUT/esp89-status-prep.json" 2>/dev/null; then
  python3 - <<PY
import json
d=json.load(open("$OUT/esp89-status-prep.json"))
print("ONLINE", d.get("version"), "serial", (d.get("msc") or {}).get("usbSerial"))
v=str(d.get("version") or "")
if "0.4.42" not in v:
    print("WARN: expected 0.4.42-dev — do NOT run 0.4.36 homecoming OTA")
else:
    print("FW OK for field")
PY
else
  echo ".89 still offline — OK; bridge is retrying. Plug car WiFi later."
  echo "Re-check: curl -sS $ESP89/api/status | python3 -m json.tool | head"
fi

echo
echo "Artifacts: $OUT"
echo "Checklist: docs/betrieb/FELD-P0-P1-CHECKLISTE-2026-10-04.md"
echo "Done. In car: PHASE P0 → Unplug → P1×2"
