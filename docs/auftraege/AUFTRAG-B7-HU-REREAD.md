# Folgeauftrag B7 — HU-Reread / 150 s + Architekturgrenze

**Stand:** 2026-10-03 · aktiv (geschärft)  
**Überordnung:** [`AUFTRAG-MSC-HOST-READ-NACHWEIS.md`](AUFTRAG-MSC-HOST-READ-NACHWEIS.md) (M1)  
**Feldbericht:** [`../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md`](../betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md) §11.10  
**FW:** `esp32.pidrive` 0.4.36-dev · Lab `.88` · Auto `.89`

---

## Ausgangslage

Feld §11.10: Mount-Scan + Cache in den beobachteten 60 s-Fenstern (Fenster oft **nach** Burst).  
Kontinuierliches MSC-Readahead **nicht belegt**. Nachlesen über Slot-/Track-Grenzen **ungeprüft**.

**Problemformulierung:** nicht „NBT liest nie nach“, sondern: unklar, ob bei **Live-gefüllter, wesentlich größerer** Datei während Wiedergabe weitere MSC-Reads kommen. Heutige ~2 MiB-Geometrie erklärt „alles cachen“ als rationales HU-Verhalten — siehe Überordnung §0.

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

Optional später **in** `esp32.pidrive` (nicht Fork): Counter-Reset-API, größerer Trace-Ring, Remount-Parameter — nur wenn B7 das braucht. Telemetrie-Fixes = **M0** in der Überordnung (vor strengem Feldurteil, wenn Burst-Samples droppen).

## Zählersemantik (Code, Lab 2026-10-02)

Siehe [`../betrieb/artifacts-2026-10-02-60s/lab88-counter-semantics/COUNTER-SEMANTICS.md`](../betrieb/artifacts-2026-10-02-60s/lab88-counter-semantics/COUNTER-SEMANTICS.md).

Kurz:

- `streamBytes` = Live-Overlay-Bytes an Host (`streamBytesServed_`).
- `readOverflow` = Telemetrie-Queue-Drops, **kein** USB-Fail.
- `live_ratio` = Harness-KPI, kein Statusfeld.

## Vorbereitung — **keine FW-Änderung für M1**

Morgen-Checkliste: [`../betrieb/B7-MORGEN-CHECKLISTE.md`](../betrieb/B7-MORGEN-CHECKLISTE.md) · Ring/BT-Papier: [`../betrieb/POST-1110-RING-BT-NOTES.md`](../betrieb/POST-1110-RING-BT-NOTES.md)

| Item | Status |
|------|--------|
| FW Auto/Lab | **0.4.36-dev belassen** — kein OTA, kein Ring, kein Probe-Fork |
| Zählersemantik | dokumentiert (`COUNTER-SEMANTICS.md`) |
| Tool | `tools/feld_150s_slot_pass.py` (Poll 2 s, Orientierungsmarken, EAR-Stoppuhr) |
| Homecoming | `tools/feld_prepare_homecoming.sh` → Bridge `.89`, FW-Check |
| Überordnung | Entscheidungsbaum + L-Leiter **nach** B7 |

```bash
./tools/feld_prepare_homecoming.sh
python3 tools/feld_150s_slot_pass.py --uid fav1 --note "HH:MM OTG PDxxxx"
```

---

## M1 — drei getrennte Passes

### B7-A — 150 s Einzelpass (Ist-Verhalten)

1. Frischer OTG-Replug, Sync-Marker **vor** Senderwahl.  
2. Live-Inhalt / Bridge bereit **bevor** Select (nicht erst nach Burst).  
3. Eine Station ≥150 s; Stoppuhr Ohr (Start/Stop).  
4. Poll ≤2 s: `readCount`, `lastReadLba`, `slotMap`, `playingUid`, `streamBytes`, `readOverflow`, `cursorArmed`, `hostAbsCursor`.  
5. Scan-LBAs vs. Play-LBAs notieren (wenn Trace vorhanden).  
6. Nur UID-Urteile, wenn gehörte Station = `playingUid` = Bridge `play_uid`. Read-flat bleibt trotzdem gültig.

### B7-B — Armed-Replug

Getrennt von A: Stream/Overlay **vor** dem HU-Burst warm (Lab-Play oder Bridge armed), dann OTG-Replug / Serial-Bump, sofort relevante Datei wählen.  
Frage: landen Live-Bytes im Burst-Fenster (`streamBytesΔ` während Erst-Reads)?

### B7-C — Ordnerwechsel / erneute Auswahl

Im selben Mount: Ordnerwechsel und nacheinander alle Sender; Marker pro Wechsel.  
Frage: neue **Payload**-File-Reads / UID-Wechsel — Directory-Reads nicht als Audio-Transport werten.

---

## Auftrag Lab (ohne neues Repo)

- NBT-Suite / paced auf `.88`, wenn Proxmox `/dev/sg0` erreichbar.  
- Remount-Verhalten dokumentieren (Host kann Remount „schlucken“ — Lab 2026-10-02: Gen blieb 6).  
- Keine Ringgrößen-FW ohne Host-Read-Nachweis (Überordnung M4).

## Nicht-Ziele

- Kein OTA Auto für Ring/Präfill.  
- Kein neues Probe-Repo.  
- Keine A2-Abnahme Dauerstreaming über MSC.  
- Kein L3/L4 und keine Geometrie-FW parallel zu diesem Feldfenster (das ist **M2/M3** danach).

## Abbruch / Architektur (nach M1, vor Endurteil)

| Ergebnis B7-A/B/C | Nächster Schritt |
|-------------------|------------------|
| Spätere Slot-/Play-Reads, Cursor folgt | Segment-Live; Ring aus Timing (M4) — L-Leiter optional zur Kapazität |
| Keine Play-Reads auf 512 KiB | **nicht** sofort BT — **M2 Geometrie + L-Leiter** (Überordnung) |
| Keine Reads + keine Auswahlerkennung | Play-Detect/Meta getrennt klären; L-Leiter trotzdem für Cache-Hypothese |
| Erst nach L-Leiter + Plateau-Gate immer noch keine Nachlese | Remount prüfen → sonst BT-Hybrid bewusst |

Einzelnutzung „keine Reads in 150 s auf dem 2‑MiB-Stick“ beendet das USB-Live-Ziel **nicht** — siehe Gate in der Überordnung §1.
