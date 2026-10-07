# Feldprotokoll s2: 30 Minuten am Auto

**Stand:** 2026-10-07 nachmittags · FW **0.4.46-dev** unverändert (Freeze, **kein** Stall-OTA) · Geometrie L3 · ESP .89 (PD0089)
**Ausrüstung:** Pi, Handy (Video + Ton), USB-Stick mit `F1-*.mp3`, USB-1.1-Hub
**Bezug:** [HU-Facts R15–R22, Q8](../../fahrzeug/HU-Technical-Facts.md) · [Stufenplan R10](../../planung/Stufenplan.md) · [Lab N1–N4](../artifacts-2026-10-07-lab/C1-C7-ERGEBNIS.md) · [Lab-Probe T1–T4](../artifacts-2026-10-07-lab/AUFTRAG-LAB-S2-PROBE-T1-T4.md)

## Ziel

Zwei Fragen entscheiden über den Stall-Go:
- **R10/Q8:** Wie liest die HU eine frisch gewählte Datei (Reihenfolge, wie weit voraus)?
- **F1:** Spielt die HU, während sie liest, oder erst nach dem Lesen?

Alles andere ist Beifang. Im Auto wird **nichts ausgewertet**. Es wird nur aufgezeichnet und markiert. Die Auswertung macht das Lab.

Gegenüber dem Langprotokoll entfallen Teil D (Quellenwechsel) und Teil F (Q4 Cache). A und C sind zu einem Zyklus zusammengelegt: Das RST am Ende eines Zyklus ist zugleich Teil C und die Vorbereitung für das nächste A.

## Vorher (zu Hause, nicht in den 30 min)

| # | Schritt | Kommando |
|---|---------|----------|
| V1 | Lab-Probe T4 bestanden (Skripte laufen auf dem Pi) | [`AUFTRAG-LAB-S2-PROBE-T1-T4.md`](../artifacts-2026-10-07-lab/AUFTRAG-LAB-S2-PROBE-T1-T4.md) |
| V2 | Stick bauen: 5MB und 100MB, 128k spart Zeit und Temp-Platz | `BR=128k ./feld-s2-prep/make-f1-stick.sh /mnt/stick` |
| V3 | Stick am Laptop kurz anhören: Marker „null“, „zehn“ … hörbar | — |
| V4 | Skripte ausführbar | `chmod +x feld-s2-prep/*.sh` |

---

## Ablauf (Uhr läuft ab Ankunft)

Jede Bedienung an der HU bekommt **vorher** eine Marke im zweiten Terminal: `./mark.sh "A1 BOB tap"`. Die Marke ist die Wanduhr; das Video ist die Absicherung.

### 0–3 min: Start

| Min | Aktion | Prüfung |
|-----|--------|---------|
| 0 | Handy-Video starten (HU-Display **und** Pi-Terminal mit `watch -n0.2 date +%T.%N` im Bild, Ton an) | Uhr im Bild lesbar |
| 1 | Terminal 1: `cd feld-s2-prep && ./run-s2.sh 2400` | Zeile `== Start …` |
| 2 | Terminal 2: `./mark.sh "s2 start"` | Lebenszeichen alle 10 s: `msc.reads=` wächst bei HU-Reads, `trace:` zeigt `new` > 0, kein `DEAD:` |

Wenn `trace:` nur Fehler zeigt (WLAN), weiterlaufen lassen. `msc.reads` über die Bridge reicht als Hauptquelle.

### 3–12 min: A+C-Zyklus, 3×

Ein Zyklus dauert ~2,5 min. BOB vorher sorgt dafür, dass Rock nach dem RST **nicht** im HU-Cache ist (R20).

| Schritt | Marke | Aktion | Dauer |
|---------|-------|--------|-------|
| 1 | `Zn BOB tap` | BOB antippen | 10 s |
| 2 | `Zn RST1` | `curl -s -m 3 -X POST http://192.168.178.89/api/restart` | 15 s warten |
| 3 | `Zn Rock tap` | **Rock antippen** (= Teil A, frische Auswahl) | 60 s laufen lassen |
| 4 | `Zn RST2` | RST (= Teil C, RST bei laufendem Rock, Position ~60 s) | 20 s warten, nichts bedienen |

`n` = 1, 2, 3. Nach Zyklus 3 geht es direkt weiter mit E.

### 12–21 min: E, F1 mit Stick über USB-1.1-Hub

| Schritt | Marke | Aktion | Notieren (laut ins Video sprechen) |
|---------|-------|--------|-----------------------------------|
| E0 | `E plug stick` | ESP-Kabel ab, Hub + Stick an den HU-Port | Zeit bis zur Medienliste |
| E1 | `E tap 100MB` | `F1-100MB` antippen | Zeit bis zum ersten Marker; **welche Zahl** zuerst |
| E2 | `E tap 5MB` | nach 30 s `F1-5MB` antippen | wie E1 |
| E3 | `E tap 100MB again` | nach 30 s nochmal `F1-100MB` antippen | wie E1 (zweiter Zugriff, Cache-Effekt) |
| E4 | `E replug ESP` | nach 30 s Stick ab, ESP wieder an | — |

Die HU liest dabei vom Stick; ESP-Daten gibt es in dieser Zeit nicht. Das Video mit Ton ist hier die einzige Quelle. Beim Wiederanstecken des ESP entsteht ein Scan (R22). Den nimmt `run-s2.sh` mit.

### 21–25 min: B, Autoplay auf Rock

| Schritt | Marke | Aktion |
|---------|-------|--------|
| B1 | `B Bayern tap` | Bayern antippen, **bis zum Ende laufen lassen**, nichts bedienen (s1-morgen: ~1,5 min) |
| B2 | `B autoplay Rock` | sobald die HU auf Rock wechselt |
| B3 | — | Rock 60 s laufen lassen |

Bei Zeitnot fällt B weg. B prüft R19/R21, entscheidet aber nicht über den Stall-Go.

### 25–30 min: Puffer und Ende

| Schritt | Aktion |
|---------|--------|
| 1 | Offene Schritte wiederholen, falls Zeit bleibt: zuerst ein vierter A+C-Zyklus, dann E1 |
| 2 | `./mark.sh "s2 ende"`, dann Ctrl-C in Terminal 1 |
| 3 | Ausgabe prüfen: `msc.reads → …`, `ov first/last`, `pidrive_pump_bridge wieder gestartet` |
| 4 | Video stoppen |

---

## Abbruchregeln

| Lage | Reaktion |
|------|----------|
| Nach Rock-Tap keine `msc.reads`-Zunahme in 20 s | Zyklus abbrechen, `./mark.sh "Zn kein read"`, nächsten Zyklus starten. Zwei Zyklen ohne Reads: Bridge-Log ansehen (`<RUN>/bridge-noaudio.log`) |
| ESP nach RST nicht wieder erreichbar (> 45 s) | ESP-Kabel ab/an, Marke setzen, weiter |
| `ov` steigt pro Zyklus um > 0 | weiter; der Trace-Poll füllt die Lücken. Notieren |
| HU zeigt Fehlermeldung | Foto, Marke, weiter mit dem nächsten Schritt |
| Stick wird nicht erkannt (E0 > 60 s) | Stick ohne Hub versuchen und `E ohne Hub` markieren; dann ist nur der 100MB-gegen-5MB-Vergleich deutbar |
| Minute 21 erreicht und E nicht fertig | B streichen, E zu Ende bringen |

---

## Auswertung zu Hause (Lab)

```bash
RUN=feld-s2-prep/s2-<datum-zeit>
python3 tools/feld_q8_msc_order.py --reads $RUN/msc_reads.jsonl --trace $RUN/trace.jsonl --out-dir $RUN/q8
```

| Frage | Quelle | Entscheidung |
|-------|--------|--------------|
| R10/Q8 | Episoden nach `Zn Rock tap`, Muster `pattern_kib` | siehe Tabelle R10 unten |
| C (RST bei Rock) | Episoden nach `Zn RST2`: Scan, dann Kopf oder Wiederaufnahme um P (R16)? | Quelle von P |
| F1 | Video E1–E3 | siehe Tabelle F1 unten |
| R15 | `status-poll.jsonl`: Reads/s ohne Play gegen mit Play | Abgleich 250/195 |
| R19/R21 | Episode nach `B autoplay Rock` | Pause ~4 MiB, Prefetch ~15 s vor Ende |

Die Episoden gehen danach als Lab-Replay an den Sim (`--golden REPLAY --replay … --replay-ms-from … --replay-ms-to …`).

**Entscheidung R10:**

| Befund | Folge für Stall (Stufenplan 3.2) |
|--------|----------------------------------|
| Fragmente liegen alle **knapp hinter** dem ersten Lauf (≤ ~1 MiB), danach sequenziell | Feste Zuordnung + `stallAhead` ≈ Fragmentbereich reicht. Stall-Pfad bleibt Plan A |
| Fragmente springen **weit voraus** (MiB, z. B. an das Dateiende) | Vorauslesen trifft immer die ferne Zukunft. Dann entweder Live-Slot so klein, dass „voraus“ begrenzt ist, oder Fallback Dateikette. Stall allein reicht nicht |
| Frische Auswahl liest wie die Wiederaufnahme (R16: F8/B120/B120/F360/B360/F968) | Startposition ist ≠ 0. Klären, woher die HU P nimmt (gespeicherte Position?) |

**Entscheidung F1:**

| Befund | Bedeutung | Folge |
|--------|-----------|-------|
| Erster Marker ≤ 3 s nach Antippen bei 100 MB (Full-Speed) | **inkrementell**: Die HU spielt, während sie liest | Stall-Pfad (Stufe 3–5), sobald R10 geklärt |
| Wartezeit ≈ Dateigröße / Leserate (100 MB ≈ 100 s) | **Batch-then-Play** | Fallback Dateikette, Stall nur Hilfsmittel |
| Wartezeit konstant ~5–15 s, unabhängig von der Größe | **Read-Ahead-Fenster** | Fenstergröße = Rate × Wartezeit. Stall gut geeignet |
| Erster Marker ist nicht „null“ | HU setzt an gespeicherter Position fort | E3 gegen E1 vergleichen; P-Quelle wie bei R16 |

**Stall-Go erst wenn:** F1 entschieden **und** R10 geklärt.

## Ablage

`run-s2.sh` legt alles in `feld-s2-prep/s2-<datum-zeit>/` ab:

| Datei | Inhalt |
|-------|--------|
| `msc_reads.jsonl` | Bridge-Bursts (Kopie bei Ctrl-C) |
| `trace.jsonl` + `trace.jsonl.polls.jsonl` | Einzel-Reads aus `mscTrace` (4 Hz), Poll-Protokoll mit Wanduhr und `uptimeMs` |
| `status-poll.jsonl` | 1 Hz Zähler |
| `bridge-noaudio.log` | Bridge-Ausgabe |
| `marks.jsonl`, `OPERATOR-LIVE.txt` | Marken mit Wanduhr |

Dazu von Hand: `video/` (Dateiname + Startzeit laut Uhr im Bild) und `run.yaml` (`hub_usb11: ja/nein`, `usb_stick`, Bitrate des Sticks).
