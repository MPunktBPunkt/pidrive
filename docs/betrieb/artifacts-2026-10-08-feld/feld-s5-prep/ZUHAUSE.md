# Zu Hause — s5 Fenster + Q11 · 2026-10-09

**Ziel im Auto (~20–25 min):** Q11 Reset-Ursache · Ohr @32k Klasse A · K3 Name (FAT)  
**Freeze:** FW `0.4.46-dev` · **kein OTA** · **kein Stall**

## Prep-Status (Dev-Host)

- [x] HEAD `b61df4d` = `origin/main` (Übergabe s5)
- [x] `feld-s5-prep/` Skripte syntaktisch OK
- [x] `run-s5.sh` Default **32k / 4000 B/s / marker / msc-lock**
- [x] `run-s5.sh` setzt jetzt immer `--name-override-file` (K3)
- [x] Sync-Paket `../SYNC-TO-PI-S5.tgz`
- [ ] Auto-Pi `.105` online → `git pull` / Sync
- [ ] ESP Feld `.89` online → `s5-check.sh before`
- [ ] UART-Adapter: DTR/RTS **aus**

## Mitnehmen

1. Handy (Video: weiße LED ja/nein + Hördauer)
2. USB-UART ohne Auto-Reset (kein DTR/RTS)
3. Pocket: `GO.md` / `ANKUNFT.md`

## Ankunft (Auto-Pi)

```bash
ssh pidrive@192.168.178.105
cd ~/pidrive && git pull
# falls Sync-Tar: tar xzf …/SYNC-TO-PI-S5.tgz -C ~/pidrive
cd ~/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep
./s5-check.sh before
# UART zuerst, dann:
./run-s5.sh 1800
```

## Reihenfolge

| ID | Aktion | Nur Klasse A? |
|----|--------|----------------|
| Q11 | UART → 1× OTG → `rst:`/Brownout | B ok für Reset-Log |
| O2 | BOB Ohr + Zähltöne @32k | **A** |
| K2 | Bayern Replug | **A** |
| K3 | OTG ab → `./rename.sh fav2 "Radio BOB 1008"` → Freeze → an | **A** |
| K4 | `./rename.sh fav2 ""` + Session | **A** |
| K5 | Reboots zählen | — |

**Hypothese Ohr@32k:** A länger (~10–12 s) / B weiter ~5–6 s / C nur Reset (Klasse B).
