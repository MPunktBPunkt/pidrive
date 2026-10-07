# Gesamtbericht Feld Stufe 1 — 2026-10-07 Morgen (`feld-s1-morgen`)

**Fahrzeug:** BMW 118d F20 LCI / NBT Evo USB-OTG · ESP `.89` · Bridge `.105`  
**FW:** **0.4.46-dev** L3 · Serial **PD0089** · `stall_ms=0` (kein Stall-OTA)  
**Ziel:** F1 Decode-Start + F2 Cache/Remount (Silence, Bridge gestoppt)  
**Ergebnis:** **Daten-PASS** (reproduzierbare Episoden) · **F1 nicht eindeutig geschlossen** · **F2 Mischbefund, gut belegt** · Stall-Go **noch nicht**

Maschinenlesbar: [`SUMMARY.json`](SUMMARY.json) · Kompakt-Poll: [`status-poll-compact.csv`](status-poll-compact.csv) · Boots: [`boots.json`](boots.json) · Wechsel: [`play-transitions.json`](play-transitions.json)

---

## Setup

| Item | Wert |
|------|------|
| Session | 07:41:27–07:59:57 (Poll) |
| Poll | 1 Hz `status-poll.jsonl` (~1084 OK / 4 Timeout bei RST) |
| Dense | `f2-watch.jsonl` (Passes 07:51–07:56) |
| Operator | `OPERATOR-LIVE.txt`, `f1-events.jsonl` |
| Bridge | für F1/F2 **gestoppt** (Silence); nach Session wieder `active` |
| Ingest | 1875 status / 4092 slots → `data/pidrive.duckdb` |

**HU-UI (wichtig):** nur **Fortschrittsbalken**, kein Sekundenzähler. Autoplay-Reihenfolge: **BOB → Bayern → Rock Antenne** (`fav2 → fav1 → fav0`).

---

## Timeline (kurz)

| Zeit | Ereignis |
|------|----------|
| 07:41:27 | Poll start; OTG noch aus |
| 07:41:40 | OTG hoch; Scan `readCount`→339; Bridge stop |
| 07:41 | Plug + Autoplay **BOB**; Wechsel **Bayern**; kein Ton |
| 07:44:08–19 | Autoplay → **Rock**: fav0 **8 MiB** Body-Sturm (`rc` 382→2337) |
| 07:46 | Operator: HU nur Balken; RST |
| 07:47–49 | Post-RST: BOB durch (flach/`fav2=512 KiB`); Bayern cold_burst; Rock erneut ~8 MiB; LED=Body |
| 07:51–56 | **5×** RST + schnelle Senderdurchwahl (Repro) |
| 07:57–58 | Letzter Pass: Rock-Burst; Session-Ende; Ingest |

---

## F1 — Decode-Start (Spielzeit vs. Lesefortschritt)

**Methode (angepasst):** `t_timer` = Balken beginnt; `t_eof` = Track/Balken fertig bzw. Slot-Bytes stagnieren. Kein Sekundenzähler.

### Kernspur Rock (fav0, 8 MiB Silence)

Wiederholt (Autoplay und nach jedem RST-Tap):

1. Beim Wechsel auf Rock: **cold_burst** ~11–13 s, `fav0` von Scan-Rest → **~8.0–8.3 MiB**, `readCount` steigt steil.  
2. Danach **`readCount` flach**, `playingUid=fav0` bleibt oft Minuten — HU „spielt“ weiter ohne Bus-Reads.  
3. LED **stark** am Track-Ende des Vorgängers / **kurz** am Rock-Start = MSC-Body (bekannt).

| Episode | Ramp-Fenster | fav0 Ende | Anmerkung |
|---------|--------------|-----------|-----------|
| Boot0 Autoplay | 07:44:08–19 | 8 388 608 | vor erstem RST |
| Boot1 Autoplay | 07:49:38–51 | 8 179 712 | nach RST 07:46 |
| Tap-Passes | 07:51:54–00 / 07:53:03–12 / 07:54:00–09 / 07:55:14–20 / 07:57:12–21 | ~8.2 MiB | Repro |

**Deutung (Entwurf für Peer-Review):** Muster spricht für **Eager/Batch-then-Play** (Datei zuerst über USB, dann Cache-Play), nicht für inkrementelles Live-Decoding vom Bus.  
**Offen:** Operator hat **nicht** bestätigt, ob der Fortschrittsbalken schon **während** der 11–13 s Ramp lief oder erst danach → F1 formal **nicht geschlossen** für Stall-Go.

---

## F2 — Cache über Abwahl / RST

### F2a (gleiche Plug-Session)

- Nach Cold-Body-EOF eines Favs: weitere Wiedergabe oft **ohne** neue Body-Reads (flach) → **Muster B** in-session.  
- Beispiel Boot1: BOB nach RST mit `fav2=524288`, `rc` lange 167 (flach), während Autoplay „durchläuft“.

### F2c (nach ESP-RST) — Mischbefund, reproduzierbar

| Datei | Nach RST typisch | Label |
|-------|------------------|-------|
| BOB `fav2` 512 KiB | oft sofort/nahe 524288, wenig bis keine Ramp | **cache_hit_like** (teilweise) |
| Bayern `fav1` 512 KiB | meist `cold_burst` → 524288 | **USB-Re-Read** |
| Rock `fav0` ~8 MiB | **immer** voller Body-Sturm | **USB-Re-Read** (stabil) |

Play-Wechsel mit 3 s-`d_readCount` (Poll): siehe [`play-transitions.json`](play-transitions.json) — fast alle echten Track-Wechsel = `cold_burst`; `cache_hit_like`-Labels nur an RST-Drops.

**Boots (Poll-Segmente):** 7 nutzbare Boots in [`boots.json`](boots.json) — nach jedem RST wieder Rock-Eager + 512 KiB-Favs aufgefüllt.

---

## Befunde (für andere Instanzen)

1. **Kein Ton die ganze Session** — erwartet (Bridge aus, Silence-Dateien); kein AV-FAIL-Signal für Live-MPEG.  
2. **LED = Body**, korreliert mit Bursts; kein Live-MPEG-Beweis.  
3. **Rock 8 MiB** wird nach jedem RST/Auswahl **neu gelesen**; kleiner BOB-Slot überlebt RST eher im HU-Cache.  
4. **HU-UI-Limit** (nur Balken) blockiert klassisches F1 mit `t_timer=0:01`.  
5. **Detect:** `playingUid` oft erst nach Burst gesetzt; teils leer bei Cache-Play (wie s1-1700).  
6. Serial konstant **PD0089** (kein Serial-Wechsel-Test / F2d).

---

## Artefakte

Ordner: [`feld-s1-morgen/`](.)

| Datei | Inhalt |
|-------|--------|
| `status-poll.jsonl` | Roh 1 Hz Status (inkl. kurze Offline-Nachläufer) |
| `status-poll-session.jsonl` | Session-Schnitt bis ~08:00 |
| `status-poll-compact.csv` | flache Spalten für Spreadsheet/Peers |
| `f2-watch.jsonl` | Dense Watch + Operator-RST |
| `f1-events.jsonl` | Operator-Marken / UI-Notes |
| `SUMMARY.json` | Gesamtexport + Verdict-Entwurf |
| `boots.json` / `play-transitions.json` | Episoden |
| `OPERATOR-LIVE.txt` | Live-Log |
| `ingest.log` | DuckDB-Ingest |
| `run.yaml` | Run-Metadaten |
| `lab-prep/` | Q4 Dry-Run (nicht Feld-Stall) |

---

## Verdict / nächste Schritte

| Frage | Stand |
|-------|--------|
| F1 inkrementell vs. after_eof | **offen** (Balken-Timing fehlt); USB-Muster → after_eof/eager **wahrscheinlich** |
| F2a Cache in Session | **[S] leaning PASS** |
| F2c Cache über RST | **[S] gemischt** — klein/BOB eher Cache, Rock immer Re-Read |
| Stall-Go | **nein** — erst F1 mit Balken-Protokoll (Video auf Balken + Timestamp) oder Marker-Ton-Probe |

**Empfehlung Peer-Review:** `SUMMARY.json` + Compact-CSV + diesen Bericht; Fokus: (a) reicht Eager-Muster für Stall-Pfad, (b) wie F1 ohne Sekundenzähler operationalisieren, (c) Stall vs. Dateikette angesichts Rock-Re-Read nach RST.
