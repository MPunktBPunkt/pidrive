# Feld s4 — Pocket Tonfenster · ~15–20 min

**FW Freeze · kein OTA** · Lab-Gate L0 muss PASS sein  
**Volltext:** [`../FELDPROTOKOLL-S4-TONFENSTER.md`](../FELDPROTOKOLL-S4-TONFENSTER.md)

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s4-prep
./run-s4.sh 1800
# Terminal 2:
./s4-check.sh before
./mark.sh "K1 BOB tap"
```

| ID | Aktion |
|----|--------|
| **K1** | BOB 30 s → Replug → von vorn; Zähltöne zählen (2×) |
| **K2** | Bayern + Replug (R28) |
| **K3** | `./rename.sh fav2 "Radio BOB 1008"` bei abgestecktem OTG → Replug → Start 0 oder P? |
| **K4** | Name zurück / Kontrolle ohne Rename |
| **K5** | Reboots mitzählen |

Override danach: `./rename.sh fav2 ""`  
Auswertung: `python3 tools/feld_live_window.py --run <RUN>`
