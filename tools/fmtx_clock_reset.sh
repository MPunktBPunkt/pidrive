#!/bin/bash
# fmtx_clock_reset.sh — ExecStopPost von pidrive-fmtx.service
#
# Nach Absturz/kill -9 kann der DMA-Kanal des Senders weiterlaufen und der
# GPCLK-Takt am Pin anliegen. Dieses Script
#   1. beendet verwaiste Sender-Prozesse (SIGINT → SIGKILL),
#   2. schaltet die Taktpins GPIO 4 und GPIO 21 auf Eingang (kein HF am Pin),
#   3. vermerkt den Stopp im State-File.
# Läuft als root. Fehler werden ignoriert (Stopp darf nie hängen).

set -u
PINS="4 21"
PROCS="pi_fm_rds rpitx pichirp tune sendiq"

for p in $PROCS; do
    pkill -INT -x "$p" 2>/dev/null || true
done
sleep 1
for p in $PROCS; do
    pkill -KILL -x "$p" 2>/dev/null || true
done

for pin in $PINS; do
    if command -v pinctrl >/dev/null 2>&1; then
        pinctrl set "$pin" ip pn 2>/dev/null || true
    elif command -v raspi-gpio >/dev/null 2>&1; then
        raspi-gpio set "$pin" ip pn 2>/dev/null || true
    fi
done

STATE=/tmp/pidrive_fmtx_state.json
if [ -f "$STATE" ]; then
    python3 - "$STATE" <<'PY' 2>/dev/null || true
import json, sys, time
p = sys.argv[1]
try:
    st = json.load(open(p))
except Exception:
    st = {}
st.update({"state": "off", "service": False, "clock_reset_ts": int(time.time())})
json.dump(st, open(p, "w"))
PY
fi
exit 0
