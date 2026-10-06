#!/usr/bin/env bash
# Feld AV session prep — Baustelle B (Prefill/Hold path, FW 0.4.46 bulk-drainTcp).
# Safe defaults: deploy bridge, clear traces, artifact stubs. OTA only with --ota.
set -euo pipefail

PI="${PI:-pidrive@192.168.178.105}"
PASS="${PIDRIVE_SSH_PASS:-pidrive}"
ESP="${ESP:-http://192.168.178.89}"
DAY="${DAY:-$(date +%Y-%m-%d)}"
STAMP="${STAMP:-$(date +%H%M)}"
OUT="${OUT:-/home/martin/projects/pidrive/docs/betrieb/artifacts-${DAY}-feld/feld-av-${STAMP}}"
BRIDGE_SRC="${BRIDGE_SRC:-/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py}"
OTA_BIN="${OTA_BIN:-/home/martin/projects/esphub/esp32.pidrive/dist/pidrive.0.4.46-dev.ota.esp32s3.bin}"
DO_OTA=0
SKIP_SSH=0

usage() {
  echo "Usage: $0 [--ota] [--skip-ssh] [--out DIR]"
  echo "  --ota       OTA 0.4.46-dev to .89 when online (field car ESP)"
  echo "  --skip-ssh  only create operator files (no Pi deploy)"
  exit 0
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ota) DO_OTA=1; shift ;;
    --skip-ssh) SKIP_SSH=1; shift ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown: $1"; usage ;;
  esac
done

ssh_pi() {
  if command -v sshpass >/dev/null 2>&1; then
    sshpass -p "$PASS" ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no \
      -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$PI" "$@"
  else
    ssh -o BatchMode=yes -o ConnectTimeout=8 "$PI" "$@"
  fi
}
scp_pi() {
  if command -v sshpass >/dev/null 2>&1; then
    sshpass -p "$PASS" scp -o PreferredAuthentications=password -o PubkeyAuthentication=no "$@"
  else
    scp "$@"
  fi
}

mkdir -p "$OUT"
date -Is | tee "$OUT/prep_started.txt"
echo "OUT=$OUT" | tee "$OUT/OUT.txt"

cat > "$OUT/OPERATOR-NOTES.txt" <<'EOF'
# Operator — kurz (Auto)

PASS streaming: live>0 AND und=0 AND behind=0 (Ohr!)
Ziel: Erstburst-Länge + Ton bei gültigem MP3 (nicht nur und-Zähler).

1) USB + WLAN: .89 erreichbar
2) Gate: Favoriten Rock/Bayern/BOB + Bridge MSC_MAP_FROZEN (siehe FELD-AV-OPERATOR.md)
3) Ein Sender tippen, ~30s hörig
4) Parallel: run-correlate.sh (90s dense)
5) Notieren: Ton ja/nein, welcher Sender
EOF

OPERATOR_SRC="/home/martin/projects/pidrive/docs/betrieb/artifacts-2026-10-06-feld/FELD-AV-OPERATOR.md"
if [[ -f "$OPERATOR_SRC" ]]; then
  cp -f "$OPERATOR_SRC" "$OUT/FELD-AV-OPERATOR.md"
fi

if [[ "$SKIP_SSH" -eq 0 ]]; then
  echo "=== deploy bridge + fresh traces ==="
  if scp_pi "$BRIDGE_SRC" "$PI:/home/pidrive/pump_bridge.py"; then
    ssh_pi 'python3 -m py_compile /home/pidrive/pump_bridge.py && echo bridge_compile_OK
echo '"$PASS"' | sudo -S systemctl restart pidrive_pump_bridge
sleep 2
: > /tmp/pidrive_msc_reads.jsonl
: > /tmp/pidrive_msc_lock.jsonl
: > /tmp/pidrive_msc_diag.jsonl
systemctl is-active pidrive_pump_bridge || true
pgrep -af pump_bridge.py | head -1 || true
echo pidrive | sudo -S journalctl -u pidrive_pump_bridge -n 12 --no-pager | tail -12
' | tee "$OUT/bridge-restart.log"
  else
    echo "WARN: Pi deploy skipped (offline or auth)" | tee "$OUT/bridge-restart.log"
  fi
fi

echo "=== probe ESP .89 ==="
if curl -sS --connect-timeout 4 -m 6 "$ESP/api/status" -o "$OUT/status-prep.json" 2>/dev/null; then
  python3 - <<PY | tee "$OUT/status-prep-summary.txt"
import json
d=json.load(open("$OUT/status-prep.json"))
m=d.get("msc") or {}
print("ONLINE version", d.get("version"), "serial", m.get("usbSerial"), "plugged", m.get("plugged"))
print("pumpTcpUp", d.get("pumpTcpUp"), "peer", d.get("pumpTcpPeer"))
print("playing", d.get("playingUid"), d.get("playingName"))
PY
else
  echo "ESP .89 offline — OK vor Abfahrt; im Auto erneut prüfen." | tee "$OUT/status-prep-summary.txt"
fi

if [[ "$DO_OTA" -eq 1 ]]; then
  echo "=== OTA 0.4.46-dev ==="
  if [[ ! -f "$OTA_BIN" ]]; then
    echo "MISSING $OTA_BIN" | tee "$OUT/ota.log"
    exit 1
  fi
  if curl -sS --connect-timeout 4 "$ESP/api/status" >/dev/null 2>&1; then
    curl -sS -m 180 -F "firmware=@${OTA_BIN}" "$ESP/ota-upload" | tee "$OUT/ota-upload-response.txt"
    echo "waiting reboot..." | tee -a "$OUT/ota.log"
    for i in $(seq 1 45); do
      if curl -sS --connect-timeout 3 -m 4 "$ESP/api/status" -o "$OUT/status-post-ota.json" 2>/dev/null; then
        python3 -c "import json;d=json.load(open('$OUT/status-post-ota.json'));print('post-OTA',d.get('version'),d.get('uptime'))"
        break
      fi
      sleep 2
    done
  else
    echo "OTA skipped: .89 offline — im Auto: $0 --ota --skip-ssh --out $OUT" | tee "$OUT/ota.log"
  fi
fi

# Runnable correlate wrapper in artifact dir
cat > "$OUT/run-correlate.sh" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
cd /home/martin/projects/pidrive
CORR="\${1:-$OUT/correlate-run}"
mkdir -p "\$CORR"
python3 tools/feld_av_correlate.py --esp $ESP --watch-s 90 --interval 0.5 --dense --out "\$CORR" \\
  2>&1 | tee "\$CORR/correlate.log"
python3 tools/feld_av_burst_summary.py "\$CORR/correlate-watch.jsonl" > "\$CORR/burst-summary.json" 2>/dev/null || true
echo "DONE \$CORR"
SCRIPT
chmod +x "$OUT/run-correlate.sh"

cat > "$OUT/run-gate-check.sh" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
curl -sS $ESP/api/status -o "$OUT/status-gate.json"
curl -sS $ESP/api/menu -o "$OUT/menu-gate.json" 2>/dev/null || true
python3 - <<'PY'
import json
st=json.load(open("$OUT/status-gate.json"))
names=[s.get("name") for s in (st.get("slotMap") or (st.get("msc") or {}).get("slotMap") or [])]
print("version", st.get("version"))
print("slotMap", names)
need={"Rock Antenne","Rock Antenne Bayern","Radio BOB!"}
ok=need.issubset(set(names or []))
print("GATE_NAMES", "PASS" if ok else "FAIL")
PY
echo "Bridge: ssh $PI 'grep MSC_MAP_FROZEN /tmp/pump_bridge*.log 2>/dev/null | tail -3; journalctl -u pidrive_pump_bridge -n 30 --no-pager | grep -E FROZEN|frozen'"
SCRIPT
chmod +x "$OUT/run-gate-check.sh"

echo
echo "Prepared: $OUT"
echo "  Im Auto: ./run-gate-check.sh  dann Sender  dann ./run-correlate.sh"
echo "  OTA im Auto: $0 --ota --skip-ssh --out $OUT"
