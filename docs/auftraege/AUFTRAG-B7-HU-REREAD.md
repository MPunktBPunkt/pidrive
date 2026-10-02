# Folgeauftrag B7 — HU-Reread / 150 s + Architekturgrenze

**Stand:** 2026-10-02 · aktiv  
**Feldbericht:** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) §11.10  
**FW:** `esp32.pidrive` 0.4.36-dev · Lab `.88` · Auto `.89`

---

## Ausgangslage

Feld §11.10: Mount-Scan + Cache in den beobachteten 60 s-Fenstern (Fenster oft **nach** Burst).  
Kontinuierliches MSC-Readahead **nicht belegt**. Nachlesen über Slot-/Track-Grenzen **ungeprüft**.

## Entscheidung: kein separates Probe-FW-Repo

Eine eigene „HU-Probe“-Firmware mit dynamischen Parametern wäre **Redundanz**:

| Schon vorhanden | Nutzen |
|-----------------|--------|
| `POST /api/lab/remount` | erzwungenes Re-Enumerate / Serial-Bump |
| `POST /api/lab/play\|stop`, `GET …/overlay_read\|stream\|listen` | Lab ohne BMW-Heuristik |
| `POST /api/config` Play-Detect-Knöpfe | Laufzeit-Parameter ohne Rebuild |
| `tools/nbt_suite.py` / `nbt_replay.py` | Host-Burst/Quiet gegen `.88` (Proxmox `/dev/sg0`) |
| Status: `readCount`, `streamBytes`, `slotMap`, `cursorArmed`, … | Messbarkeit |

**Verworfen:** neues Repo nur zur HU-Analyse. Fehlende Fragen (Cache-Ende, Track-Ende, Stationswahl ohne Reads) sind **Auto-exklusiv** — eine Lab-FW kann die NBT-Cache-Politik nicht ersetzen.

Optional später **in** `esp32.pidrive` (nicht Fork): Counter-Reset-API, größerer Trace-Ring, Remount-Parameter — nur wenn B7 das braucht.

## Zählersemantik (Code, Lab 2026-10-02)

Siehe [`../betrieb/artifacts-2026-10-02-60s/lab88-counter-semantics/COUNTER-SEMANTICS.md`](../betrieb/artifacts-2026-10-02-60s/lab88-counter-semantics/COUNTER-SEMANTICS.md).

Kurz:

- `streamBytes` = Live-Overlay-Bytes an Host (`streamBytesServed_`).
- `readOverflow` = Telemetrie-Queue-Drops, **kein** USB-Fail.
- `live_ratio` = Harness-KPI, kein Statusfeld.

## Vorbereitung (2026-10-02) — **keine FW-Änderung**

| Item | Status |
|------|--------|
| FW Auto/Lab | **0.4.36-dev belassen** — kein OTA, kein Ring, kein Probe-Fork |
| Zählersemantik | dokumentiert (`COUNTER-SEMANTICS.md`) |
| Tool | `tools/feld_150s_slot_pass.py` (Poll 2 s, Orientierungsmarken, EAR-Stoppuhr) |
| Homecoming | `tools/feld_prepare_homecoming.sh` → Bridge `.89`, FW-Check |

```bash
./tools/feld_prepare_homecoming.sh
python3 tools/feld_150s_slot_pass.py --uid fav1 --note "HH:MM OTG PDxxxx"
```

---

1. Frischer OTG-Replug, Sync-Marker **vor** Senderwahl.  
2. Eine Station ≥150 s; Stoppuhr Ohr (Start/Stop).  
3. Poll ≤2 s: `readCount`, `lastReadLba`, `slotMap`, `playingUid`, `streamBytes`, `readOverflow`, `cursorArmed`, `hostAbsCursor`.  
4. Prüfen, ob Reads bei ~28 s / ~87 s (nur Rechenorientierung) oder später kommen.  
5. Nur werten, wenn gehörte Station = `playingUid` = Bridge `play_uid`.

## Auftrag B — Stationswechsel im selben Mount

Nach A: nacheinander alle Sender; Marker pro Wechsel. Frage: erzeugt Auswahl neue Reads / UID-Wechsel?

## Auftrag C — Lab (ohne neues Repo)

- NBT-Suite / paced auf `.88`, wenn Proxmox `/dev/sg0` erreichbar.  
- Remount-Verhalten dokumentieren (Host kann Remount „schlucken“ — Lab 2026-10-02: Gen blieb 6).  
- Keine Ringgrößen-FW ohne B7-Ergebnis.

## Nicht-Ziele

- Kein OTA Auto für Ring/Präfill.  
- Kein neues Probe-Repo.  
- Keine A2-Abnahme Dauerstreaming über MSC.

## Abbruch / Architektur

| Ergebnis A+B | Richtung |
|--------------|----------|
| Spätere Slot-Reads | Segment-Live / Clip-Experiment möglich |
| Keine Reads + keine Auswahlerkennung | MSC = Menü/Cover; Audio-Transport neu bewerten (BT = getrennte Quelle) |
