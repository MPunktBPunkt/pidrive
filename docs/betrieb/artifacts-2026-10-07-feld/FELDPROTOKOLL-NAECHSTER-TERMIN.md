# Feldprotokoll nächster Termin: Lesereihenfolge (Q8) und Decode-Start (F1)

**Stand:** 2026-10-07 · FW **0.4.46-dev** unverändert (Freeze, **kein** Stall-OTA) · Geometrie L3 · ESP .89 (PD0089)
**Bezug:** [Korrektur s1-morgen](feld-s1-morgen/KORREKTUR-F2C-RST-ARTEFAKT.md) · [HU-Facts R15–R22, Q8](../../fahrzeug/HU-Technical-Facts.md) · [Stufenplan R10](../../planung/Stufenplan.md) · [Lab C1–C7](../artifacts-2026-10-07-lab/AUFTRAG-LAB-CURSOR-C1-C7.md)

## Warum dieser Termin

s1-morgen hat zwei Lücken gezeigt:
1. **Ohne Bridge gibt es keine LBA-Daten.** Bei gestoppter Bridge exportiert der ESP kein `msc.reads`. Die Lesereihenfolge (Rock ab Kopf, Fragmente, 51 ungelesene Blöcke) lässt sich deshalb nur aus 1-Hz-Zählern erraten.
2. **F1 ist per Bildschirm nicht entscheidbar.** Die HU zeigt nur einen Balken (F7), und der ESP liefert nur Stille.

Dieser Termin schließt beide Lücken ohne FW-Änderung. Q4 (Cache-Größe) kommt **erst danach**.

**Stall-Go erst wenn:** F1 entschieden **und** R10 geklärt (Teil A unten).

---

## 0. Aufbau (vor dem ersten Antippen)

| # | Schritt | Kommando / Hinweis |
|---|---------|--------------------|
| 0.1 | Uhrzeit Pi per NTP prüfen, `run.yaml` aus s1-morgen kopieren, `run_id: feld-s2-<datum>` | `timedatectl` |
| 0.2 | **Video läuft vor der ersten Auswahl:** Handy filmt HU-Display **und** eine Sekundenuhr (Pi-Terminal `watch -n0.2 date +%T.%N` auf zweitem Handy oder Laptop). Ohne Uhr im Bild ist das Video nicht mit den Logs synchronisierbar | Ton mit aufnehmen (für Teil E) |
| 0.3 | Bridge-Dienst stoppen, Bridge **mit `--no-audio` von Hand** starten. Damit kommt `msc.reads`, aber kein Live-Audio (Zustand wie s1-morgen) | siehe unten |
| 0.4 | Status-Poll 1 Hz | `./run-status-poll.sh 3600` (ESP .89) |
| 0.5 | Operator-Log: jede Aktion mit Uhrzeit | `./run-f1-log.sh` bzw. `OPERATOR-LIVE.txt` |

```bash
sudo systemctl stop pidrive_pump_bridge
: > /tmp/pidrive_msc_reads.jsonl
python3 /home/pidrive/pump_bridge.py --transport tcp --host 192.168.178.89 --no-audio 2>&1 \
  | tee "$RUN/bridge-noaudio.log"
```

**Prüfen nach 0.3:** Im Log erscheinen `[msc.reads] …`-Zeilen, sobald die HU liest. **Spalte `ov`** (Überlauf-Zähler) notieren. Steigt `ov` während einer Rampe, fehlen Bursts, und die Episode zählt nur eingeschränkt.

**Bekannte Nebenwirkung:** Die verbundene Bridge kann den Lesetakt ändern (Lab C2). Deshalb `readCount`-Steigung pro Sekunde je Teil mit s1-morgen vergleichen: 250/s ohne Play, 195/s mit Play.

---

## A. Rock ab Kopf, frisch gewählt (Q8, entscheidend für R10) — 3×

**Ziel:** Vollständige LBA-Folge einer **frischen** 8-MiB-Auswahl. Das umfasst den ersten Lauf (368.640 B), die Fragmentphase mit den echten Offsets, den Endlauf und die Lage der 51 ungelesenen Blöcke.

| Schritt | Aktion | Erwartung (s1-morgen) |
|---------|--------|----------------------|
| A1 | BOB antippen, 20 s spielen lassen | BOB ist aktueller Titel |
| A2 | ESP-RST (`/api/restart`), 15 s warten | Wiederanlauf: `rc≈167`, BOB komplett, 8 Stichproben fav0 (R20). Rock ist **nicht** im HU-Cache |
| A3 | **Rock antippen**, Uhrzeit notieren | Rampe 368.640 B, Fragmente 2–3 s, Endlauf |
| A4 | 30 s nichts tun | keine weiteren Reads |

**Auswertung** (aus `msc_reads.jsonl`, LBA → Dateioffset `(lba − 81) × 512`):
- Liste der Segmente: Start, Länge, Richtung, Zeit.
- Größter Dateioffset, der in den ersten 2 s gelesen wird.
- Lage der nie gelesenen Blöcke.

**Entscheidung R10:**

| Befund | Folge für Stall (Stufenplan 3.2) |
|--------|----------------------------------|
| Fragmente liegen alle **knapp hinter** dem ersten Lauf (≤ ~1 MiB), danach sequenziell | Feste Zuordnung + `stallAhead` ≈ Fragmentbereich reicht. Stall-Pfad bleibt Plan A |
| Fragmente springen **weit voraus** (MiB, z. B. an das Dateiende) | Vorauslesen trifft immer die ferne Zukunft. Dann entweder Live-Slot so klein, dass „voraus“ begrenzt ist, oder Fallback Dateikette. Stall allein reicht nicht |
| Frische Auswahl liest wie die Wiederaufnahme (R16: F8/B120/B120/F360/B360/F968) | Startposition ist ≠ 0. Klären, woher die HU P nimmt (gespeicherte Position?) |

## B. Autoplay-Wechsel auf Rock — 2×

**Ziel:** R19 (Pause nach ~4 MiB) und R21 (Prefetch ~15 s vor Ende) mit LBAs belegen.

| Schritt | Aktion |
|---------|--------|
| B1 | Bayern antippen, **bis zum Ende laufen lassen**, nichts bedienen |
| B2 | Autoplay wechselt auf Rock; Zeit des Wechsels im Video |
| B3 | Rock 60 s laufen lassen |

**Auswertung:** Startzeit des Rock-Prefetch relativ zum Bayern-Ende (aus dem Video). Lage der Pause (Offset und Dauer). Vergleich der LBA-Folge mit Teil A: Gleicht ein Autoplay-Prefetch einer frischen Auswahl?

## C. RST bei laufendem Rock — 2×

**Ziel:** Wiederanlauf-Rampe (Summe 8.179.712 B, M4) mit LBAs, plus die Frage, ob nach RST die Wiederaufnahme-Folge R16 um die Wiedergabeposition kommt.

| Schritt | Aktion |
|---------|--------|
| C1 | Rock läuft mindestens 60 s (Wiedergabeposition > 0) |
| C2 | ESP-RST, 20 s warten, nichts bedienen |

**Auswertung:**
- Erste Reads nach RST: LBA 0 / Scan (R22: 1.374.720 B?), dann Rock ab Kopf oder ab Wiedergabeposition?
- Gesamtbytes fav0 und die ungelesenen Blöcke.

## D. Quellenwechsel (optional, 1×)

Rock läuft 60 s → Quelle Radio → 10 s → zurück USB. Prüfen, ob R16 (Wiederaufnahme um P) daraus entsteht. Der Auslöser der Folge vom 03./04.10. ist nicht protokolliert.

## E. F1 Decode-Start mit echtem USB-Stick — je Datei 2×

**Ziel:** F1 hörbar entscheiden. Der ESP kann mit 0.4.46 keinen hörbaren Inhalt liefern (Korrektur K2). Deshalb kommt ein **normaler USB-Stick** mit echten MP3s an den HU-Port, statt des ESP.

**Dateien vorbereiten** (am Pi oder Laptop, vor dem Termin):
- Sprachmarker alle 10 s, gesprochen wird die Position („null“, „zehn“, „zwanzig“ … „eins null null“ …).
- Format wie die Bridge: MPEG-2 Layer III, 22,05 kHz, mono, 48 kbit/s CBR, ID3 mit Titel.
- `F1-5MB.mp3`: ~5 MB ≈ 14 min bei 48k.
- `F1-100MB.mp3`: ~100 MB ≈ 4,6 h (Markerschleife mit fortlaufender Zahl).
- Optional `F1-1GB.mp3`, falls kein USB-1.1-Hub da ist (siehe unten).

```bash
# Skizze: 10-s-Blöcke mit gesprochener Zahl, dann zusammenfügen und kodieren
for i in $(seq 0 10 830); do
  espeak-ng -v de "$i" -w m.wav
  ffmpeg -loglevel error -y -i m.wav -af apad=whole_dur=10 -ar 22050 -ac 1 "blk_$(printf %05d $i).wav"
done
ls blk_*.wav | sed 's/^/file /' > list.txt
ffmpeg -f concat -i list.txt -c:a libmp3lame -b:a 48k -ar 22050 -ac 1 -metadata title="F1-5MB" F1-5MB.mp3
```

**Warum USB-1.1-Hub:** Ein normaler Stick läuft am HU-Port vermutlich mit High-Speed. 100 MB sind dann in wenigen Sekunden gelesen, und „sofort hörbar“ wäre kein Beweis. Ein USB-1.1-Hub zwischen HU und Stick erzwingt Full-Speed (~1 MB/s wie beim ESP). Dann braucht ein Komplett-Read von 100 MB ≈ 100 s. Ohne Hub nimmt man die 1-GB-Datei: bei ~30 MB/s ≈ 33 s.

| Schritt | Aktion | Messung |
|---------|--------|---------|
| E1 | Stick (über Hub) einstecken, Medienliste abwarten | Zeit Plug → Liste |
| E2 | `F1-100MB` antippen (Video + Ton laufen) | `t_voice` = Antippen → erster Marker hörbar; **welcher** Marker zuerst („null“?) |
| E3 | 30 s hören, dann `F1-5MB` antippen | `t_voice` |
| E4 | Wiederholen (zweiter Durchgang, ggf. erst nach Ab-/Anstecken) | Cache-Effekt |

**Entscheidung F1:**

| Befund | Bedeutung | Folge |
|--------|-----------|-------|
| `t_voice` ≤ 3 s bei 100 MB (Full-Speed) bzw. 1 GB | **inkrementell**: Die HU spielt, während sie liest | Stall-Pfad (Stufe 3–5), sobald R10 geklärt |
| `t_voice` ≈ Dateigröße / Leserate | **Batch-then-Play** | Fallback Dateikette, Stall nur Hilfsmittel |
| `t_voice` konstant ~5–15 s, unabhängig von der Größe | **Read-Ahead-Fenster** | Fenstergröße = Rate × `t_voice`. Stall gut geeignet |

## F. Erst danach: Q4 (Cache-Kapazität)

Nur wenn Zeit bleibt, nach Katalog [`EXPERIMENTKATALOG-Q4-…`](../artifacts-2026-10-06-feld/EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md). Wichtig: Nach einem RST liest die HU neu (K1). RST ist deshalb **kein** Cache-Test. Cache-Fragen nur innerhalb einer Session ohne RST.

---

## Ablage und Abschluss

Ordner `artifacts-<datum>-feld/feld-s2-<zeit>/`:

| Datei | Inhalt |
|-------|--------|
| `run.yaml` | wie s1-morgen, plus `bridge.state_during_probes: no_audio`, `usb_stick`, `hub_usb11: ja/nein` |
| `msc_reads.jsonl` | Kopie von `/tmp/pidrive_msc_reads.jsonl` (**nach jedem Teil sichern**, Datei nicht zwischendurch leeren) |
| `bridge-noaudio.log` | Bridge-Ausgabe |
| `status-poll.jsonl` | 1 Hz |
| `OPERATOR-LIVE.txt` / `f1-events.jsonl` | Aktionen mit Uhrzeit |
| `video/` | Dateinamen + Startzeit laut Uhr im Bild |
| `F1-STICK.md` | `t_voice` je Datei, erster Marker, Hub ja/nein |

Danach `./run-ingest.sh`. Episoden aus `msc_reads.jsonl` als Lab-Replay übergeben (C6: `--golden REPLAY --replay … --replay-ms-from … --replay-ms-to …`).

**Bridge danach zurück auf Normalbetrieb:** `sudo systemctl start pidrive_pump_bridge`.
