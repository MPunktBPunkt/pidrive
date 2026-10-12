# Zu Hause — s6 Q11-first + optional E7 · 2026-10-12

**Ziel im Auto:** Q11 Reset-Ursache **vor** erneutem Stream/Ohr; Ohr@32k nur Klasse A; Stall/E7 nur mit Go.  
**s5-Lehre:** Unter Bridge/WLAN-Last fast nur Klasse B → Phase `q11` **ohne** Pump-Bridge.

## Prep-Status (Dev-Host)

- [x] `pidrive` `origin/main` inkl. E7-Lab-Artefakte (`58e6ccd`+)
- [x] Lab `.88` = `0.4.48-dev`, Stall-Default aus; PC E7 L1 PASS
- [x] Feld `.89` = Freeze `0.4.46-dev` (kein OTA ohne Go)
- [x] `feld-s6-prep/` Skripte + Sync-Tar
- [ ] Auto-Pi `.105` online → Sync / `git pull`
- [ ] ESP `.89` online → `./s6-check.sh before`
- [ ] UART-Adapter: DTR/RTS **aus**

## Mitnehmen

1. Handy (Video: weiße LED + Hördauer)
2. USB-UART **ohne** Auto-Reset (kein DTR/RTS) — **Pflicht für Q11**
3. Pocket: `GO.md` / `ANKUNFT.md`
4. Optional Go-only: OTA-Bin auf Pi (`dist/…0.4.48…`) — **nicht** flashen ohne Go

## Ankunft (Auto-Pi)

```bash
ssh pidrive@192.168.178.105
cd ~/pidrive && git pull --ff-only || true
# falls nötig:
#   tar xzf /tmp/SYNC-TO-PI-S6.tgz -C ~/pidrive
cd ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep
./s6-check.sh before
# UART zuerst, dann Phase 1:
./run-s6.sh q11 900
```

## Reihenfolge

| ID | Aktion | Nur Klasse A? |
|----|--------|----------------|
| Q11 | UART → OTG ohne Bridge → `rst:`/Brownout | B ok für Reset-Log |
| S0 | Bridge starten erst nach A ≥30 s | **A** |
| O2 | BOB Ohr @32k; Tip nur bei Play/absEnd | **A** |
| K5 | Reboots/Serial zählen | — |
| E7 | OTA 0.4.48 + Stall-Leiter | **Go + A** |

Kontext: [`MASSNAHMEN-E7`](../../../planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md) · Lab [`E7-Leiter`](../../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md) · s5 [`ERGEBNIS-S5`](../../artifacts-2026-10-08-feld/feld-s5-prep/s5-20261011-184623/ERGEBNIS-S5.md)
