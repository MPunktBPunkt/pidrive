# Ankunft · s5 starten (Auto-Pi)

ESP `.89` im Heim-WLAN. **FW-Freeze · kein OTA.**  
Ziel: Q11 Reset-Grund + Ohr-Fenster @32k + K3 Name (FAT).

```bash
ssh pidrive@192.168.178.105
cd ~/pidrive && git pull --ff-only || true
# K3-Fix (name-override) + Prep: Sync-Tar falls pull die Dateien noch nicht hat
#   tar xzf /tmp/SYNC-TO-PI-S5.tgz -C ~/pidrive   # vom Dev-Host sync-when-online.sh
cd ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep
./s5-check.sh before
# UART zuerst (Laptop/USB-UART, DTR/RTS aus), dann:
./run-s5.sh 1800   # setzt --name-override-file automatisch (K3)
```

Zweites Terminal:

```bash
cd ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep
./mark.sh "Q11 plug cycle 1"
./s5-check.sh after-plug   # Uptime/Serial — Klasse A?
./mark.sh "O2 BOB ear 32k"
```

Pocket: `GO.md` · Kontext: [`../UEBERGABE-S4-NAECHSTE-KI-2026-10-08.md`](../UEBERGABE-S4-NAECHSTE-KI-2026-10-08.md)

**K3:** OTG abstecken → `./rename.sh fav2 "Radio BOB 1008"` → Bridge-Log `MSC_MAP_FROZEN` mit neuem Namen → OTG an.  
Danach: `./rename.sh fav2 ""` und erneut OTG-Zyklus für Restore.

Handyvideo: weiße LED ja/nein + Hördauer.
