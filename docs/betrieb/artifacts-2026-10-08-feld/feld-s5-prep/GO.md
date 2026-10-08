# Feld s5 — Pocket · ~20–25 min

**FW Freeze 0.4.46-dev · kein OTA · kein Stall**  
Lab-Gate: Bitrate/K3-FAT/Q10/Klasse-A Remount grün (Abend 08.10.)

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep
# Auto-Pi oft: ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep
./run-s5.sh 1800
# Terminal 2:
./s5-check.sh before
./mark.sh "Q11 uart armed"
```

### Pflicht: Episodenklasse

| Klasse | Bedeutung |
|--------|-----------|
| **A** | OTG ab/an, **keine** weiße LED, Uptime/Serial stabil → Tonfenster/P gültig |
| **B** | weiße LED / Boot → nur Q11; Fenster verwerfen |

### Ablauf

| ID | Aktion | Ziel |
|----|--------|------|
| **Q11** | UART-Log **ohne** DTR/RTS; 1× OTG; `rst:`/Brownout sichern | Reset-Ursache |
| **O2** | Klasse-A Replug, BOB, **Ohr** + Zähltöne @32k | Hörfenster >5–6 s? (Lab ~12,5 s) |
| **K2** | Bayern Klasse-A Replug | R28 multi-station |
| **K3** | OTG **ab** → `./rename.sh fav2 "Radio BOB 1008"` → warten Bridge-Freeze → OTG **an** → Start 0 oder P? | P-Name (FAT lab-verifiziert) |
| **K4** | `./rename.sh fav2 ""` + neue Session | Restore |
| **P1a** | nur wenn K3 klar: gleicher Name, **Hinweis Größe** noch ohne FW — skip oder notieren | Größe offen |
| **K5** | Reboots zählen | Versorgung |

Override-Datei: `NAME_OVERRIDE_FILE=/tmp/pidrive-name-overrides.json` (rename.sh Default).  
Auswertung: `python3 tools/feld_live_window.py --run <RUN>` — **live_s mit 4000 B/s** rechnen, nicht blind 48k.
