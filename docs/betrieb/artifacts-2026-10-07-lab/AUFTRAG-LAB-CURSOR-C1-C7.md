# Lab-Auftrag: Cursor-Geschwindigkeit und -Position (C1–C7)

**Stand:** 2026-10-07 · **Für:** Lab-Instanz (Debian-Container, Lab-ESP .88, FW **0.4.46-dev**, Geometrie **L3**) · **Freeze:** keine FW-Änderung
**Bezug:** [HU-Technical-Facts R15–R22](../../fahrzeug/HU-Technical-Facts.md) · [Stufenplan 3.2 feste Zuordnung, R10/R11](../../planung/Stufenplan.md) · [Korrektur s1-morgen](../artifacts-2026-10-07-feld/feld-s1-morgen/KORREKTUR-F2C-RST-ARTEFAKT.md)

## Ziel

Klären, **wie schnell** der Host-Cursor (`hostAbsCursor`) gegenüber dem Producer (`absEnd`) läuft und **welcher Dateioffset welchen Strominhalt** bekommt. Dabei soll die HU-Lesereihenfolge aus dem Feld gelten, nicht ein idealer sequenzieller Leser. Die Ergebnisse sind die Grundlage, um die feste Zuordnung (Stufenplan 3.2) vor einem Stall-Go zu prüfen.

---

## 0. Vorbereitung (einmalig, vor C1)

### 0.1 Tool-Stand

Die Tools wurden am 07.10. ohne Testlauf geändert (lokal kein Python). **Zuerst prüfen:**

```bash
python3 tools/nbt_hu_sim.py --self-test
python3 -m py_compile tools/nbt_hu_sim.py tools/m3_lab_hu_eager_file.py
sg disk -c 'python3 tools/nbt_hu_sim.py --golden ALL --sg /dev/sg0'   # Regression: G1–G5 wie bisher
```

Das ist neu:

| Änderung | Datei | Wirkung |
|----------|-------|---------|
| L1 Takt nach Fahrplan | `nbt_hu_sim.py --period-ms 4.0` / `5.1` | Abstand von Read-Start zu Read-Start wie die HU. Bisher lag eine Pause **nach** jedem Read (`gap_ms`), das ergab ~10 ms pro Read statt 4. Ohne Option bleibt das alte Verhalten, damit G1–G5 vergleichbar bleiben |
| L1 Zeitstatistik | `REPORT.json → timing` | `sg_duration_ms`, `wall_ms`, `start_to_start_ms` (p5/p50/p95/p99), `late_reads` |
| L2 Ohr-Fix | `VirtualEar.on_block` | Prüft **alle** PDSQ-Stempel im Block und merkt sich den letzten. Bisher meldete jeder 4-KiB-Block eine falsche Lücke von +16 |
| L3 Eager per SG_IO | `m3_lab_hu_eager_file.py --sg /dev/sg0 --period-ms 4.0` | Ein READ10 mit 4 KiB pro Schritt. Bisher `dd bs=512` = 8 READ10 zu 512 B plus Prozessstart pro 4 KiB, daher dauerte 8 MiB im Lab 32 s statt ~8 s. Alter Weg: `--use-dd` |
| L4 Lesereihenfolge | `--golden G7` (Auswahl ab Kopf), `--golden GW` (Wiederaufnahme um P) | Feldmodelle R17 und R16 |
| L5 Remount / Prefetch | `--golden G8` (Wiederanlauf `rc=167`), `--golden G4N` (Prefetch 15 s vor Ende) | Feldmodelle R20 und R21 |
| L6 Per-Read-JSONL | `<out>/reads.jsonl` in beiden Tools | Je Read: `wall`, `uid`, `off`, `lba`, `n`, `klass`, `dur_ms`, `wall_ms`, `seq0`/`seq1`/`abs0` (PDSQ). **Immer mit archivieren** |
| C6 Replay | `--golden REPLAY --replay <msc_reads.jsonl>` | Spielt Feld-`msc.reads` mit LBA und Zeit nach |

**Hinweis:** Die älteren `m3_lab_*`-Tools lesen weiter per `dd bs=512`. Ihre Zeit- und `readCount`-Werte sind nicht HU-ähnlich und gelten nicht als Kalibrierung.

### 0.2 Bridge im Lab (L7)

Für C2, C4 und C6 braucht es den ESP-Export `msc.reads`. Den gibt es nur bei verbundener Bridge:

```bash
python3 esp32.pidrive-main/tools/pump_bridge.py --transport tcp --host 192.168.178.88 --no-audio
# schreibt /tmp/pidrive_msc_reads.jsonl  → nach jedem Lauf in <out>/ kopieren und leeren
```

Achtung: Der Sim öffnet selbst eine Pump-TCP-Verbindung. Vorher prüfen, ob der ESP **zwei** Clients gleichzeitig annimmt. Wenn nicht, laufen C2-„mit Bridge“ und die Sim-Goldens mit Producer getrennt, und die PUMP-Last wird mit der Bridge allein erzeugt.

### 0.3 Ablage

Je Lauf ein Ordner `docs/betrieb/artifacts-2026-10-07-lab/lab88-<test>-<HHMM>/` mit `REPORT.json`, `reads.jsonl`, ggf. `msc_reads.jsonl`, `status-*.json`, `RUN.log`, Kommandozeile.

---

## C1 — Obergrenze Bus/ESP: schafft das Lab ≥ 250 Reads/s?

**Frage:** Liest das Lab so schnell wie die HU (4,0 ms pro 4 KiB)? Wenn nicht, sind alle Zeitaussagen des Sims unterhalb dieser Grenze verfälscht.

**Ablauf:** ESP frisch remountet, kein Producer, **keine** Bridge, kein Status-Poll.

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 2000 --sg /dev/sg0'
```

3× wiederholen.

**Messgrößen:** `reads_per_s`, `ms_per_4k`, `sg_duration_ms.p50/p95`, `esp_readCount_delta`.

**Abnahme:**
- **Neu (07.10. nachmittags):** `sg_duration p50 ≤ 4,1 ms` = ESP/Bus auf HU-Niveau. Reads/s an der Wanduhr enthält ~0,8 ms Host-Abstand pro Kommando und ist kein Kriterium (siehe `C1-C7-ERGEBNIS.md`, N1).
- ~~≥ 245 Reads/s~~ (ursprüngliches Kriterium, misst den Lab-Host mit).

## C2 — ESP-Servicezeit je Zustand: woher kommen 5,1 ms?

**Frage:** Im Feld liest die HU mit 4,0 ms pro Read, solange der ESP nichts spielt, und mit 5,1 ms, sobald `playingUid` gesetzt ist (R15). Welcher ESP-Zustand kostet die 1,1 ms?

**Matrix** (je Zelle `BENCH 4096 × 2000`, 2 Wiederholungen):

| Zustand ESP | HTTP-Poll | Bridge (`msc.reads`) |
|-------------|-----------|----------------------|
| idle (kein `audio_start`) | 0 / 1 / 10 Hz | aus / an |
| armed (`audio_start fav0`, kein Producer) | 0 / 1 / 10 Hz | aus / an |
| armed + Producer 9 KB/s | 0 / 1 / 10 Hz | aus / an |
| armed, gelesen wird ein **Nicht-Live-Slot** (`--bench-uid fav1`) | 1 Hz | an |

Zustände per Option:
- idle: ohne `--live`;
- armed: `--live fav0 --live-no-producer`;
- armed + Producer: `--live fav0`;
- Nicht-Live-Slot: `--live fav0 --bench-uid fav1`.

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 2000 --live fav0 --sg /dev/sg0'
```

**Messgrößen:** `ms_per_4k`, `sg_duration_ms.p50/p95/p99`.

**Auswertung:** Tabelle `ms_per_4k` je Zelle. Erwartung: eine Zeile springt von ~4,0 auf ~5,1 ms.
- Liegt der Sprung am **Live-Pfad** (`readAt`, `noteDataRead`), ist das ein ESP-Thema und wichtig für den Stall-Adapter, denn der Adapter bekommt weniger Zeitbudget.
- Liegt er an **Poll oder Bridge**, ist es ein Messartefakt und im Feld abschaltbar.

## C3 — Größen-Sweep: Callback-Granularität

**Frage:** In welcher Stückelung ruft TinyUSB `onRead` auf? Das bestimmt, wie fein der Stall-Adapter Teilantworten geben kann.

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 512,4096,16384,65536 --bench-n 500 --sg /dev/sg0'
```

**Messgrößen:** pro Größe `reads_per_s`, `MBps`, `esp_readCount_delta / reads` (Callbacks pro READ10).

**Auswertung:**
- `readCount` pro 64-KiB-Read = 16 heißt, ein Callback je 4 KiB (`CFG_TUD_MSC_EP_BUFSIZE` = 4096).
- MB/s bei 512 B zeigt den Fix-Overhead pro Kommando (CBW/CSW). Diesen Wert in Spike-Doc N5 nachtragen.

## C4 — Zuordnung Dateioffset → Strominhalt bei Lesen außer der Reihe

**Frage:** Welcher Strominhalt (PDSQ `abs0`) landet an welchem Dateioffset, wenn die HU wie im Feld liest? Das ist die Referenz für 0.4.46 (zählender Cursor) und später für die feste Zuordnung.

**Ablauf** (je Reihenfolge 2×):
1. `--live fav0`: Remount, `audio_start fav0`, `RealisticProducer` (PDSQ, 1,45× für 60 s, dann Echtzeit), 8 s Vorlauf (`--live-prefill-s`).
2. Den Sim mit `--period-ms 5.1` in drei Reihenfolgen lesen lassen:

   ```bash
   sg disk -c 'python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 2048 --live fav0 --period-ms 5.1 --sg /dev/sg0'  # sequenziell
   sg disk -c 'python3 tools/nbt_hu_sim.py --golden GW --live fav0 --period-ms 5.1 --sg /dev/sg0'
   sg disk -c 'python3 tools/nbt_hu_sim.py --golden G7 --live fav0 --period-ms 5.1 --sg /dev/sg0'
   ```

   Achtung: `BENCH` schaltet den Takt intern ab (back-to-back). Für C4 sequenziell zählt nur die Reihenfolge, nicht der Takt.
3. `reads.jsonl` archivieren.

**Auswertung:** Tabelle je Read: `off`, `klass`, `abs0`, `seq0`, `seq1`. Daraus:
- `abs0 − off` über der Zeit. Bei fester Zuordnung wäre das eine **Konstante**; bei 0.4.46 ist ein zählender Cursor zu erwarten, mit `abs0` monoton in **Lesereihenfolge**, nicht in Dateireihenfolge.
- Anzahl der Rückwärts-Reads mit **neuem** Inhalt (das wäre der falsche Inhalt am alten Offset).
- `duplicate`- und `gap_in_content`-Ereignisse des Ohrs, jetzt ohne Fehlalarm.
- Position der `nearHead`-Resyncs: Sprung von `abs0` auf die Kopfposition.

**Abnahme:** Die Tabelle ist reproduzierbar (2/2) und als `C4-MAPPING.csv` abgelegt. **Zusatz 07.10.:** Mindestens 100 LIVE-Reads **außer der Reihe** in der Tabelle, sonst ist nur der sequenzielle Kopf geprüft (C4-Lauf 1209 hatte 12 LIVE, alle sequenziell). Dafür den Sim auf Producer-Tempo drosseln (C4b). Daraus folgt eine Testvorlage für die FW nach Go: gleiche Reihenfolge, Erwartung `abs0 − off = const` für alle LIVE-Blöcke.

## C5 — Steigung `hostAbs − absEnd`: Cursor-Geschwindigkeit direkt

**Frage:** Mit welcher Rate läuft der Cursor dem Producer davon, und ab wann liefert der ESP nur noch Stille?

**Ablauf:**
1. Wie C4 sequenziell, `--period-ms 4.0` und dann `5.1`.
2. Parallel einen Status-Poll mit **10 Hz** laufen lassen: `python3 tools/feld_status_poll.py --esp http://192.168.178.88 --interval 0.1 --seconds 120 --out <out>/poll-10hz.jsonl`. Felder `hostAbsCursor`, `absEnd`, `absBase`, `underruns`, `readCount`, Wanduhr.
3. Einmal mit 1 Hz als Gegenprobe; laut C2 kann der Poll selbst bremsen.

**Auswertung:**
- Plot von `d = hostAbs − absEnd` über `t`.
- Steigung während des Lesens: erwartet ≈ Leserate − Producer-Rate ≈ 0,8–1,0 MB/s − 9 KB/s.
- `t_cross`: Zeitpunkt, an dem `d` > 0 wird (ab da Stille).
- `underruns`-Rate muss der Steigung entsprechen.

**Abnahme:** Die Steigung stimmt auf ±5 % mit `reads.jsonl` überein (Bytes pro s). Damit ist die Cursor-Geschwindigkeit als Zahl belegt und kein Modell mehr.

## C6 — Replay der Feld-Episoden und Musterabgleich

**Frage:** Erzeugt die echte Feld-Lesefolge im Lab dieselben ESP-Zähler? Und passt das G7-Modell zu s1-morgen?

**Episoden** (Ränder aus Pausen > 2 s, ESP-`ms`):

| Datei | Episode | ms | Start-LBA | Bytes |
|-------|---------|----|-----------|-------|
| `artifacts-2026-10-04-feld/p1-run-a/msc_reads.jsonl` | Plug-Scan | 217113–218891 | 0 | 1.374.720 |
| ebd. | Wiederaufnahme um P | 364034–365907 | 1953 | 1.982.464 |
| ebd. | Lauf bis EOF | 371055–376757 | 4625 | 6.057.984 |
| `artifacts-2026-10-04-feld/p1-run-b/msc_reads.jsonl` | Wiederaufnahme um P (nach Neustart) | 171378–173250 | 1953 | 1.982.464 |
| `artifacts-2026-10-03-m3/auto89-m3seq-2042/pidrive_msc_reads.jsonl` | Wiederaufnahme (größer) | 184143–188302 | 1953 | 4.407.296 |

Hinweis: `p1-run-b` enthält am Anfang die Zeilen von `p1-run-a` und hat einen ms-Rücksprung (ESP-Neustart). Deshalb immer mit `--replay-ms-from/--replay-ms-to` schneiden. Spalte `ov` ist ein Überlauf-Zähler; in `p1-run-b` steht `ov=116`, dort fehlen also Bursts.

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --golden REPLAY --period-ms 4.0 \
  --replay docs/betrieb/artifacts-2026-10-04-feld/p1-run-a/msc_reads.jsonl \
  --replay-ms-from 364034 --replay-ms-to 376757 --sg /dev/sg0'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G7 --period-ms 4.0 --sg /dev/sg0'
sg disk -c 'python3 tools/nbt_hu_sim.py --golden G7 --g7-autoplay --period-ms 4.0 --sg /dev/sg0'
```

**Abnahme:**
- REPLAY: ESP `slots.fav0.bytes_delta` = Summe der Episode (±4 KiB). `maxSeq` und `readCount_delta` mit dem Feld-Status vom selben Tag vergleichen, sofern vorhanden.
- G7: `maxSeq_after_head = 368.640`, `maxSeq_final = 5.201.920`, `bytes_delta = 8.179.712`. **Bekannte Abweichung:** Im Feld steigt `maxSeq` in der Fragmentphase auf 392–632 KiB, im Modell bleibt es bei 360 KiB. Die echte Fragmentfolge kommt erst aus dem Feld-`msc.reads` (Feldprotokoll Q8). Danach das Modell anpassen.
- Die Lage der 51 ungelesenen Blöcke ist im Modell eine **Annahme** (Lücke direkt vor dem Endlauf). Prüfen, sobald Feld-LBAs vorliegen.

## C7 — Wiederanlauf nach Remount und RST

**Frage:** Bildet G8 die Feld-Signatur `rc=167` nach, und verhält sich der ESP bei Remount anders als bei RST?

**Ablauf:** Je 3×:
- `--golden G8` (nach `/api/lab/remount`);
- dasselbe nach Soft-RST (`--soft-rst`).

Dazu `usbSerial` vor und nach notieren.

**Abnahme:**
- `readCount_delta` = 167 ± 2 (31 Meta-Reads + 8 Stichproben + 128 Datei-Reads; der eigene Probe-Read des Sims nach `open()` liegt davor).
- `fav0_bytes_delta = 32.768`, `fav0_maxSeq = 4.096`, aktueller Titel `maxSeq = 524.288`.
- Serial: Remount wechselt sie, RST nicht (HU-Facts F6). Wenn das im Lab anders ist, eintragen.
- Plug-Scan-Signatur (R22): Nach echtem Re-Plug am Lab-Host den ersten Burst ab LBA 0 messen. Ist er ≠ 1.374.720 B, liest der Linux-Host anders als die HU (erwartet). Dann gilt G8 nur für das ESP-Zählverhalten, nicht für den Host.

---

## Zwischenstand 2026-10-07 ~13:50

Siehe [`C1-C7-ERGEBNIS.md`](C1-C7-ERGEBNIS.md).

- ALL, C2–C4, C6–C7, G6 **PASS**; C1 Lab-Host-Limit; C5 Steigung im Clean-Fenster ok, Wi-Fi unter MSC bricht ab.
- Nachträge: HU-Facts R15/Q9, Stufenplan EP=4 KiB, Maßnahmen-Ampel Lesetakt 🟢.

## Rückmeldung

Kurzbericht `C1-C7-ERGEBNIS.md` im Lab-Ordner. Pro Test: Kommando, Zahl, PASS/FAIL, Abweichung. Danach trage ich die Ergebnisse in diese Dokumente ein:
- HU-Facts R15 (Ursache 5,1 ms) und Q9;
- Stufenplan 3.2 (`stallAhead`, Zeitbudget des Adapters);
- Kalibrierblatt G4n/G7/G8.
