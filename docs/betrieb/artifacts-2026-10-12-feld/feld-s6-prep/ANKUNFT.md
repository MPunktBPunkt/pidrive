# Ankunft · s6 starten (Auto-Pi)

ESP `.89` im Heim-WLAN. **Default: FW-Freeze 0.4.46 · kein OTA · kein Stall.**  
Ziel: Q11 Reset-Grund **ohne Bridge-Last**, dann Ohr@32k nur Klasse A.

```bash
ssh pidrive@192.168.178.105
cd ~/pidrive && git pull --ff-only || true
tar xzf /tmp/SYNC-TO-PI-S6.tgz -C ~/pidrive 2>/dev/null || true
cd ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep
./s6-check.sh before
# UART zuerst (Laptop/USB-UART, DTR/RTS aus!), dann:
./run-s6.sh q11 900
```

Zweites Terminal:

```bash
cd ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep
./mark.sh "Q11 uart + OTG no-bridge"
./s6-check.sh after-plug   # Uptime/Serial — Klasse A?
# Wenn A ≥30 s hält:
./mark.sh "S0 start bridge / stream phase"
# neues Terminal oder nach Stop von q11:
./run-s6.sh stream 1200
./mark.sh "O2 BOB ear 32k — tip only if playingUid"
```

### Abort-Regeln (s5)

- Weiße LED / Serial-Sprung → Episode **B**, kein Ohr-Claim  
- Tip **nicht** blind wiederholen; erst `./s6-check.sh` mit `playingUid`/`absEnd>0`  
- Weniger Steckzyklen als s5

### Stall/E7

Nur mit explizitem Go → `E7-FELD.md` + `./ota-stall-048.sh`.

Pocket: `GO.md` · Auswertung: `python3 ~/pidrive/tools/feld_live_window.py --run <RUN> --bps 4000`
