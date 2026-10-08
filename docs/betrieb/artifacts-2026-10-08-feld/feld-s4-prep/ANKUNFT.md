# Ankunft · s4 starten (Auto-Pi)

ESP `.89` muss im Heim-WLAN sein. FW-Freeze · **kein OTA**.

```bash
ssh pidrive@192.168.178.105
cd ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s4-prep
./s4-check.sh before
./run-s4.sh 1800
```

Zweites Terminal:

```bash
cd ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s4-prep
./mark.sh "K1 BOB tap"
./s4-check.sh after-tap   # nach Tap / nach Plug
```

Pocket: `GO.md` · Protokoll: `../FELDPROTOKOLL-S4-TONFENSTER.md`

| ID | Kurz |
|----|------|
| K1 | BOB 30 s → Replug → von vorn; Zähltöne |
| K2 | Bayern + Replug (R28) |
| K3 | OTG ab → `./rename.sh fav2 "Radio BOB 1008"` → an → Start 0 oder P? |
| K4 | Name lassen, Replug-Kontrolle |
| K5 | Reboots mitzählen |

Danach: `./rename.sh fav2 ""`  
Handyvideo auf HU + Ton.
