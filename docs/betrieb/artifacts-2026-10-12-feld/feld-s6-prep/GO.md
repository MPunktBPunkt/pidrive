# Feld s6 — Pocket · ~25–40 min

**Default: FW Freeze `0.4.46-dev` · kein OTA · kein Stall**  
Lab-E7 PC (12.10.): L0/L1/L3/L4 PASS → NBT-E7 erst nach **Q11 Klasse A** + explizitem Go.

```bash
cd ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep
# Phase 1 — ohne Bridge (Steckfestigkeit / UART):
./run-s6.sh q11 900
# Terminal 2:
./s6-check.sh before
./mark.sh "Q11 uart armed"
# Phase 2 — nur wenn Klasse A hält (keine weiße LED):
./run-s6.sh stream 1200
```

### Pflicht: Episodenklasse

| Klasse | Bedeutung |
|--------|-----------|
| **A** | OTG ab/an, **keine** weiße LED, Uptime/Serial stabil → Tonfenster/E7 gültig |
| **B** | weiße LED / Boot → nur Q11; Fenster/E7 verwerfen |

### Ablauf

| ID | Aktion | Ziel |
|----|--------|------|
| **Q11** | UART **ohne** DTR/RTS; OTG unter **ohne** Bridge zuerst; `rst:`/Brownout | Reset-Ursache |
| **S0** | Bridge/WLAN erst **nach** stabilem OTG (Klasse A ≥30 s) | Last-Entkopplung (s5-Lehre) |
| **O2** | BOB, Ohr + Zähltöne @32k; Tip nur bei `playingUid`/`absEnd>0` | Hörfenster >5–6 s? |
| **K5** | Serial-/Reboot-Zählung | Versorgung |
| **E7** | **nur mit Go:** OTA `0.4.48-dev`, `stallEnable=false` prüfen, dann Leiter | NBT Busy-Toleranz |

### Stall / E7 — Freeze bis Go

- **Nicht** flashen, solange Q11/Klasse-A unklar.  
- Mit Go: `./ota-stall-048.sh` → Check `version=0.4.48-dev`, `stall.enable=false` → erst dann Config-Leiter (siehe `E7-FELD.md`).
