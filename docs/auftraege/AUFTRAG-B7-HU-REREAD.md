# Folgeauftrag B7 — HU-Reread / 150 s + Architekturgrenze

**Stand:** 2026-10-03 · aktiv (Rev. 2)  
**Überordnung:** [`AUFTRAG-MSC-HOST-READ-NACHWEIS.md`](AUFTRAG-MSC-HOST-READ-NACHWEIS.md) (M1)  
**Feldbericht:** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) §11.10  
**FW:** `esp32.pidrive` 0.4.36-dev · Lab `.88` · Auto `.89`

---

## Ausgangslage

Feld §11.10: Mount-Scan + Cache in den beobachteten 60 s-Fenstern (Fenster oft **nach** Burst).  
Kontinuierliches MSC-Readahead **nicht belegt**. Nachlesen über Slot-/Track-Grenzen **ungeprüft**.

**Problemformulierung:** unklar, ob bei **wesentlich größerer** Datei während Wiedergabe weitere MSC-Reads kommen. Heutige ~2 MiB-Geometrie erklärt „alles cachen“ als rational — Überordnung §0.  
**Zusatz:** weitere Reads ≠ Live (Pace-Frage); L-Leiter später **statisch**, nicht Live — Überordnung §0.1–0.2.

## Entscheidung: kein separates Probe-FW-Repo

Bestehende Lab-APIs + NBT-Harness reichen. BMW-Cache-Fragen = Auto-exklusiv.

Optional in `esp32.pidrive`: Counter-Reset / Trace — nur bei Bedarf. **M0** nur bei realen Burst-Drops (quantifiziert: Anzahl + LBA-Bereich).

## Zählersemantik

[`../betrieb/artifacts-2026-10-02-60s/lab88-counter-semantics/COUNTER-SEMANTICS.md`](../betrieb/artifacts-2026-10-02-60s/lab88-counter-semantics/COUNTER-SEMANTICS.md) — `streamBytes` = Live-Overlay; `readOverflow` = Telemetrie-Drops.

## Vorbereitung — Auto bleibt 0.4.36 für M1

Checkliste: [`../betrieb/B7-MORGEN-CHECKLISTE.md`](../betrieb/B7-MORGEN-CHECKLISTE.md)

| Item | Status |
|------|--------|
| FW Auto | **0.4.36-dev** — kein Ring-OTA während B7 |
| L0 Lab | **erlaubt parallel** entwickeln; Auto-OTA **nach** B7 |
| Tool | `tools/feld_150s_slot_pass.py` |
| Homecoming | `tools/feld_prepare_homecoming.sh` → Bridge `.89` |

```bash
./tools/feld_prepare_homecoming.sh
python3 tools/feld_150s_slot_pass.py --uid fav1 --note "HH:MM OTG PDxxxx B7-A"
```

---

## M1 — drei getrennte Passes

### B7-A — 150 s Einzelpass (Baseline)

1. Frischer OTG-Replug, Sync **vor** Senderwahl.  
2. Live/Bridge bereit **vor** Select.  
3. Eine Station ≥150 s; Ohr-Stoppuhr + **UI-Position** notieren.  
4. Poll: `readCount`, `lastReadLba`, `slotMap`, `playingUid`, `streamBytes`, `readOverflow`, `cursorArmed`, `hostAbsCursor`.  
5. Scan- vs. Play-LBAs (wenn Trace).  
6. UID-Urteile nur bei Ohr = `playingUid` = Bridge `play_uid`.

**Erwartung:** sehr wahrscheinlich **keine Play-Reads** (Stick ~komplett im Cache). Das ist die **Baseline**, kein Abbruch des USB-Ziels.

### B7-B — Armed-Replug

Stream vor HU-Burst warm → Replug → Datei wählen.  
Frage: `streamBytesΔ` im Burst?

**Erwartung / Deckel:** 48 KiB Ring ≈ **~8 s** Live @ ~6 KiB/s. „Nur ~8 s“ = physikalisches Maximum, **kein** Misserfolg.

### B7-C — Ordnerwechsel / erneute Auswahl

Payload-File-Reads vs. Directory/FAT.  
**Hart** nur mit M0-Read-Klassen; sonst nur Ohr/`playingUid` (kein Transport-Urteil).

---

## Lab parallel (ohne Auto-OTA)

- L0-Geometrie in `esp32.pidrive` (FAT16, 4 KiB-Cluster) auf `.88` — Überordnung M2.  
- NBT-Suite / Remount-Doku wenn `/dev/sg0` da.  
- Kein Ring-FW ohne Pace-Nachweis (M4).

## Nicht-Ziele

- Kein Auto-OTA für Ring/L0 **während** B7-Hörfenster.  
- Kein Probe-Repo; keine A2-Abnahme Dauerstreaming.  
- Kein Live-Overlay als Messvariable der späteren L-Leiter.

## Abbruch / nächster Schritt (nach M1)

| Ergebnis | Nächster Schritt |
|----------|------------------|
| Spätere Play-Reads + Cursor | Pace analysieren → Ring/Pacing (M4); L-Leiter optional |
| Keine Play-Reads (erwartet) | Baseline ok → L0-OTA → **statische** L-Leiter (M3) |
| B7-B ≈8 s Live | Deckel bestätigt, kein Fail |
| Nach L-Leiter + Plateau-Gate keine Nachlese | Remount → sonst BT-Hybrid |
